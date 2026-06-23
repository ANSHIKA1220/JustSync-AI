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
        department = "Customer Care"
        if any(w in lower for w in ["refund", "duplicate payment", "charged twice"]):
            intent, department = "refund_request", "Billing and Returns"
        elif any(w in lower for w in ["password", "login", "access", "account"]):
            intent, department = "account_access", "Technical Support"
        elif any(w in lower for w in ["damaged", "broken", "replacement"]):
            intent, department = "damaged_order", "Logistics and Returns"
        elif any(w in lower for w in ["cancel", "subscription"]):
            intent, department = "cancellation_risk", "Retention Team"
        elif any(w in lower for w in ["recommend", "which product"]):
            intent, department = "product_recommendation", "Sales"

        sentiment = "negative" if any(w in lower for w in ["angry", "upset", "damaged", "late", "cancel", "broken", "charged twice"]) else "positive" if "thank" in lower else "neutral"
        urgency = "high" if any(w in lower for w in ["urgent", "today", "angry", "cancel", "damaged", "broken"]) else "medium"
        tier = (customer_context or {}).get("loyalty_tier", "Standard")
        confidence = 0.91 if intent != "general_support" else 0.72
        action = "Verify order context, acknowledge the issue, apply policy, and keep the customer updated."
        if intent == "damaged_order":
            action = "Verify order photos if available and initiate priority replacement or return according to damaged-order policy."
        return AIAnalysis(
            intent=intent,
            sentiment=sentiment,
            urgency=urgency,
            summary=f"{tier} customer needs help with {intent.replace('_', ' ')}. Sentiment is {sentiment} and urgency is {urgency}.",
            recommended_department=department,
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
            "You are JourneySync AI, a customer support copilot. Return only valid JSON with these keys: "
            "intent, sentiment, urgency, summary, recommended_department, next_best_action, "
            "churn_risk_explanation, suggested_response, confidence. "
            "Use only non-protected business context for routing. Confidence must be between 0 and 1.\n\n"
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
