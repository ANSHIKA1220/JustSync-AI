from datetime import datetime
from time import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .adapters import ADAPTERS
from .ai_providers import get_provider_status
from .auth import create_access_token, current_user, require_roles, verify_password
from .config import settings
from .database import Base, engine, get_db
from .models import (
    AISuggestion,
    AuditLog,
    Channel,
    Conversation,
    Customer,
    KnowledgeDocument,
    Message,
    RoutingRule,
    SupportTicket,
    User,
)
from .schemas import KnowledgeCreate, LoginRequest, MessageCreate, SuggestionDecision
from .seed import seed_database
from .services import analytics_summary, analyze_text, chunk_document, create_ai_suggestion, route_case, search_knowledge

Base.metadata.create_all(bind=engine)
app = FastAPI(title="JourneySync AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3100",
        "http://127.0.0.1:3100",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
rate_buckets: dict[str, list[float]] = {}


def serialize(obj):
    data = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    return data


def ai_rate_limit(request: Request):
    key = request.client.host if request.client else "local"
    now = time()
    bucket = [t for t in rate_buckets.get(key, []) if now - t < 60]
    if len(bucket) > 30:
        raise HTTPException(status_code=429, detail="AI rate limit exceeded")
    bucket.append(now)
    rate_buckets[key] = bucket


@app.get("/health")
def health():
    return {"status": "healthy", **get_provider_status()}


@app.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": serialize(user)}


@app.get("/auth/me")
def me(user: User = Depends(current_user)):
    return serialize(user)


@app.get("/users")
def users(db: Session = Depends(get_db), _: User = Depends(require_roles("administrator"))):
    return [serialize(u) for u in db.query(User).all()]


@app.get("/customers")
def customers(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [serialize(c) for c in db.query(Customer).all()]


@app.get("/customers/{customer_id}")
def customer_detail(customer_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    data = serialize(customer)
    data["profile"] = serialize(customer.profile) if customer.profile else None
    return data


@app.get("/customers/{customer_id}/timeline")
def customer_timeline(customer_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    conversations = db.query(Conversation).filter(Conversation.customer_id == customer_id).all()
    events = []
    for conv in conversations:
        for msg in conv.messages:
            item = serialize(msg)
            item["subject"] = conv.subject
            item["sentiment"] = conv.sentiment
            events.append(item)
    events.sort(key=lambda e: e["created_at"])
    return {"customer": serialize(customer), "events": events}


@app.get("/conversations")
def conversations(
    q: str = "",
    channel: str = "",
    sentiment: str = "",
    priority: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
):
    rows = db.query(Conversation).all()
    data = []
    for conv in rows:
        if q and q.lower() not in (conv.subject + conv.customer.name + conv.customer.email).lower():
            continue
        if channel and conv.channel.name != channel:
            continue
        if sentiment and conv.sentiment != sentiment:
            continue
        if priority and conv.priority != priority:
            continue
        item = serialize(conv)
        item["customer"] = serialize(conv.customer)
        item["channel"] = serialize(conv.channel)
        item["latest_message"] = conv.messages[-1].body if conv.messages else ""
        data.append(item)
    return sorted(data, key=lambda x: x["updated_at"], reverse=True)


@app.get("/conversations/{conversation_id}")
def conversation_detail(conversation_id: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    data = serialize(conv)
    data["customer"] = serialize(conv.customer)
    data["profile"] = serialize(conv.customer.profile) if conv.customer.profile else None
    data["channel"] = serialize(conv.channel)
    data["messages"] = [serialize(m) for m in conv.messages]
    suggestion = db.query(AISuggestion).filter(AISuggestion.conversation_id == conv.id).order_by(AISuggestion.created_at.desc()).first()
    data["ai_suggestion"] = serialize(suggestion) if suggestion else serialize(create_ai_suggestion(db, conv))
    return data


@app.post("/messages")
def create_message(payload: MessageCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    adapter = ADAPTERS.get(payload.channel, ADAPTERS["web_chat"])
    normalized = adapter.receive_message(payload.model_dump())
    conv = db.get(Conversation, payload.conversation_id) if payload.conversation_id else None
    if not conv:
        if not payload.customer_id:
            raise HTTPException(status_code=400, detail="customer_id or conversation_id is required")
        channel = db.query(Channel).filter(Channel.name == normalized.channel).first()
        conv = Conversation(customer_id=payload.customer_id, channel_id=channel.id, subject="New simulated interaction", unread=True)
        db.add(conv)
        db.flush()
    msg = Message(
        conversation_id=conv.id,
        sender_type=normalized.sender_type,
        body=normalized.body,
        channel_name=normalized.channel,
        metadata_json=normalized.metadata,
    )
    conv.unread = normalized.sender_type == "customer"
    conv.updated_at = datetime.utcnow()
    db.add(msg)
    analysis = analyze_text(db, normalized.body, conv.customer)
    conv.sentiment = analysis.sentiment
    conv.priority = "high" if analysis.urgency == "high" else conv.priority
    db.add(AuditLog(user_id=user.id, action="message_created", explanation=f"Normalized {normalized.channel} message."))
    db.commit()
    return {"conversation_id": conv.id, "message": serialize(msg), "analysis": analysis.model_dump()}


@app.post("/tickets/{ticket_id}/resolve")
def resolve_ticket(ticket_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator", "agent"))):
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.status = "resolved"
    db.add(AuditLog(user_id=user.id, action="ticket_resolved", explanation=ticket.title))
    db.commit()
    return serialize(ticket)


@app.post("/tickets/{ticket_id}/escalate")
def escalate_ticket(ticket_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator", "agent"))):
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.escalated = True
    ticket.priority = "high"
    db.add(AuditLog(user_id=user.id, action="ticket_escalated", explanation=ticket.title, human_decision="escalated"))
    db.commit()
    return serialize(ticket)


@app.get("/analytics/summary")
def analytics(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return analytics_summary(db)


@app.get("/knowledge")
def knowledge(db: Session = Depends(get_db), _: User = Depends(current_user)):
    docs = []
    for doc in db.query(KnowledgeDocument).all():
        item = serialize(doc)
        item["chunk_count"] = len(doc.chunks)
        docs.append(item)
    return docs


@app.post("/knowledge")
def add_knowledge(payload: KnowledgeCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("administrator"))):
    doc = KnowledgeDocument(title=payload.title, content=payload.content, status="pending")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    chunk_document(db, doc)
    return serialize(doc)


@app.put("/knowledge/{doc_id}")
def update_knowledge(doc_id: str, payload: KnowledgeCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("administrator"))):
    doc = db.get(KnowledgeDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.title = payload.title
    doc.content = payload.content
    chunk_document(db, doc)
    return serialize(doc)


@app.delete("/knowledge/{doc_id}")
def delete_knowledge(doc_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles("administrator"))):
    doc = db.get(KnowledgeDocument, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()
    return {"ok": True}


@app.get("/knowledge/search")
def knowledge_search(q: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    return search_knowledge(db, q)


@app.post("/knowledge/reindex")
def reindex(db: Session = Depends(get_db), _: User = Depends(require_roles("administrator"))):
    for doc in db.query(KnowledgeDocument).all():
        chunk_document(db, doc)
    return {"ok": True}


@app.post("/ai/analyze", dependencies=[Depends(ai_rate_limit)])
def ai_analyze(payload: MessageCreate, db: Session = Depends(get_db), _: User = Depends(current_user)):
    customer = db.get(Customer, payload.customer_id) if payload.customer_id else None
    return analyze_text(db, payload.body, customer).model_dump()


@app.post("/ai/conversations/{conversation_id}/suggest", dependencies=[Depends(ai_rate_limit)])
def ai_suggest(conversation_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles("administrator", "agent"))):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return serialize(create_ai_suggestion(db, conv))


@app.post("/ai/suggestions/{suggestion_id}/approve")
def approve_suggestion(suggestion_id: str, payload: SuggestionDecision, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator", "agent"))):
    suggestion = db.get(AISuggestion, suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    suggestion.status = "approved"
    suggestion.edited_response = payload.edited_response or suggestion.suggested_response
    db.add(Message(conversation_id=suggestion.conversation_id, sender_type="agent", body=suggestion.edited_response, channel_name="agent_console"))
    db.add(AuditLog(
        user_id=user.id,
        action="ai_suggestion_approved",
        model_provider=suggestion.provider,
        confidence=suggestion.confidence,
        retrieved_sources=suggestion.sources,
        human_decision="approved_edited" if payload.edited_response else "approved",
        explanation=suggestion.next_best_action,
    ))
    db.commit()
    return serialize(suggestion)


@app.post("/ai/suggestions/{suggestion_id}/reject")
def reject_suggestion(suggestion_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator", "agent"))):
    suggestion = db.get(AISuggestion, suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    suggestion.status = "rejected"
    db.add(AuditLog(user_id=user.id, action="ai_suggestion_rejected", model_provider=suggestion.provider, confidence=suggestion.confidence, human_decision="rejected", explanation="Agent rejected AI suggestion."))
    db.commit()
    return serialize(suggestion)


@app.get("/routing/rules")
def routing_rules(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [serialize(r) for r in db.query(RoutingRule).all()]


@app.post("/routing/rules")
def create_rule(rule: dict, db: Session = Depends(get_db), _: User = Depends(require_roles("administrator"))):
    obj = RoutingRule(**rule)
    db.add(obj)
    db.commit()
    return serialize(obj)


@app.post("/routing/decide/{conversation_id}")
def routing_decide(conversation_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator", "agent"))):
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    analysis = analyze_text(db, "\n".join(m.body for m in conv.messages), conv.customer)
    decision = route_case(db, conv, analysis)
    db.add(AuditLog(user_id=user.id, action="routing_decision", explanation=decision.explanation, confidence=analysis.confidence))
    db.commit()
    return decision.model_dump()


@app.get("/audit")
def audit(db: Session = Depends(get_db), _: User = Depends(require_roles("administrator", "agent"))):
    return [serialize(a) for a in db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100)]


@app.post("/demo/reset")
def reset_demo(db: Session = Depends(get_db), _: User = Depends(require_roles("administrator"))):
    seed_database(reset=True)
    return {"ok": True}


@app.post("/demo/run-scenario")
def run_scenario(db: Session = Depends(get_db), user: User = Depends(require_roles("administrator", "agent"))):
    customer = db.query(Customer).filter(Customer.email == "priya.shah@example.com").first()
    channel = db.query(Channel).filter(Channel.name == "email").first()
    conv = Conversation(customer_id=customer.id, channel_id=channel.id, subject="Damaged product after delayed delivery", priority="high", sentiment="negative", unread=True, sla_risk=True)
    db.add(conv)
    db.flush()
    db.add(Message(conversation_id=conv.id, sender_type="customer", body="My delayed order finally arrived today, but the espresso machine is damaged. I am really upset and need an urgent replacement.", channel_name="email"))
    ticket = SupportTicket(conversation_id=conv.id, customer_id=customer.id, title=conv.subject, priority="high", department="Logistics and Returns", escalated=True, channel_name="email", first_response_minutes=6, resolution_minutes=0)
    db.add(ticket)
    db.commit()
    suggestion = create_ai_suggestion(db, conv)
    db.add(AuditLog(user_id=user.id, action="guided_demo_scenario", model_provider=settings.ai_provider, confidence=suggestion.confidence, retrieved_sources=suggestion.sources, explanation="Created damaged-product escalation scenario."))
    db.commit()
    return {"conversation_id": conv.id, "suggestion_id": suggestion.id}
