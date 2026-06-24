import asyncio
import math
import re
from collections import Counter, defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

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


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2]


def chunk_document(db: Session, doc: KnowledgeDocument) -> None:
    db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).delete()
    words = doc.content.split()
    for idx in range(0, len(words), 85):
        text = " ".join(words[idx : idx + 110])
        db.add(KnowledgeChunk(document_id=doc.id, chunk_text=text, token_set=list(set(tokens(text)))))
    doc.status = "indexed"
    db.commit()


def search_knowledge(db: Session, query: str, organization_id: str | None = None, limit: int = 4) -> list[dict]:
    q_tokens = tokens(query)
    if not q_tokens:
        return []
    chunks_query = db.query(KnowledgeChunk).join(KnowledgeDocument)
    if organization_id:
        chunks_query = chunks_query.filter(KnowledgeDocument.organization_id == organization_id)
    chunks = chunks_query.all()
    doc_count = max(1, len(chunks))
    df = Counter(token for chunk in chunks for token in set(chunk.token_set))
    scored = []
    for chunk in chunks:
        overlap = set(q_tokens) & set(chunk.token_set)
        score = sum(math.log((doc_count + 1) / (df[t] + 1)) + 1 for t in overlap)
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)
    results = []
    for score, chunk in scored[:limit]:
        results.append({
            "title": chunk.document.title,
            "source_id": chunk.document.id,
            "chunk_id": chunk.id,
            "score": round(float(score), 3),
            "snippet": chunk.chunk_text[:260],
            "excerpt": chunk.chunk_text[:260],
        })
    return results


def run_ai_analysis(messages: list[dict[str, str]], sources: list[dict], customer_context: dict | None = None) -> tuple[AIAnalysis, str, str, str | None]:
    return asyncio.run(analyze_with_fallback(messages, sources, customer_context))


def analyze_text(db: Session, text: str, customer: Customer | None = None) -> AIAnalysis:
    sources = search_knowledge(db, text, customer.organization_id if customer else None)
    messages = [{"role": "customer", "content": text}]
    customer_context = {
        "loyalty_tier": customer.loyalty_tier,
        "lifetime_value": customer.lifetime_value,
        "satisfaction_score": customer.satisfaction_score,
        "churn_risk_score": customer.churn_risk_score,
        "preferred_channel": customer.preferred_channel,
        "history_summary": f"{customer.name} is a {customer.loyalty_tier} customer with preferred channel {customer.preferred_channel}.",
    } if customer else None
    analysis, _, _, _ = run_ai_analysis(messages, sources, customer_context)
    return analysis


def assemble_ai_context(db: Session, conversation: Conversation) -> tuple[list[dict[str, str]], list[dict], dict]:
    customer = conversation.customer
    customer_conversations = (
        db.query(Conversation)
        .filter(Conversation.organization_id == conversation.organization_id, Conversation.customer_id == customer.id)
        .order_by(Conversation.created_at.asc())
        .all()
    )
    messages: list[dict[str, str]] = []
    timeline_parts: list[str] = []
    for item in customer_conversations:
        for message in item.messages:
            role = message.sender_type
            content = f"[{message.channel_name}] {item.subject}: {message.body}"
            timeline_parts.append(content)
            if item.id == conversation.id:
                messages.append({"role": role, "content": content})
    if not messages:
        messages = [{"role": message.sender_type, "content": message.body} for message in conversation.messages[-8:]]
    ticket = db.query(SupportTicket).filter(
        SupportTicket.organization_id == conversation.organization_id,
        SupportTicket.conversation_id == conversation.id,
    ).first()
    query_text = "\n".join(timeline_parts[-18:] or [message["content"] for message in messages])
    sources = search_knowledge(db, query_text, conversation.organization_id)
    customer_context = {
        "customer_name": customer.name,
        "loyalty_tier": customer.loyalty_tier,
        "lifetime_value": customer.lifetime_value,
        "satisfaction_score": customer.satisfaction_score,
        "churn_risk_score": customer.churn_risk_score,
        "preferred_channel": customer.preferred_channel,
        "recent_purchases": customer.recent_purchases,
        "tags": customer.tags,
        "conversation_count": len(customer_conversations),
        "ticket_status": ticket.status if ticket else "unknown",
        "ticket_priority": ticket.priority if ticket else conversation.priority,
        "assigned_department": ticket.department if ticket else "unassigned",
        "history_summary": f"{customer.name} has {len(customer_conversations)} tenant-scoped conversations across {', '.join(sorted({c.channel.name for c in customer_conversations}))}.",
    }
    return messages, sources, customer_context


