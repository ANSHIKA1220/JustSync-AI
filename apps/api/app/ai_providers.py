import json
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import ValidationError

from .config import settings
from .schemas import AIAnalysis


class AIProvider(ABC):
    name = "base"
    model = "unknown"

    @abstractmethod
    async def analyze(
        self,
        messages: list[dict[str, str]],
        sources: list[dict[str, Any]],
        customer_context: dict[str, Any] | None = None,
    ) -> AIAnalysis:
        raise NotImplementedError


class MockAIProvider(AIProvider):
    name = "mock"
    model = "mock-deterministic"

    async def analyze(
        self,
        messages: list[dict[str, str]],
        sources: list[dict[str, Any]],
        customer_context: dict[str, Any] | None = None,
    ) -> AIAnalysis:
        text = "\n".join(message.get("content", "") for message in messages)
        lower = text.lower()
        intent = "general_support"
        department = "Account Support"
        if any(w in lower for w in ["refund", "duplicate payment", "charged twice"]):
            intent, department = "refund_request", "Billing"
        elif any(w in lower for w in ["password", "login", "access", "account"]):
            intent, department = "account_access", "Technical Support"
        elif any(w in lower for w in ["late", "delayed", "tracking", "shipment", "delivery"]):
            intent, department = "delivery_delay", "Delivery"
        elif any(w in lower for w in ["damaged", "broken", "replacement"]):
            intent, department = "technical_issue", "Escalations"
        elif any(w in lower for w in ["cancel", "subscription"]):
            intent, department = "billing_issue", "Account Support"
        elif any(w in lower for w in ["recommend", "which product"]):
            intent, department = "general_support", "Account Support"

        sentiment = "angry" if any(w in lower for w in ["angry", "furious"]) else "frustrated" if any(w in lower for w in ["upset", "damaged", "late", "delayed", "cancel", "broken", "charged twice"]) else "positive" if "thank" in lower else "neutral"
        urgency = "critical" if any(w in lower for w in ["urgent escalation", "legal", "unsafe"]) else "high" if any(w in lower for w in ["urgent", "today", "angry", "cancel", "damaged", "broken", "late", "delayed"]) else "medium"
        tier = (customer_context or {}).get("loyalty_tier", "Standard")
        confidence = 0.91 if intent != "general_support" else 0.72
        action = "Verify order context, acknowledge the issue, apply policy, and keep the customer updated."
        if intent == "delivery_delay":
            action = "Open a carrier trace, assign Delivery, give the customer a concrete update window, and escalate if the promise date was missed."
        if intent == "technical_issue":
            action = "Verify order photos if available and initiate priority replacement or return according to damaged-order policy."
        repeat_contact = len(messages) > 2 or any(w in lower for w in ["again", "follow up", "next day", "still", "continued"])
        history_summary = customer_context.get("history_summary") if customer_context else ""
        history_summary = history_summary or f"{tier} customer with preferred channel {(customer_context or {}).get('preferred_channel', 'unknown')} and recent support context."
        conversation_summary = f"The customer reports {intent.replace('_', ' ')} with {sentiment} sentiment and {urgency} urgency."
        routing_reason = f"{department} is recommended because intent={intent}, urgency={urgency}, sentiment={sentiment}, and tenant knowledge was checked."
        return AIAnalysis(
            intent=intent,
            sentiment=sentiment,
            urgency=urgency,
            repeat_contact=repeat_contact,
            repeat_contact_reason="Multiple messages or follow-up language indicate repeated contact." if repeat_contact else "No clear repeat-contact signal in the assembled context.",
            customer_history_summary=history_summary,
            conversation_summary=conversation_summary,
            summary=f"{tier} customer needs help with {intent.replace('_', ' ')}. Sentiment is {sentiment} and urgency is {urgency}.",
            recommended_department=department,
            routing_reason=routing_reason,
            next_best_action=action,
            churn_risk_explanation=f"Risk is elevated when {sentiment} sentiment combines with recent repeat contact and {tier} loyalty status.",
            suggested_response=(
                "I am sorry this experience has fallen short. I reviewed your recent history and the relevant policy. "
                "I can help resolve this now, confirm the next step, and keep the case prioritized until it is complete."
            ),
            confidence=confidence,
            sources=sources,
        )


