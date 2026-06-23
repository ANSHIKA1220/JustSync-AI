import asyncio
import logging
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import vector_store
from .ai_providers import analyze_with_fallback
from .models import (
    AISuggestion,
    AuditLog,
    Conversation,
    Customer,
    KnowledgeChunk,
    KnowledgeDocument,
    RoutingRule,
    SentimentRecord,
    SupportTicket,
)
from .schemas import AIAnalysis, RouteDecision

logger = logging.getLogger(__name__)


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2]


def chunk_document(db: Session, doc: KnowledgeDocument) -> None:
    """Split *doc* into overlapping windows, persist to SQLite, and index in ChromaDB.

    ChromaDB indexing is best-effort: if the vector store is unavailable the
    function still commits the SQL chunks and marks the document as indexed so
    keyword retrieval continues to work.
    """
    db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).delete()
    words = doc.content.split()
    new_chunks: list[KnowledgeChunk] = []
    for idx in range(0, len(words), 85):
        text = " ".join(words[idx : idx + 110])
        chunk = KnowledgeChunk(
            document_id=doc.id,
            chunk_text=text,
            token_set=list(set(tokens(text))),
        )
        db.add(chunk)
        new_chunks.append(chunk)
    doc.status = "indexed"
    db.commit()

    # ── Vector indexing (best-effort) ──────────────────────────────────────────
    client = vector_store.get_client()
    if client is not None:
        try:
            client.add_chunks(doc.id, new_chunks)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ChromaDB indexing failed for document_id=%s — keyword fallback "
                "still available. (%s)",
                doc.id,
                exc,
            )


# ── Shared result builder ──────────────────────────────────────────────────────

def _build_semantic_results(
    db: Session, hits: list[dict]
) -> list[dict]:
    """Enrich raw ChromaDB hits with document titles from SQLite."""
    results = []
    retrieved_at = datetime.now(timezone.utc).isoformat()

    # Batch-load documents for the returned document_ids to avoid N+1 queries.
    doc_ids = list({h["document_id"] for h in hits if h.get("document_id")})
    docs_by_id: dict[str, KnowledgeDocument] = {}
    if doc_ids:
        for d in db.query(KnowledgeDocument).filter(KnowledgeDocument.id.in_(doc_ids)):
            docs_by_id[d.id] = d

    for hit in hits:
        doc = docs_by_id.get(hit.get("document_id", ""))
        results.append({
            "chunk_id": hit["chunk_id"],
            "provider": "chromadb",
            "similarity": hit["similarity"],
            "retrieved_at": retrieved_at,
            "title": doc.title if doc else "Unknown",
            "excerpt": hit["excerpt"],
        })
    return results


def _build_keyword_results(
    db: Session, query: str, limit: int
) -> list[dict]:
    """Existing TF-IDF keyword retriever, now returning the unified source schema."""
    q_tokens = tokens(query)
    if not q_tokens:
        return []

    chunks = db.query(KnowledgeChunk).all()
    doc_count = max(1, len(chunks))
    df = Counter(token for chunk in chunks for token in set(chunk.token_set))
    scored = []
    for chunk in chunks:
        overlap = set(q_tokens) & set(chunk.token_set)
        score = sum(math.log((doc_count + 1) / (df[t] + 1)) + 1 for t in overlap)
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)

    max_score = scored[0][0] if scored else 1.0
    retrieved_at = datetime.now(timezone.utc).isoformat()
    results = []
    for score, chunk in scored[:limit]:
        results.append({
            "chunk_id": chunk.id,
            "provider": "keyword",
            "similarity": round(float(score) / float(max_score), 4),
            "retrieved_at": retrieved_at,
            "title": chunk.document.title,
            "excerpt": chunk.chunk_text[:260],
            # Legacy field kept so existing audit-log readers still work.
            "score": round(float(score), 3),
        })
    return results


def search_knowledge(db: Session, query: str, limit: int = 4) -> list[dict]:
    """Retrieve knowledge chunks relevant to *query*.

    Strategy
    --------
    1. Attempt semantic retrieval via ChromaDB (``provider="chromadb"``).
    2. On any failure (client unavailable, empty index, exception): log a
       warning and fall back to the keyword/TF-IDF retriever
       (``provider="keyword"``).

    Both paths return the same schema so callers are provider-agnostic:
        chunk_id, provider, similarity, retrieved_at, title, excerpt
    """
    client = vector_store.get_client()
    if client is not None:
        try:
            hits = client.search(query, limit=limit)
            if hits:
                return _build_semantic_results(db, hits)
            # Fall through: empty index — keyword retriever may still find results.
            logger.debug("ChromaDB returned 0 hits for query=%r; using keyword fallback.", query)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Semantic retrieval failed — falling back to keyword retrieval. (%s)", exc
            )

    return _build_keyword_results(db, query, limit)


def run_ai_analysis(messages: list[dict[str, str]], sources: list[dict], customer_context: dict | None = None) -> tuple[AIAnalysis, str, str, str | None]:
    return asyncio.run(analyze_with_fallback(messages, sources, customer_context))