def create_ai_suggestion(db: Session, conversation: Conversation) -> AISuggestion:
    messages, sources, customer_context = assemble_ai_context(db, conversation)
    analysis, provider_name, model_name, fallback_reason = run_ai_analysis(messages, sources, customer_context)
    analysis.fallback_active = provider_name == "mock" and fallback_reason is not None
    analysis.fallback_reason = fallback_reason
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
        organization_id=conversation.organization_id,
        action="ai_suggestion_created",
        model_provider=provider_name,
        confidence=analysis.confidence,
        retrieved_sources=analysis.sources,
        human_decision="pending",
        explanation=f"AI classified {analysis.intent}, {analysis.sentiment} sentiment, {analysis.urgency} urgency. {analysis.routing_reason} {fallback_reason or ''}".strip(),
    ))
    for source in analysis.sources:
        db.add(AuditLog(
            organization_id=conversation.organization_id,
            action="knowledge_source_referenced",
            model_provider=provider_name,
            confidence=analysis.confidence,
            retrieved_sources=[source],
            human_decision="system",
            explanation=f"Knowledge source '{source.get('title', 'Untitled')}' was used for this recommendation.",
        ))
    db.commit()
    db.refresh(suggestion)
    return suggestion


def route_case(db: Session, conversation: Conversation, analysis: AIAnalysis) -> RouteDecision:
    rules = db.query(RoutingRule).filter(RoutingRule.organization_id == conversation.organization_id).all()
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


def analytics_summary(db: Session, organization_id: str | None = None) -> dict:
    tickets_query = db.query(SupportTicket)
    conversations_query = db.query(Conversation)
    sentiments_query = db.query(SentimentRecord).join(Customer, Customer.id == SentimentRecord.customer_id)
    customers_query = db.query(Customer)
    if organization_id:
        tickets_query = tickets_query.filter(SupportTicket.organization_id == organization_id)
        conversations_query = conversations_query.filter(Conversation.organization_id == organization_id)
        sentiments_query = sentiments_query.filter(Customer.organization_id == organization_id)
        customers_query = customers_query.filter(Customer.organization_id == organization_id)
    tickets = tickets_query.all()
    conversations = conversations_query.all()
    suggestions = db.query(AISuggestion).join(Conversation, Conversation.id == AISuggestion.conversation_id)
    if organization_id:
        suggestions = suggestions.filter(Conversation.organization_id == organization_id)
    suggestions = suggestions.all()
    sentiments = sentiments_query.all()
    total_tickets = max(1, len(tickets))
    accepted = len([s for s in suggestions if s.status == "approved"])
    by_channel = defaultdict(int)
    by_status = defaultdict(int)
    by_customer = defaultdict(int)
    for ticket in tickets:
        by_channel[ticket.channel_name] += 1
        by_status[ticket.status] += 1
        by_customer[ticket.customer_id] += 1
    sentiment_map = {"positive": 1, "neutral": 0, "frustrated": -0.6, "angry": -0.9, "urgent": -0.8, "negative": -1}
    repeat_customers = len([customer_id for customer_id, count in by_customer.items() if count > 1])
    customer_count = max(1, len(by_customer))
    return {
        "active_conversations": len([c for c in conversations if c.status == "open"]),
        "open_tickets": len([t for t in tickets if t.status == "open"]),
        "avg_first_response_time": round(sum(t.first_response_minutes for t in tickets) / total_tickets, 1),
        "avg_resolution_time": round(sum(t.resolution_minutes for t in tickets) / total_tickets, 1),
        "customer_satisfaction": round((customers_query.with_entities(func.avg(Customer.satisfaction_score)).scalar() or 0), 1),
        "escalation_rate": round(100 * len([t for t in tickets if t.escalated]) / total_tickets, 1),
        "repeat_contact_rate": round(100 * repeat_customers / customer_count, 1),
        "ai_acceptance_rate": round(100 * accepted / max(1, len(suggestions)), 1),
        "avg_sentiment_score": round(sum(sentiment_map.get(s.sentiment, 0) for s in sentiments) / max(1, len(sentiments)), 2),
        "sla_compliance": round(100 * len([c for c in conversations if not c.sla_risk]) / max(1, len(conversations)), 1),
        "channel_distribution": [{"name": k, "value": v} for k, v in by_channel.items()],
        "ticket_status_distribution": [{"name": k, "value": v} for k, v in by_status.items()],
        "sentiment_trend": [{"name": f"Day {i+1}", "positive": 12+i, "neutral": 8, "negative": max(1, 6-i)} for i in range(7)],
        "ticket_volume": [{"name": f"Week {i+1}", "tickets": 18 + i * 3, "resolved": 14 + i * 2} for i in range(6)],
        "high_risk_customers": [
            {"id": c.id, "name": c.name, "risk": c.churn_risk_score, "tier": c.loyalty_tier}
            for c in customers_query.order_by(Customer.churn_risk_score.desc()).limit(5)
        ],
        "recent_escalations": [
            {"id": t.id, "title": t.title, "department": t.department, "priority": t.priority}
            for t in tickets_query.filter(SupportTicket.escalated.is_(True)).limit(5)
        ],
    }
