import argparse
import secrets
from datetime import datetime, timedelta

from .auth import hash_password
from .database import Base, SessionLocal, engine
from .models import (
    AgentAssignment,
    AISuggestion,
    AuditLog,
    Channel,
    Conversation,
    Customer,
    CustomerMetric,
    CustomerProfile,
    KnowledgeDocument,
    Message,
    Organization,
    RoutingRule,
    SentimentRecord,
    SupportTicket,
    User,
    Workspace,
)
from .services import analyze_text, chunk_document


def ensure_channels(db):
    channel_defs = [
        ("web_chat", "MessagesSquare"),
        ("email", "Mail"),
        ("mobile_app", "Smartphone"),
        ("social", "Share2"),
        ("in_store", "Store"),
    ]
    channels = []
    for name, icon in channel_defs:
        channel = db.query(Channel).filter(Channel.name == name).first()
        if not channel:
            channel = Channel(name=name, icon=icon)
            db.add(channel)
            db.flush()
        channels.append(channel)
    return channels


def demo_email(base: str, suffix: str) -> str:
    if not suffix:
        return f"{base}@example.com"
    return f"{base}+{suffix}@example.com"


def seed_curated_demo_data(db, org: Organization, users: list[User], email_suffix: str = "") -> None:
    if db.query(Customer).filter(Customer.organization_id == org.id).first():
        return
    channels = ensure_channels(db)
    agent = next((user for user in users if user.role in ("agent", "administrator")), users[0])
    customers = [
        ("Ari Vale", demo_email("ari.vale", email_suffix), "Platinum", "email", 12840, "Demo City", ["BrewMaster Pro", "Ceramic cups"], ["high_value", "delivery_issue"], 68, 0.82),
        ("Mira Sol", demo_email("mira.sol", email_suffix), "Gold", "web_chat", 7420, "Harbor District", ["Trail jacket"], ["duplicate_payment"], 74, 0.42),
        ("Nico Reed", demo_email("nico.reed", email_suffix), "Silver", "mobile_app", 3190, "Metro West", ["Smart scale"], ["refund_request"], 62, 0.58),
        ("Tala Frost", demo_email("tala.frost", email_suffix), "Bronze", "social", 980, "North Loop", ["Headphones"], ["recommendation"], 88, 0.2),
        ("Kian Park", demo_email("kian.park", email_suffix), "Gold", "email", 6840, "Lakeview", ["Security camera"], ["account_access"], 71, 0.48),
        ("Lena Quill", demo_email("lena.quill", email_suffix), "Silver", "in_store", 2450, "Old Town", ["Carry-on luggage"], ["damaged_product"], 57, 0.69),
        ("Remy Lin", demo_email("remy.lin", email_suffix), "Platinum", "mobile_app", 15120, "Central", ["Premium subscription"], ["loyalty"], 91, 0.18),
        ("Sora Wynn", demo_email("sora.wynn", email_suffix), "Gold", "web_chat", 8020, "West End", ["Meal kit plan"], ["cancellation_risk"], 49, 0.88),
    ]
    customer_objs = []
    for name, email, tier, pref, value, location, purchases, tags, sat, risk in customers:
        c = Customer(organization_id=org.id, name=name, email=email, loyalty_tier=tier, preferred_channel=pref, lifetime_value=value, location=location, recent_purchases=purchases, tags=tags, satisfaction_score=sat, churn_risk_score=risk)
        db.add(c)
        db.flush()
        db.add(CustomerProfile(customer_id=c.id, preferences={"contact_window": "Afternoons", "language": "English"}, churn_explanation=f"Churn risk {risk} based on satisfaction, repeat contact, and unresolved issues."))
        db.add(CustomerMetric(customer_id=c.id, metric_name="nps", metric_value=sat - 50))
        customer_objs.append(c)
    docs = [
        ("Refund Policy", "Refund requests are eligible within 30 days when proof of purchase is available. Duplicate payments should be reversed within two business days after verification."),
        ("Delivery Delay Escalation Policy", "Delayed delivery cases should receive proactive updates, shipment trace review, and expedited replacement when the promised delivery window is missed. Repeat contacts about the same order should route to Delivery or Escalations."),
        ("Payment Failures", "Failed or duplicate payments require transaction id validation, payment gateway check, and billing team escalation for high value customers."),
        ("Account Recovery", "Account access problems should be handled by verifying email ownership, sending a secure reset link, and avoiding disclosure of sensitive data."),
        ("Loyalty Benefits", "Gold and Platinum members receive priority support, extended returns, birthday rewards, and free expedited shipping on replacement orders."),
        ("Product Returns", "Returns require order validation, item condition notes, and a return authorization. Agents should explain refund or replacement timelines clearly."),
        ("Damaged Orders", "Damaged product reports should be acknowledged with empathy. Request photos when needed, offer priority replacement, and waive return shipping for verified damage."),
        ("Escalation Policy", "High urgency, negative sentiment, high-value customers, or churn risk above 0.75 should be escalated to a senior queue or relevant specialist team."),
    ]
    for title, content in docs:
        doc = KnowledgeDocument(organization_id=org.id, title=title, content=content, status="pending")
        db.add(doc)
        db.flush()
        chunk_document(db, doc)
    rules = [
        RoutingRule(organization_id=org.id, name="Refund to billing", intent="refund_request", department="Billing"),
        RoutingRule(organization_id=org.id, name="Account access to technical support", intent="account_access", department="Technical Support"),
        RoutingRule(organization_id=org.id, name="High-value frustrated to escalations", sentiment="frustrated", loyalty_tier="Platinum", department="Escalations"),
        RoutingRule(organization_id=org.id, name="High urgency delivery queue", urgency="high", department="Delivery"),
        RoutingRule(organization_id=org.id, name="Churn risk account support", churn_risk_min=0.75, department="Account Support"),
        RoutingRule(organization_id=org.id, name="Damaged delivery escalation", intent="technical_issue", department="Escalations"),
    ]
    db.add_all(rules)
    db.flush()
    scenario_messages = [
        ("Delayed delivery", "web_chat", "My espresso machine was supposed to arrive yesterday and tracking has not moved.", "We are checking the carrier trace and will update you today."),
        ("Duplicate payment", "email", "I was charged twice for the same trail jacket order.", "I found the duplicate authorization and escalated it to billing."),
        ("Refund request", "mobile_app", "The smart scale is not compatible with my app. I want a refund.", "I can start the return authorization and refund review."),
        ("Product recommendation", "social", "Which headphones are best for long flights?", "The QuietAir model is best for travel and has adaptive noise control."),
        ("Account access problem", "email", "I cannot log in after changing my phone.", "I sent a secure recovery link to your verified email."),
        ("Damaged product", "in_store", "My carry-on wheel cracked after one trip.", "We can inspect it and arrange a replacement under policy."),
        ("Loyalty benefit query", "mobile_app", "Do Platinum members get free expedited replacements?", "Yes, Platinum members receive expedited replacement shipping."),
        ("Subscription cancellation risk", "web_chat", "I am thinking of cancelling because deliveries keep arriving late.", "I can review your plan and apply a retention credit if eligible."),
    ]
    now = datetime.utcnow()
    for idx, (subject, channel_name, customer_body, agent_body) in enumerate(scenario_messages):
        customer = customer_objs[idx]
        channel = next(c for c in channels if c.name == channel_name)
        analysis = analyze_text(db, customer_body, customer)
        conv = Conversation(organization_id=org.id, customer_id=customer.id, channel_id=channel.id, subject=subject, priority="high" if analysis.urgency == "high" else "medium", sentiment=analysis.sentiment, unread=idx % 2 == 0, sla_risk=idx in (0, 7))
        conv.created_at = now - timedelta(days=10 - idx)
        db.add(conv)
        db.flush()
        bodies = [customer_body, agent_body, f"Follow-up for {subject.lower()} with customer context retained.", "Thank you for checking. Please keep me posted."]
        for j, body in enumerate(bodies):
            db.add(Message(conversation_id=conv.id, sender_type="customer" if j in (0, 3) else "agent", body=body, channel_name=channel_name, created_at=conv.created_at + timedelta(minutes=j * 12)))
        ticket = SupportTicket(organization_id=org.id, conversation_id=conv.id, customer_id=customer.id, title=subject, status="open" if idx % 3 else "resolved", priority=conv.priority, department=analysis.recommended_department, first_response_minutes=5 + idx * 3, resolution_minutes=45 + idx * 24, escalated=idx in (0, 5, 7), channel_name=channel_name)
        db.add(ticket)
        db.flush()
        db.add(AgentAssignment(ticket_id=ticket.id, agent_id=agent.id))
        db.add(SentimentRecord(customer_id=customer.id, conversation_id=conv.id, sentiment=analysis.sentiment, score=-0.7 if analysis.sentiment == "negative" else 0.2))
        db.add(AISuggestion(conversation_id=conv.id, provider="mock", model="mock-deterministic", intent=analysis.intent, sentiment=analysis.sentiment, urgency=analysis.urgency, summary=analysis.summary, suggested_response=analysis.suggested_response, next_best_action=analysis.next_best_action, recommended_department=analysis.recommended_department, confidence=analysis.confidence, sources=analysis.sources, status="approved" if idx < 3 else "pending"))
    flagship_customer = customer_objs[0]
    flagship_steps = [
        ("Order delayed - first contact", "web_chat", "Where is my BrewMaster Pro order? Tracking has not moved and it was due yesterday.", "We are opening a carrier trace and will update you by the end of the day."),
        ("Order delayed - email follow-up", "email", "I am following up again. I still do not have a delivery date and this is getting frustrating.", "Thank you for the follow-up. We are keeping this case linked to your original delivery issue."),
        ("Order delayed - mobile escalation", "mobile_app", "The app still shows delayed. If it cannot arrive this week, I need a refund or replacement.", "I can route this to Delivery for a firm update and prepare refund options if the order misses the promise date."),
        ("Order delayed - support desk escalation", "in_store", "I came to the support desk because this has now taken four contacts. Please escalate it.", "We are escalating the case and keeping the full channel history attached."),
    ]
    for offset, (subject, channel_name, customer_body, agent_body) in enumerate(flagship_steps):
        channel = next(c for c in channels if c.name == channel_name)
        analysis = analyze_text(db, customer_body, flagship_customer)
        conv = Conversation(organization_id=org.id, customer_id=flagship_customer.id, channel_id=channel.id, subject=subject, priority="high", sentiment=analysis.sentiment, unread=offset == len(flagship_steps) - 1, sla_risk=True)
        conv.created_at = now - timedelta(days=4 - offset)
        db.add(conv)
        db.flush()
        db.add(Message(conversation_id=conv.id, sender_type="customer", body=customer_body, channel_name=channel_name, created_at=conv.created_at))
        db.add(Message(conversation_id=conv.id, sender_type="agent", body=agent_body, channel_name=channel_name, created_at=conv.created_at + timedelta(minutes=9)))
        ticket = SupportTicket(organization_id=org.id, conversation_id=conv.id, customer_id=flagship_customer.id, title=subject, status="open", priority="high", department="Delivery" if offset < 3 else "Escalations", first_response_minutes=8 + offset, resolution_minutes=0, escalated=offset >= 2, channel_name=channel_name)
        db.add(ticket)
        db.flush()
        db.add(AgentAssignment(ticket_id=ticket.id, agent_id=agent.id))
        db.add(SentimentRecord(customer_id=flagship_customer.id, conversation_id=conv.id, sentiment=analysis.sentiment, score=-0.8))
    db.add(AuditLog(organization_id=org.id, user_id=agent.id, action="seed_demo", model_provider="mock", confidence=1, explanation=f"Seeded curated fictional demo data for {org.name}."))


