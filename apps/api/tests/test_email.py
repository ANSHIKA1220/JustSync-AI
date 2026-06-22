import os
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from app.database import SessionLocal
from app.models import Customer, Conversation, Message, Attachment
from app.email_providers import MockEmailProvider, GmailProvider, OutlookProvider, EmailMessage, EmailAttachment
from app.email_sync import process_email

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.mark.asyncio
async def test_mock_email_provider():
    provider = MockEmailProvider()
    unread = await provider.fetch_unread()
    assert unread == []
    assert await provider.check_connection() is True


@pytest.mark.asyncio
async def test_gmail_provider_no_token():
    provider = GmailProvider()
    provider.refresh_token = ""
    with pytest.raises(ValueError):
        await provider.check_connection()


@pytest.mark.asyncio
async def test_outlook_provider_no_token():
    provider = OutlookProvider()
    provider.refresh_token = ""
    with pytest.raises(ValueError):
        await provider.check_connection()


@pytest.mark.asyncio
async def test_process_email_new_customer_and_conversation(db):
    msg = EmailMessage(
        id="msg123",
        thread_id="thread123",
        subject="Test Subject",
        sender="newuser@example.com",
        recipients=["support@journeysync.com"],
        body="This is a test email.",
        attachments=[
            EmailAttachment(filename="test.txt", content_type="text/plain", size=10, data=b"test")
        ]
    )
    provider = AsyncMock()
    
    await process_email(msg, provider)
    
    provider.mark_read.assert_awaited_once_with("msg123")
    
    customer = db.query(Customer).filter(Customer.email == "newuser@example.com").first()
    assert customer is not None
    
    conv = db.query(Conversation).filter(Conversation.customer_id == customer.id).first()
    assert conv is not None
    assert conv.subject == "Test Subject"
    
    db_msg = db.query(Message).filter(Message.external_id == "msg123").first()
    assert db_msg is not None
    assert db_msg.body == "This is a test email."
    
    att = db.query(Attachment).filter(Attachment.message_id == db_msg.id).first()
    assert att is not None
    assert att.filename == "test.txt"


@pytest.mark.asyncio
async def test_process_email_duplicate_prevention(db):
    msg = EmailMessage(
        id="msg_duplicate",
        thread_id="thread456",
        subject="Duplicate Subject",
        sender="existing@example.com",
        recipients=[],
        body="Body",
        attachments=[]
    )
    provider = AsyncMock()
    
    await process_email(msg, provider)
    
    # Should not process again
    provider_mock2 = AsyncMock()
    await process_email(msg, provider_mock2)
    provider_mock2.mark_read.assert_not_called()
    
    count = db.query(Message).filter(Message.external_id == "msg_duplicate").count()
    assert count == 1
