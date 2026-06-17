from dataclasses import dataclass
from datetime import datetime


@dataclass
class NormalizedMessage:
    channel: str
    sender_type: str
    body: str
    received_at: str
    metadata: dict


class ChannelAdapter:
    channel = "generic"

    def normalize_payload(self, payload: dict) -> NormalizedMessage:
        return NormalizedMessage(
            channel=self.channel,
            sender_type=payload.get("sender_type", "customer"),
            body=payload["body"],
            received_at=datetime.utcnow().isoformat(),
            metadata={"simulated": True, "source_payload": payload},
        )

    def receive_message(self, payload: dict) -> NormalizedMessage:
        return self.normalize_payload(payload)

    def send_message(self, body: str) -> dict:
        return {"channel": self.channel, "status": "sent", "body": body, "simulated": True}


class WebChatAdapter(ChannelAdapter):
    channel = "web_chat"


class EmailAdapter(ChannelAdapter):
    channel = "email"


class MobileAdapter(ChannelAdapter):
    channel = "mobile_app"


class SocialAdapter(ChannelAdapter):
    channel = "social"


class StoreAdapter(ChannelAdapter):
    channel = "in_store"


ADAPTERS = {
    "web_chat": WebChatAdapter(),
    "email": EmailAdapter(),
    "mobile_app": MobileAdapter(),
    "social": SocialAdapter(),
    "in_store": StoreAdapter(),
}