def analyze_text(db: Session, text: str, customer: Customer | None = None) -> AIAnalysis:
    sources = search_knowledge(db, text)
    messages = [{"role": "customer", "content": text}]
    customer_context = {
        "loyalty_tier": customer.loyalty_tier,
        "lifetime_value": customer.lifetime_value,
        "satisfaction_score": customer.satisfaction_score,
        "churn_risk_score": customer.churn_risk_score,
        "preferred_channel": customer.preferred_channel,
    } if customer else None
    analysis, _, _, _ = run_ai_analysis(messages, sources, customer_context)
    return analysis


def create_ai_suggestion(db: Session, conversation: Conversation) -> AISuggestion:
    customer = conversation.customer
    messages = [{"role": message.sender_type, "content": message.body} for message in conversation.messages[-8:]]
    text = "\n".join(message["content"] for message in messages)
    sources = search_knowledge(db, text)
    customer_context = {
        "loyalty_tier": customer.loyalty_tier,
        "lifetime_value": customer.lifetime_value,
        "satisfaction_score": customer.satisfaction_score,
        "churn_risk_score": customer.churn_risk_score,
        "preferred_channel": customer.preferred_channel,
    }
    analysis, provider_name, model_name, fallback_reason = run_ai_analysis(messages, sources, customer_context)
    suggestion = AISuggestion(
        conversation_id=conversation.id,
        provider=provider_name,
        model=model_name,
        **analysis.model_dump(exclude={"churn_risk_explanation"}),
    )
    conversation.sentiment = analysis.sentiment
    conversation.priority = "high" if analysis.urgency == "high" else conversation.priority
    db.add(suggestion)
    db.add(AuditLog(
        action="ai_suggestion_created",
        model_provider=provider_name,
        confidence=analysis.confidence,
        retrieved_sources=analysis.sources,
        human_decision="pending",
        explanation=f"{analysis.summary} {fallback_reason or ''}".strip(),
    ))
    db.commit()
    db.refresh(suggestion)
    return suggestion


def route_case(db: Session, conversation: Conversation, analysis: AIAnalysis) -> RouteDecision:
    rules = db.query(RoutingRule).all()
    customer = conversation.customer
    for rule in rules:
        checks = [
            rule.intent in (None, analysis.intent),
            rule.sentiment in (None, analysis.sentiment),
            rule.urgency in (None, analysis.urgency),
            rule.channel in (None, conversation.channel.name),
            rule.loyalty_tier in (None, customer.loyalty_tier),
            rule.churn_risk_min is None or customer.churn_risk_score >= rule.churn_risk_min,
        ]
        if all(checks):
            return RouteDecision(department=rule.department, explanation=f"Matched rule: {rule.name}", matched_rule=rule.name)
    return RouteDecision(department=analysis.recommended_department, explanation="Used AI recommended department.", matched_rule=None)


def analytics_summary(db: Session) -> dict:
    tickets = db.query(SupportTicket).all()
    conversations = db.query(Conversation).all()
    suggestions = db.query(AISuggestion).all()
    sentiments = db.query(SentimentRecord).all()
    total_tickets = max(1, len(tickets))
    accepted = len([s for s in suggestions if s.status == "approved"])
    by_channel = defaultdict(int)
    for ticket in tickets:
        by_channel[ticket.channel_name] += 1
    sentiment_map = {"positive": 1, "neutral": 0, "negative": -1}
    return {
        "active_conversations": len([c for c in conversations if c.status == "open"]),
        "open_tickets": len([t for t in tickets if t.status == "open"]),
        "avg_first_response_time": round(sum(t.first_response_minutes for t in tickets) / total_tickets, 1),
        "avg_resolution_time": round(sum(t.resolution_minutes for t in tickets) / total_tickets, 1),
        "customer_satisfaction": round((db.query(func.avg(Customer.satisfaction_score)).scalar() or 0), 1),
        "escalation_rate": round(100 * len([t for t in tickets if t.escalated]) / total_tickets, 1),
        "repeat_contact_rate": 37.5,
        "ai_acceptance_rate": round(100 * accepted / max(1, len(suggestions)), 1),
        "avg_sentiment_score": round(sum(sentiment_map.get(s.sentiment, 0) for s in sentiments) / max(1, len(sentiments)), 2),
        "sla_compliance": round(100 * len([c for c in conversations if not c.sla_risk]) / max(1, len(conversations)), 1),
        "channel_distribution": [{"name": k, "value": v} for k, v in by_channel.items()],
        "sentiment_trend": [{"name": f"Day {i+1}", "positive": 12+i, "neutral": 8, "negative": max(1, 6-i)} for i in range(7)],
        "ticket_volume": [{"name": f"Week {i+1}", "tickets": 18 + i * 3, "resolved": 14 + i * 2} for i in range(6)],
        "high_risk_customers": [
            {"id": c.id, "name": c.name, "risk": c.churn_risk_score, "tier": c.loyalty_tier}
            for c in db.query(Customer).order_by(Customer.churn_risk_score.desc()).limit(5)
        ],
        "recent_escalations": [
            {"id": t.id, "title": t.title, "department": t.department, "priority": t.priority}
            for t in db.query(SupportTicket).filter(SupportTicket.escalated.is_(True)).limit(5)
        ],
    }
