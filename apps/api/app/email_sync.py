import asyncio
import logging
from datetime import datetime

from .database import SessionLocal
from .email_providers import MockEmailProvider, get_email_provider
from .models import Attachment, Channel, Conversation, Customer, Message, SupportTicket
from .services import create_ai_suggestion

logger = logging.getLogger(__name__)


async def process_email(msg, provider) -> None:
    db = SessionLocal()
    try:
        # Check for duplicates
        existing = db.query(Message).filter(Message.external_id == msg.id).first()
        if existing:
            return

        # Find or create customer
        customer = db.query(Customer).filter(Customer.email == msg.sender).first()
        if not customer:
            org_id = db.query(Customer).first().organization_id  # fallback org
            customer = Customer(
                organization_id=org_id,
                name=msg.sender.split("@")[0],
                email=msg.sender,
                loyalty_tier="Standard",
                preferred_channel="email",
                lifetime_value=0.0,
                location="Unknown",
                satisfaction_score=50,
                churn_risk_score=0.1,
            )
            db.add(customer)
            db.flush()

        # Find or create channel
        channel = db.query(Channel).filter(Channel.name == "email").first()
        if not channel:
            channel = Channel(name="email", icon="Mail")
            db.add(channel)
            db.flush()

        # Find existing conversation by thread id or subject
        conv = None
        if msg.thread_id:
            msg_with_thread = db.query(Message).filter(Message.metadata_json.op("->>")("thread_id") == msg.thread_id).first()
            if msg_with_thread:
                conv = msg_with_thread.conversation
        if not conv:
            # Create new conversation
            conv = Conversation(
                customer_id=customer.id,
                channel_id=channel.id,
                subject=msg.subject,
                priority="medium",
                sentiment="neutral",
                unread=True,
                sla_risk=False,
            )
            db.add(conv)
            db.flush()
            
            # Create ticket
            ticket = SupportTicket(
                conversation_id=conv.id,
                customer_id=customer.id,
                title=msg.subject,
                channel_name="email",
            )
            db.add(ticket)

        # Create message
        db_msg = Message(
            conversation_id=conv.id,
            sender_type="customer",
            body=msg.body,
            channel_name="email",
            external_id=msg.id,
            metadata_json={"thread_id": msg.thread_id, "recipients": msg.recipients},
        )
        db.add(db_msg)
        db.flush()

        # Add attachments
        for att in msg.attachments:
            db_att = Attachment(
                message_id=db_msg.id,
                filename=att.filename,
                content_type=att.content_type,
                size=att.size,
            )
            db.add(db_att)

        db.commit()

        # Run AI Pipeline
        create_ai_suggestion(db, conv)
        
        # Broadcast WS
        db.refresh(conv)
        from .main import manager
        conv_dict = {
            "id": conv.id,
            "subject": conv.subject,
            "priority": conv.priority,
            "sentiment": conv.sentiment,
            "unread": conv.unread,
            "sla_risk": conv.sla_risk,
            "customer": {"name": customer.name, "email": customer.email},
            "channel": {"name": "email"},
            "latest_message": db_msg.body[:50] + "...",
        }
        manager.broadcast_sync("conversation.created", conv_dict)

        # Mark as read
        await provider.mark_read(msg.id)

    except Exception as e:
        logger.error(f"Error processing email {msg.id}: {e}")
        db.rollback()
    finally:
        db.close()


async def email_sync_loop():
    logger.info("Starting email sync loop...")
    while True:
        try:
            provider = get_email_provider()
            if isinstance(provider, MockEmailProvider):
                await asyncio.sleep(30)
                continue

            try:
                connected = await provider.check_connection()
                if not connected:
                    logger.warning("Email provider connection failed. Falling back to Mock.")
                    provider = MockEmailProvider()
            except Exception as e:
                logger.error(f"Provider auth error, fallback to Mock: {e}")
                provider = MockEmailProvider()

            if not isinstance(provider, MockEmailProvider):
                unread_msgs = await provider.fetch_unread()
                for msg in unread_msgs:
                    await process_email(msg, provider)

        except Exception as e:
            logger.error(f"Email sync loop error: {e}")
        
        await asyncio.sleep(30)
