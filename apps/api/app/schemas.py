from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)


class InviteUserRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    role: str = Field(pattern="^(administrator|agent|customer)$")
    temporary_password: str = Field(min_length=8)


class MessageCreate(BaseModel):
    customer_id: str | None = None
    conversation_id: str | None = None
    channel: str = "web_chat"
    body: str = Field(min_length=1)
    sender_type: str = "customer"


class NormalizedMessage(BaseModel):
    external_id: str | None = None
    customer_identifier: str
    channel: str
    sender: str
    subject: str | None = None
    content: str
    timestamp: datetime
    metadata: dict = Field(default_factory=dict)


class KnowledgeCreate(BaseModel):
    title: str = Field(min_length=3)
    content: str = Field(min_length=10)


class SuggestionDecision(BaseModel):
    edited_response: str | None = None


class AIAnalysis(BaseModel):
    intent: str
    sentiment: str
    urgency: str
    summary: str
    recommended_department: str
    next_best_action: str
    churn_risk_explanation: str
    suggested_response: str
    confidence: float = Field(ge=0, le=1)
    sources: list[dict] = Field(default_factory=list)


class RouteDecision(BaseModel):
    department: str
    explanation: str
    matched_rule: str | None = None
