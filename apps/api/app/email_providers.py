import base64
import logging
from abc import ABC, abstractmethod
from typing import List

import httpx
from pydantic import BaseModel

from .config import settings

logger = logging.getLogger(__name__)


class EmailAttachment(BaseModel):
    filename: str
    content_type: str
    size: int
    data: bytes  # Raw data, we won't persist this directly in DB but we'll save it to disk/bucket in production. Here we just capture it.


class EmailMessage(BaseModel):
    id: str
    thread_id: str
    subject: str
    sender: str
    recipients: List[str]
    body: str
    attachments: List[EmailAttachment] = []


class EmailProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def fetch_unread(self) -> List[EmailMessage]:
        raise NotImplementedError

    @abstractmethod
    async def mark_read(self, message_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_reply(self, recipient: str, subject: str, body: str, thread_id: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    async def check_connection(self) -> bool:
        raise NotImplementedError


class MockEmailProvider(EmailProvider):
    name = "mock"

    async def fetch_unread(self) -> List[EmailMessage]:
        return []

    async def mark_read(self, message_id: str) -> None:
        pass

    async def send_reply(self, recipient: str, subject: str, body: str, thread_id: str | None = None) -> None:
        logger.info(f"[MockEmail] Sending email to {recipient} with subject '{subject}'")

    async def check_connection(self) -> bool:
        return True


class GmailProvider(EmailProvider):
    name = "gmail"
    timeout_seconds = 15

    def __init__(self):
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.refresh_token = settings.google_refresh_token
        self._access_token = None

    async def _get_access_token(self) -> str:
        if not self.refresh_token:
            raise ValueError("Gmail refresh token not configured")
        
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            resp.raise_for_status()
            self._access_token = resp.json()["access_token"]
            return self._access_token

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        token = self._access_token or await self._get_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.request(method, url, headers=headers, **kwargs)
            if resp.status_code == 401:
                token = await self._get_access_token()
                headers["Authorization"] = f"Bearer {token}"
                resp = await client.request(method, url, headers=headers, **kwargs)
            resp.raise_for_status()
            return resp

    def _parse_message(self, msg_data: dict) -> EmailMessage:
        payload = msg_data.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
        
        subject = headers.get("subject", "No Subject")
        sender = headers.get("from", "Unknown Sender")
        to_header = headers.get("to", "")
        recipients = [r.strip() for r in to_header.split(",") if r.strip()]

        body = ""
        attachments = []

        def extract_parts(parts: list):
            nonlocal body
            for part in parts:
                mime_type = part.get("mimeType")
                if mime_type == "text/plain" and not part.get("filename"):
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body += base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                elif mime_type == "multipart/alternative" or mime_type == "multipart/mixed":
                    extract_parts(part.get("parts", []))
                elif part.get("filename"):
                    size = part.get("body", {}).get("size", 0)
                    attachments.append(
                        EmailAttachment(
                            filename=part.get("filename"),
                            content_type=mime_type or "application/octet-stream",
                            size=size,
                            data=b"", # Not downloading data yet to save memory
                        )
                    )

        if "parts" in payload:
            extract_parts(payload["parts"])
        else:
            # Single part
            data = payload.get("body", {}).get("data", "")
            if data:
                body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

        return EmailMessage(
            id=msg_data["id"],
            thread_id=msg_data["threadId"],
            subject=subject,
            sender=sender,
            recipients=recipients,
            body=body.strip(),
            attachments=attachments,
        )

    async def fetch_unread(self) -> List[EmailMessage]:
        try:
            resp = await self._request("GET", "https://gmail.googleapis.com/gmail/v1/users/me/messages?q=is:unread")
            messages_meta = resp.json().get("messages", [])
            messages = []
            for meta in messages_meta[:10]:  # Limit batch
                msg_resp = await self._request("GET", f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{meta['id']}")
                messages.append(self._parse_message(msg_resp.json()))
            return messages
        except Exception as e:
            logger.error(f"Gmail fetch_unread error: {e}")
            raise

    async def mark_read(self, message_id: str) -> None:
        await self._request(
            "POST",
            f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/modify",
            json={"removeLabelIds": ["UNREAD"]},
        )

    async def send_reply(self, recipient: str, subject: str, body: str, thread_id: str | None = None) -> None:
        message_str = f"To: {recipient}\r\nSubject: {subject}\r\n\r\n{body}"
        encoded_message = base64.urlsafe_b64encode(message_str.encode("utf-8")).decode("utf-8")
        payload = {"raw": encoded_message}
        if thread_id:
            payload["threadId"] = thread_id
        
        await self._request(
            "POST",
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            json=payload,
        )

    async def check_connection(self) -> bool:
        try:
            await self._get_access_token()
            return True
        except Exception:
            return False


class OutlookProvider(EmailProvider):
    name = "outlook"
    timeout_seconds = 15

    def __init__(self):
        self.client_id = settings.microsoft_client_id
        self.client_secret = settings.microsoft_client_secret
        self.tenant_id = settings.microsoft_tenant_id or "common"
        self.refresh_token = settings.microsoft_refresh_token
        self._access_token = None

    async def _get_access_token(self) -> str:
        if not self.refresh_token:
            raise ValueError("Outlook refresh token not configured")
        
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(
                f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                    "scope": "https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Mail.Send",
                },
            )
            resp.raise_for_status()
            self._access_token = resp.json()["access_token"]
            return self._access_token

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        token = self._access_token or await self._get_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.request(method, url, headers=headers, **kwargs)
            if resp.status_code == 401:
                token = await self._get_access_token()
                headers["Authorization"] = f"Bearer {token}"
                resp = await client.request(method, url, headers=headers, **kwargs)
            resp.raise_for_status()
            return resp

    async def fetch_unread(self) -> List[EmailMessage]:
        try:
            resp = await self._request("GET", "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$filter=isRead eq false&$top=10")
            items = resp.json().get("value", [])
            messages = []
            for item in items:
                attachments = []
                if item.get("hasAttachments"):
                    att_resp = await self._request("GET", f"https://graph.microsoft.com/v1.0/me/messages/{item['id']}/attachments")
                    for att in att_resp.json().get("value", []):
                        attachments.append(EmailAttachment(
                            filename=att.get("name", "attachment"),
                            content_type=att.get("contentType", "application/octet-stream"),
                            size=att.get("size", 0),
                            data=b"",
                        ))
                
                messages.append(EmailMessage(
                    id=item["id"],
                    thread_id=item["conversationId"],
                    subject=item.get("subject", "No Subject"),
                    sender=item.get("from", {}).get("emailAddress", {}).get("address", "Unknown Sender"),
                    recipients=[r.get("emailAddress", {}).get("address") for r in item.get("toRecipients", [])],
                    body=item.get("bodyPreview", ""),
                    attachments=attachments,
                ))
            return messages
        except Exception as e:
            logger.error(f"Outlook fetch_unread error: {e}")
            raise

    async def mark_read(self, message_id: str) -> None:
        await self._request(
            "PATCH",
            f"https://graph.microsoft.com/v1.0/me/messages/{message_id}",
            json={"isRead": True},
        )

    async def send_reply(self, recipient: str, subject: str, body: str, thread_id: str | None = None) -> None:
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": recipient}}],
            },
            "saveToSentItems": "true"
        }
        await self._request("POST", "https://graph.microsoft.com/v1.0/me/sendMail", json=payload)

    async def check_connection(self) -> bool:
        try:
            await self._get_access_token()
            return True
        except Exception:
            return False


def get_email_provider() -> EmailProvider:
    provider = settings.email_provider.lower()
    if provider == "gmail":
        return GmailProvider()
    if provider == "outlook":
        return OutlookProvider()
    return MockEmailProvider()