DEMO_ORG_SLUG = "journeysync-demo-retail"
DEMO_USERS = [
    ("admin@journeysync.demo", "Avery Admin", "administrator"),
    ("agent@journeysync.demo", "Sam Support", "agent"),
    ("customer@journeysync.demo", "Casey Customer", "customer"),
]


def unusable_password_hash() -> str:
    return hash_password(secrets.token_urlsafe(48))


def provision_demo_tenant(db, reset_user_passwords: bool = True) -> Organization:
    org = db.query(Organization).filter(Organization.slug == DEMO_ORG_SLUG).first()
    if not org:
        org = Organization(name="JourneySync Demo Retail", slug=DEMO_ORG_SLUG, plan="enterprise_trial")
        db.add(org)
        db.flush()
    elif org.name != "JourneySync Demo Retail" or org.plan != "enterprise_trial":
        org.name = "JourneySync Demo Retail"
        org.plan = "enterprise_trial"

    workspace = db.query(Workspace).filter(
        Workspace.organization_id == org.id,
        Workspace.slug == "customer-operations",
    ).first()
    if not workspace:
        db.add(Workspace(organization_id=org.id, name="Customer Operations", slug="customer-operations", is_default=True))

    users = []
    for email, name, role in DEMO_USERS:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                organization_id=org.id,
                email=email,
                name=name,
                role=role,
                hashed_password=unusable_password_hash(),
            )
            db.add(user)
            db.flush()
        else:
            user.organization_id = org.id
            user.name = name
            user.role = role
            user.is_active = True
            if reset_user_passwords:
                user.hashed_password = unusable_password_hash()
        users.append(user)

    seed_curated_demo_data(db, org, users)
    db.commit()
    return org


def seed_database(reset: bool = False) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if reset:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    provision_demo_tenant(db, reset_user_passwords=False)
    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    seed_database(reset=args.reset)
