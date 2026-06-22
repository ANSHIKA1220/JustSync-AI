import argparse
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
)
from .services import analyze_text, chunk_document


def seed_database(reset: bool = False) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if reset:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    if db.query(User).first():
        db.close()
        return
    org = Organization(name="JourneySync AI Demo Retail")
    db.add(org)
    db.flush()
    users = [
        User(organization_id=org.id, email="admin@journeysync.demo", name="Avery Admin", role="administrator", hashed_password=hash_password("Admin123!")),
        User(organization_id=org.id, email="agent@journeysync.demo", name="Sam Support", role="agent", hashed_password=hash_password("Agent123!")),
        User(organization_id=org.id, email="customer@journeysync.demo", name="Casey Customer", role="customer", hashed_password=hash_password("Customer123!")),
    ]
    db.add_all(users)
    channels = [
        Channel(name="web_chat", icon="MessagesSquare"),
        Channel(name="email", icon="Mail"),
        Channel(name="mobile_app", icon="Smartphone"),
        Channel(name="social", icon="Share2"),
        Channel(name="in_store", icon="Store"),
    ]
    db.add_all(channels)
    db.flush()
    customers = [
        ("Priya Shah", "priya.shah@example.com", "Platinum", "email", 12840, "Mumbai", ["BrewMaster Pro", "Ceramic cups"], ["high_value", "delivery_issue"], 68, 0.82),
        ("Marcus Lee", "marcus.lee@example.com", "Gold", "web_chat", 7420, "Seattle", ["Trail jacket"], ["duplicate_payment"], 74, 0.42),
        ("Elena Garcia", "elena.garcia@example.com", "Silver", "mobile_app", 3190, "Madrid", ["Smart scale"], ["refund_request"], 62, 0.58),
        ("Noah Wilson", "noah.wilson@example.com", "Bronze", "social", 980, "Austin", ["Headphones"], ["recommendation"], 88, 0.2),
        ("Aisha Khan", "aisha.khan@example.com", "Gold", "email", 6840, "Dubai", ["Security camera"], ["account_access"], 71, 0.48),
        ("Liam O'Brien", "liam.obrien@example.com", "Silver", "in_store", 2450, "Dublin", ["Carry-on luggage"], ["damaged_product"], 57, 0.69),
        ("Mei Chen", "mei.chen@example.com", "Platinum", "mobile_app", 15120, "Singapore", ["Premium subscription"], ["loyalty"], 91, 0.18),
        ("Sofia Rossi", "sofia.rossi@example.com", "Gold", "web_chat", 8020, "Milan", ["Meal kit plan"], ["cancellation_risk"], 49, 0.88),
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
        ("Shipping Delays", "Delayed delivery cases should receive proactive updates, shipment trace review, and expedited replacement when the promised delivery window is missed."),
        ("Payment Failures", "Failed or duplicate payments require transaction id validation, payment gateway check, and billing team escalation for high value customers."),
        ("Account Recovery", "Account access problems should be handled by verifying email ownership, sending a secure reset link, and avoiding disclosure of sensitive data."),
        ("Loyalty Benefits", "Gold and Platinum members receive priority support, extended returns, birthday rewards, and free expedited shipping on replacement orders."),
        ("Product Returns", "Returns require order validation, item condition notes, and a return authorization. Agents should explain refund or replacement timelines clearly."),
        ("Damaged Orders", "Damaged product reports should be acknowledged with empathy. Request photos when needed, offer priority replacement, and waive return shipping for verified damage."),
        ("Escalation Policy", "High urgency, negative sentiment, high-value customers, or churn risk above 0.75 should be escalated to a senior queue or relevant specialist team."),
    ]
    for title, content in docs:
        doc = KnowledgeDocument(title=title, content=content, status="pending")
        db.add(doc)
        db.flush()
        chunk_document(db, doc)
    rules = [
        RoutingRule(name="Refund to billing and returns", intent="refund_request", department="Billing and Returns"),
        RoutingRule(name="Account access to technical support", intent="account_access", department="Technical Support"),
        RoutingRule(name="High-value negative to senior retention", sentiment="negative", loyalty_tier="Platinum", department="Senior Retention Agent"),
        RoutingRule(name="High urgency priority queue", urgency="high", department="Priority Queue"),
        RoutingRule(name="Churn risk retention", churn_risk_min=0.75, department="Retention Team"),
        RoutingRule(name="Damaged delivery logistics", intent="damaged_order", department="Logistics and Returns"),
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
        conv = Conversation(customer_id=customer.id, channel_id=channel.id, subject=subject, priority="high" if analysis.urgency == "high" else "medium", sentiment=analysis.sentiment, unread=idx % 2 == 0, sla_risk=idx in (0, 7))
        conv.created_at = now - timedelta(days=10 - idx)
        db.add(conv)
        db.flush()
        bodies = [customer_body, agent_body, f"Follow-up for {subject.lower()} with customer context retained.", "Thank you for checking. Please keep me posted."]
        for j, body in enumerate(bodies):
            db.add(Message(conversation_id=conv.id, sender_type="customer" if j in (0, 3) else "agent", body=body, channel_name=channel_name, created_at=conv.created_at + timedelta(minutes=j * 12)))
        ticket = SupportTicket(conversation_id=conv.id, customer_id=customer.id, title=subject, status="open" if idx % 3 else "resolved", priority=conv.priority, department=analysis.recommended_department, first_response_minutes=5 + idx * 3, resolution_minutes=45 + idx * 24, escalated=idx in (0, 5, 7), channel_name=channel_name)
        db.add(ticket)
        db.flush()
        db.add(AgentAssignment(ticket_id=ticket.id, agent_id=users[1].id))
        db.add(SentimentRecord(customer_id=customer.id, conversation_id=conv.id, sentiment=analysis.sentiment, score=-0.7 if analysis.sentiment == "negative" else 0.2))
        db.add(AISuggestion(conversation_id=conv.id, provider="mock", model="mock-deterministic", intent=analysis.intent, sentiment=analysis.sentiment, urgency=analysis.urgency, summary=analysis.summary, suggested_response=analysis.suggested_response, next_best_action=analysis.next_best_action, recommended_department=analysis.recommended_department, confidence=analysis.confidence, sources=analysis.sources, status="approved" if idx < 3 else "pending"))
    db.add(AuditLog(user_id=users[0].id, action="seed_demo", model_provider="mock", confidence=1, explanation="Seeded JourneySync AI demo data."))
    db.commit()
    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    seed_database(reset=args.reset)
