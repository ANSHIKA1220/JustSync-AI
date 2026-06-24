import re
from datetime import datetime
from time import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .adapters import ADAPTERS
from .ai_providers import get_provider_status
from .auth import create_access_token, current_user, hash_password, require_roles, verify_password
from .config import settings
from .database import get_db
from .models import (
    AISuggestion,
    AuditLog,
    Channel,
    Conversation,
    Customer,
    KnowledgeDocument,
    Message,
    Organization,
    RoutingRule,
    SupportTicket,
    User,
    Workspace,
)
from .schemas import InviteUserRequest, KnowledgeCreate, LoginRequest, MessageCreate, SignupRequest, SuggestionDecision, TicketAssignment
from .seed import ensure_channels, seed_database
from .services import analytics_summary, analyze_text, chunk_document, create_ai_suggestion, route_case, search_knowledge

app = FastAPI(title="JourneySync AI API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
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


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "workspace"


def tenant_conversation(db: Session, conversation_id: str, user: User) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if not conv or conv.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


def tenant_ticket(db: Session, ticket_id: str, user: User) -> SupportTicket:
    ticket = db.get(SupportTicket, ticket_id)
    if not ticket or ticket.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def ticket_for_conversation(db: Session, conversation_id: str, user: User) -> SupportTicket:
    tenant_conversation(db, conversation_id, user)
    ticket = db.query(SupportTicket).filter(
        SupportTicket.conversation_id == conversation_id,
        SupportTicket.organization_id == user.organization_id,
    ).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


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


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is not ready") from exc
    return {"status": "ready"}


@app.post("/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": serialize(user)}


@app.post("/auth/signup")
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email is already registered")
    base_slug = slugify(payload.organization_name)
    slug = base_slug
    suffix = 2
    while db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    org = Organization(name=payload.organization_name, slug=slug, plan="trial")
    db.add(org)
    db.flush()
    db.add(Workspace(organization_id=org.id, name="Customer Operations", slug="customer-operations", is_default=True))
    ensure_channels(db)
    user = User(
        organization_id=org.id,
        email=payload.email,
        name=payload.name,
        role="administrator",
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.flush()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Could not create organization") from exc
    return {"access_token": create_access_token(user), "token_type": "bearer", "user": serialize(user), "organization": serialize(org)}


@app.get("/auth/me")
def me(user: User = Depends(current_user)):
    return serialize(user)


@app.get("/organization")
def organization(db: Session = Depends(get_db), user: User = Depends(current_user)):
    org = db.get(Organization, user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    data = serialize(org)
    data["workspaces"] = [serialize(w) for w in db.query(Workspace).filter(Workspace.organization_id == org.id).all()]
    return data


@app.get("/users")
def users(db: Session = Depends(get_db), user: User = Depends(require_roles("administrator"))):
    return [serialize(u) for u in db.query(User).filter(User.organization_id == user.organization_id).all()]


@app.post("/users/invite")
def invite_user(payload: InviteUserRequest, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator"))):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email is already registered")
    invited = User(
        organization_id=user.organization_id,
        email=payload.email,
        name=payload.name,
        role=payload.role,
        hashed_password=hash_password(payload.temporary_password),
    )
    db.add(invited)
    db.add(AuditLog(organization_id=user.organization_id, user_id=user.id, action="user_invited", explanation=f"Invited {payload.email} as {payload.role}."))
    db.commit()
    db.refresh(invited)
    return serialize(invited)


@app.get("/customers")
def customers(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [serialize(c) for c in db.query(Customer).filter(Customer.organization_id == user.organization_id).all()]


@app.get("/customers/{customer_id}")
def customer_detail(customer_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    customer = db.get(Customer, customer_id)
    if not customer or customer.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Customer not found")
    data = serialize(customer)
    data["profile"] = serialize(customer.profile) if customer.profile else None
    return data


@app.get("/customers/{customer_id}/timeline")
def customer_timeline(customer_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    customer = db.get(Customer, customer_id)
    if not customer or customer.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Customer not found")
    conversations = db.query(Conversation).filter(Conversation.customer_id == customer_id, Conversation.organization_id == user.organization_id).all()
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
    user: User = Depends(current_user),
):
    rows = db.query(Conversation).filter(Conversation.organization_id == user.organization_id).all()
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
def conversation_detail(conversation_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    conv = tenant_conversation(db, conversation_id, user)
    data = serialize(conv)
    data["customer"] = serialize(conv.customer)
    data["profile"] = serialize(conv.customer.profile) if conv.customer.profile else None
    data["channel"] = serialize(conv.channel)
    data["messages"] = [serialize(m) for m in conv.messages]
    suggestion = db.query(AISuggestion).filter(AISuggestion.conversation_id == conv.id).order_by(AISuggestion.created_at.desc()).first()
    data["ai_suggestion"] = serialize(suggestion) if suggestion else serialize(create_ai_suggestion(db, conv))
    return data


@app.get("/conversations/{conversation_id}/timeline")
def conversation_customer_timeline(conversation_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    conv = tenant_conversation(db, conversation_id, user)
    return customer_timeline(conv.customer_id, db, user)


@app.get("/conversations/{conversation_id}/ticket")
def conversation_ticket(conversation_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return serialize(ticket_for_conversation(db, conversation_id, user))


@app.post("/messages")
def create_message(payload: MessageCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    adapter = ADAPTERS.get(payload.channel, ADAPTERS["web_chat"])
    normalized = adapter.receive_message(payload.model_dump())
    conv = tenant_conversation(db, payload.conversation_id, user) if payload.conversation_id else None
    if not conv:
        if not payload.customer_id:
            raise HTTPException(status_code=400, detail="customer_id or conversation_id is required")
        customer = db.get(Customer, payload.customer_id)
        if not customer or customer.organization_id != user.organization_id:
            raise HTTPException(status_code=404, detail="Customer not found")
        channel = db.query(Channel).filter(Channel.name == normalized.channel).first()
        conv = Conversation(organization_id=user.organization_id, customer_id=payload.customer_id, channel_id=channel.id, subject="New simulated interaction", unread=True)
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
    db.add(AuditLog(organization_id=user.organization_id, user_id=user.id, action="message_created", explanation=f"Normalized {normalized.channel} message."))
    db.commit()
    return {"conversation_id": conv.id, "message": serialize(msg), "analysis": analysis.model_dump()}


@app.post("/tickets/{ticket_id}/resolve")
def resolve_ticket(ticket_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator", "agent"))):
    ticket = tenant_ticket(db, ticket_id, user)
    ticket.status = "resolved"
    db.add(AuditLog(organization_id=user.organization_id, user_id=user.id, action="ticket_resolved", human_decision="resolved", explanation=ticket.title))
    db.commit()
    return serialize(ticket)


@app.post("/tickets/{ticket_id}/escalate")
def escalate_ticket(ticket_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator", "agent"))):
    ticket = tenant_ticket(db, ticket_id, user)
    ticket.escalated = True
    ticket.priority = "high"
    db.add(AuditLog(organization_id=user.organization_id, user_id=user.id, action="ticket_escalated", explanation=ticket.title, human_decision="escalated"))
    db.commit()
    return serialize(ticket)


@app.post("/tickets/{ticket_id}/priority-high")
def mark_ticket_high_priority(ticket_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator", "agent"))):
    ticket = tenant_ticket(db, ticket_id, user)
    ticket.priority = "high"
    db.add(AuditLog(organization_id=user.organization_id, user_id=user.id, action="ticket_priority_marked_high", human_decision="priority_changed", explanation=f"{ticket.title} marked high priority."))
    db.commit()
    return serialize(ticket)


@app.post("/tickets/{ticket_id}/reopen")
def reopen_ticket(ticket_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator", "agent"))):
    ticket = tenant_ticket(db, ticket_id, user)
    ticket.status = "open"
    db.add(AuditLog(organization_id=user.organization_id, user_id=user.id, action="ticket_reopened", human_decision="reopened", explanation=f"{ticket.title} reopened for additional review."))
    db.commit()
    return serialize(ticket)


@app.post("/tickets/{ticket_id}/assign-team")
def assign_ticket_team(ticket_id: str, payload: TicketAssignment, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator", "agent"))):
    ticket = tenant_ticket(db, ticket_id, user)
    ticket.department = payload.department
    db.add(AuditLog(
        organization_id=user.organization_id,
        user_id=user.id,
        action="ticket_team_assigned",
        human_decision="assigned",
        explanation=f"{ticket.title} assigned to {payload.department}.",
    ))
    db.commit()
    return serialize(ticket)


@app.get("/analytics/summary")
def analytics(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return analytics_summary(db, user.organization_id)


@app.get("/knowledge")
def knowledge(db: Session = Depends(get_db), user: User = Depends(current_user)):
    docs = []
    for doc in db.query(KnowledgeDocument).filter(KnowledgeDocument.organization_id == user.organization_id).all():
        item = serialize(doc)
        item["chunk_count"] = len(doc.chunks)
        docs.append(item)
    return docs


@app.post("/knowledge")
def add_knowledge(payload: KnowledgeCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator"))):
    doc = KnowledgeDocument(organization_id=user.organization_id, title=payload.title, content=payload.content, status="pending")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    chunk_document(db, doc)
    return serialize(doc)


@app.put("/knowledge/{doc_id}")
def update_knowledge(doc_id: str, payload: KnowledgeCreate, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator"))):
    doc = db.get(KnowledgeDocument, doc_id)
    if not doc or doc.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.title = payload.title
    doc.content = payload.content
    chunk_document(db, doc)
    return serialize(doc)


@app.delete("/knowledge/{doc_id}")
def delete_knowledge(doc_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator"))):
    doc = db.get(KnowledgeDocument, doc_id)
    if not doc or doc.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)
    db.commit()
    return {"ok": True}


@app.get("/knowledge/search")
def knowledge_search(q: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return search_knowledge(db, q, user.organization_id)


@app.post("/knowledge/reindex")
def reindex(db: Session = Depends(get_db), user: User = Depends(require_roles("administrator"))):
    for doc in db.query(KnowledgeDocument).filter(KnowledgeDocument.organization_id == user.organization_id).all():
        chunk_document(db, doc)
    return {"ok": True}


@app.post("/ai/analyze", dependencies=[Depends(ai_rate_limit)])
def ai_analyze(payload: MessageCreate, db: Session = Depends(get_db), _: User = Depends(current_user)):
    customer = db.get(Customer, payload.customer_id) if payload.customer_id else None
    return analyze_text(db, payload.body, customer).model_dump()


@app.post("/ai/conversations/{conversation_id}/suggest", dependencies=[Depends(ai_rate_limit)])
def ai_suggest(conversation_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles("administrator", "agent"))):
    conv = tenant_conversation(db, conversation_id, _)
    return serialize(create_ai_suggestion(db, conv))


@app.post("/ai/suggestions/{suggestion_id}/approve")
def approve_suggestion(suggestion_id: str, payload: SuggestionDecision, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator", "agent"))):
    suggestion = db.get(AISuggestion, suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    tenant_conversation(db, suggestion.conversation_id, user)
    suggestion.status = "approved"
    suggestion.edited_response = payload.edited_response or suggestion.suggested_response
    db.add(Message(conversation_id=suggestion.conversation_id, sender_type="agent", body=suggestion.edited_response, channel_name="agent_console"))
    db.add(AuditLog(
        organization_id=user.organization_id,
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
    tenant_conversation(db, suggestion.conversation_id, user)
    suggestion.status = "rejected"
    db.add(AuditLog(organization_id=user.organization_id, user_id=user.id, action="ai_suggestion_rejected", model_provider=suggestion.provider, confidence=suggestion.confidence, human_decision="rejected", explanation="Agent rejected AI suggestion."))
    db.commit()
    return serialize(suggestion)


@app.get("/routing/rules")
def routing_rules(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return [serialize(r) for r in db.query(RoutingRule).filter(RoutingRule.organization_id == user.organization_id).all()]


@app.post("/routing/rules")
def create_rule(rule: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator"))):
    obj = RoutingRule(**rule, organization_id=user.organization_id)
    db.add(obj)
    db.commit()
    return serialize(obj)


@app.post("/routing/decide/{conversation_id}")
def routing_decide(conversation_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles("administrator", "agent"))):
    conv = tenant_conversation(db, conversation_id, user)
    analysis = analyze_text(db, "\n".join(m.body for m in conv.messages), conv.customer)
    decision = route_case(db, conv, analysis)
    db.add(AuditLog(organization_id=user.organization_id, user_id=user.id, action="routing_decision", explanation=decision.explanation, confidence=analysis.confidence))
    db.commit()
    return decision.model_dump()


@app.get("/audit")
def audit(db: Session = Depends(get_db), user: User = Depends(require_roles("administrator", "agent"))):
    return [serialize(a) for a in db.query(AuditLog).filter(AuditLog.organization_id == user.organization_id).order_by(AuditLog.created_at.desc()).limit(100)]


@app.post("/demo/reset")
def reset_demo(db: Session = Depends(get_db), _: User = Depends(require_roles("administrator"))):
    seed_database(reset=True)
    return {"ok": True}


@app.post("/demo/load-sample-data")
def load_sample_data(db: Session = Depends(get_db), user: User = Depends(require_roles("administrator"))):
    org = db.get(Organization, user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    from .seed import seed_curated_demo_data

    before = db.query(Customer).filter(Customer.organization_id == org.id).count()
    seed_curated_demo_data(db, org, [user], email_suffix=org.slug)
    db.add(AuditLog(
        organization_id=org.id,
        user_id=user.id,
        action="demo_sample_data_loaded",
        human_decision="approved",
        explanation="Loaded fictional, tenant-scoped JourneySync sample data for the current organization.",
    ))
    db.commit()
    after = db.query(Customer).filter(Customer.organization_id == org.id).count()
    return {"ok": True, "created": max(0, after - before), "organization_id": org.id}


@app.post("/demo/run-scenario")
def run_scenario(db: Session = Depends(get_db), user: User = Depends(require_roles("administrator", "agent"))):
    customer = db.query(Customer).filter(
        Customer.organization_id == user.organization_id,
        Customer.email.like("ari.vale%"),
    ).first()
    if not customer:
        org = db.get(Organization, user.organization_id)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        from .seed import seed_curated_demo_data

        seed_curated_demo_data(db, org, [user], email_suffix=org.slug)
        db.commit()
        customer = db.query(Customer).filter(
            Customer.organization_id == user.organization_id,
            Customer.email.like("ari.vale%"),
        ).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Demo customer not found")
    channel = db.query(Channel).filter(Channel.name == "email").first()
    conv = Conversation(organization_id=user.organization_id, customer_id=customer.id, channel_id=channel.id, subject="Damaged product after delayed delivery", priority="high", sentiment="negative", unread=True, sla_risk=True)
    db.add(conv)
    db.flush()
    db.add(Message(conversation_id=conv.id, sender_type="customer", body="My delayed order finally arrived today, but the espresso machine is damaged. I am really upset and need an urgent replacement.", channel_name="email"))
    ticket = SupportTicket(organization_id=user.organization_id, conversation_id=conv.id, customer_id=customer.id, title=conv.subject, priority="high", department="Escalations", escalated=True, channel_name="email", first_response_minutes=6, resolution_minutes=0)
    db.add(ticket)
    db.commit()
    suggestion = create_ai_suggestion(db, conv)
    db.add(AuditLog(organization_id=user.organization_id, user_id=user.id, action="guided_demo_scenario", model_provider=settings.ai_provider, confidence=suggestion.confidence, retrieved_sources=suggestion.sources, explanation="Created damaged-product escalation scenario."))
    db.commit()
    return {"conversation_id": conv.id, "suggestion_id": suggestion.id}
