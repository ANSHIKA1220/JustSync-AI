import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def uuid_str() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(40), default="trial")
    status: Mapped[str] = mapped_column(String(40), default="active")


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(40))
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    loyalty_tier: Mapped[str] = mapped_column(String(40))
    preferred_channel: Mapped[str] = mapped_column(String(40))
    lifetime_value: Mapped[float] = mapped_column(Float)
    location: Mapped[str] = mapped_column(String(120))
    recent_purchases: Mapped[list] = mapped_column(JSON, default=list)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    satisfaction_score: Mapped[float] = mapped_column(Float)
    churn_risk_score: Mapped[float] = mapped_column(Float)
    profile: Mapped["CustomerProfile"] = relationship(back_populates="customer", uselist=False)


class CustomerProfile(Base, TimestampMixin):
    __tablename__ = "customer_profiles"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    churn_explanation: Mapped[str] = mapped_column(Text)
    customer: Mapped[Customer] = relationship(back_populates="profile")


class Channel(Base, TimestampMixin):
    __tablename__ = "channels"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    icon: Mapped[str] = mapped_column(String(40))


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    channel_id: Mapped[str] = mapped_column(ForeignKey("channels.id"))
    subject: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(40), default="open")
    priority: Mapped[str] = mapped_column(String(40), default="medium")
    sentiment: Mapped[str] = mapped_column(String(40), default="neutral")
    unread: Mapped[bool] = mapped_column(Boolean, default=False)
    sla_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    customer: Mapped[Customer] = relationship()
    channel: Mapped[Channel] = relationship()
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all,delete")


class Message(Base, TimestampMixin):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    sender_type: Mapped[str] = mapped_column(String(40))
    body: Mapped[str] = mapped_column(Text)
    channel_name: Mapped[str] = mapped_column(String(60))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class SupportTicket(Base, TimestampMixin):
    __tablename__ = "support_tickets"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    title: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(40), default="open")
    priority: Mapped[str] = mapped_column(String(40), default="medium")
    department: Mapped[str] = mapped_column(String(80), default="General Support")
    first_response_minutes: Mapped[int] = mapped_column(Integer, default=0)
    resolution_minutes: Mapped[int] = mapped_column(Integer, default=0)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    channel_name: Mapped[str] = mapped_column(String(60), default="web_chat")


class AgentAssignment(Base, TimestampMixin):
    __tablename__ = "agent_assignments"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    ticket_id: Mapped[str] = mapped_column(ForeignKey("support_tickets.id"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class KnowledgeDocument(Base, TimestampMixin):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="indexed")
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(back_populates="document", cascade="all,delete")


class KnowledgeChunk(Base, TimestampMixin):
    __tablename__ = "knowledge_chunks"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id"))
    chunk_text: Mapped[str] = mapped_column(Text)
    token_set: Mapped[list] = mapped_column(JSON, default=list)
    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")


class AISuggestion(Base, TimestampMixin):
    __tablename__ = "ai_suggestions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    provider: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    intent: Mapped[str] = mapped_column(String(80))
    sentiment: Mapped[str] = mapped_column(String(40))
    urgency: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(Text)
    suggested_response: Mapped[str] = mapped_column(Text)
    next_best_action: Mapped[str] = mapped_column(Text)
    recommended_department: Mapped[str] = mapped_column(String(80))
    confidence: Mapped[float] = mapped_column(Float)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    edited_response: Mapped[str | None] = mapped_column(Text, nullable=True)


class SentimentRecord(Base, TimestampMixin):
    __tablename__ = "sentiment_records"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    sentiment: Mapped[str] = mapped_column(String(40))
    score: Mapped[float] = mapped_column(Float)


class CustomerMetric(Base, TimestampMixin):
    __tablename__ = "customer_metrics"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    metric_name: Mapped[str] = mapped_column(String(80))
    metric_value: Mapped[float] = mapped_column(Float)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(120))
    model_provider: Mapped[str] = mapped_column(String(80), default="mock")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    retrieved_sources: Mapped[list] = mapped_column(JSON, default=list)
    human_decision: Mapped[str] = mapped_column(String(80), default="system")
    explanation: Mapped[str] = mapped_column(Text)


class RoutingRule(Base, TimestampMixin):
    __tablename__ = "routing_rules"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    intent: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sentiment: Mapped[str | None] = mapped_column(String(40), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(40), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(60), nullable=True)
    loyalty_tier: Mapped[str | None] = mapped_column(String(40), nullable=True)
    churn_risk_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    department: Mapped[str] = mapped_column(String(80))


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