class JSONLLMProvider(AIProvider):
    timeout_seconds = 25

    def build_prompt(
        self,
        messages: list[dict[str, str]],
        sources: list[dict[str, Any]],
        customer_context: dict[str, Any] | None,
    ) -> str:
        return (
            "You are JourneySync AI, an explainable support decision layer. Return only valid JSON. "
            "Required keys: intent, sentiment, urgency, repeat_contact, repeat_contact_reason, "
            "customer_history_summary, conversation_summary, summary, recommended_department, routing_reason, "
            "next_best_action, churn_risk_explanation, suggested_response, confidence. "
            "Allowed intent values include delivery_delay, refund_request, billing_issue, account_access, technical_issue, general_support. "
            "Allowed sentiment values are positive, neutral, frustrated, angry, urgent. "
            "Allowed urgency values are low, medium, high, critical. "
            "Use only supplied tenant context and retrieved knowledge. Do not invent external policy. Confidence must be between 0 and 1.\n\n"
            f"Customer context: {json.dumps(customer_context or {}, ensure_ascii=False)}\n"
            f"Retrieved knowledge sources: {json.dumps(sources, ensure_ascii=False)}\n"
            f"Conversation messages: {json.dumps(messages, ensure_ascii=False)}"
        )

    def parse_analysis(self, content: str, sources: list[dict[str, Any]]) -> AIAnalysis:
        match = re.search(r"\{.*\}", content, flags=re.DOTALL)
        if not match:
            raise ValueError("LLM response did not contain a JSON object")
        raw = json.loads(match.group(0))
        raw["sources"] = sources
        raw.setdefault("summary", raw.get("conversation_summary", "AI analysis completed."))
        raw.setdefault("repeat_contact", False)
        raw.setdefault("repeat_contact_reason", "")
        raw.setdefault("customer_history_summary", "")
        raw.setdefault("conversation_summary", raw["summary"])
        raw.setdefault("routing_reason", "Recommended from structured analysis and retrieved tenant knowledge.")
        return AIAnalysis.model_validate(raw)


class OllamaAIProvider(JSONLLMProvider):
    name = "ollama"

    def __init__(self) -> None:
        self.model = settings.ollama_model

    async def analyze(
        self,
        messages: list[dict[str, str]],
        sources: list[dict[str, Any]],
        customer_context: dict[str, Any] | None = None,
    ) -> AIAnalysis:
        prompt = self.build_prompt(messages, sources, customer_context)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{settings.ollama_base_url.rstrip('/')}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "format": "json",
                    "messages": [
                        {"role": "system", "content": "Return strict JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        return self.parse_analysis(content, sources)


class OpenAICompatibleProvider(JSONLLMProvider):
    name = "openai"

    def __init__(self) -> None:
        self.model = settings.openai_model

    async def analyze(
        self,
        messages: list[dict[str, str]],
        sources: list[dict[str, Any]],
        customer_context: dict[str, Any] | None = None,
    ) -> AIAnalysis:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not configured")
        prompt = self.build_prompt(messages, sources, customer_context)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": self.model,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": "Return strict JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return self.parse_analysis(content, sources)


class GeminiAIProvider(JSONLLMProvider):
    name = "gemini"

    def __init__(self) -> None:
        self.model = settings.gemini_model

    async def analyze(
        self,
        messages: list[dict[str, str]],
        sources: list[dict[str, Any]],
        customer_context: dict[str, Any] | None = None,
    ) -> AIAnalysis:
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not configured")
        prompt = self.build_prompt(messages, sources, customer_context)
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{settings.gemini_base_url.rstrip('/')}/models/{self.model}:generateContent",
                headers={"Content-Type": "application/json", "x-goog-api-key": settings.gemini_api_key},
                json={
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
                },
            )
            response.raise_for_status()
        candidates = response.json().get("candidates", [])
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        content = "\n".join(part.get("text", "") for part in parts)
        return self.parse_analysis(content, sources)


def get_ai_provider() -> AIProvider:
    provider = settings.ai_provider.lower()
    if provider == "ollama":
        return OllamaAIProvider()
    if provider == "openai":
        return OpenAICompatibleProvider()
    if provider == "gemini":
        return GeminiAIProvider()
    return MockAIProvider()


def get_provider_status() -> dict[str, Any]:
    configured = settings.ai_provider.lower()
    status: dict[str, Any] = {
        "configured_provider": configured,
        "active_provider": "mock" if configured == "mock" else configured,
        "fallback_active": False,
        "model": "mock-deterministic",
        "ollama_available": False,
        "database_mode": "sqlite" if settings.database_url.startswith("sqlite") else "postgresql",
    }
    if configured == "ollama":
        status["model"] = settings.ollama_model
        try:
            response = httpx.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=1.5)
            response.raise_for_status()
            models = [item.get("name") for item in response.json().get("models", [])]
            status["ollama_available"] = True
            status["active_provider"] = "ollama"
            if models and settings.ollama_model in models:
                status["model"] = settings.ollama_model
        except httpx.HTTPError:
            status["active_provider"] = "mock"
            status["fallback_active"] = True
            status["model"] = "mock-deterministic"
    elif configured == "openai":
        status["model"] = settings.openai_model
        if not settings.openai_api_key:
            status["active_provider"] = "mock"
            status["fallback_active"] = True
            status["model"] = "mock-deterministic"
    elif configured == "gemini":
        status["model"] = settings.gemini_model
        if not settings.gemini_api_key:
            status["active_provider"] = "mock"
            status["fallback_active"] = True
            status["model"] = "mock-deterministic"
    return status


async def analyze_with_fallback(
    messages: list[dict[str, str]],
    sources: list[dict[str, Any]],
    customer_context: dict[str, Any] | None = None,
) -> tuple[AIAnalysis, str, str, str | None]:
    provider = get_ai_provider()
    fallback = MockAIProvider()
    try:
        analysis = await provider.analyze(messages, sources, customer_context)
        return analysis, provider.name, provider.model, None
    except (httpx.HTTPError, ValidationError, ValueError, KeyError, json.JSONDecodeError) as exc:
        analysis = await fallback.analyze(messages, sources, customer_context)
        return analysis, fallback.name, fallback.model, f"{provider.name} failed: {exc}"
