# Architecture

JourneySync AI is a monorepo with a Next.js frontend and FastAPI backend. The backend owns authentication, RBAC, persistence, AI orchestration, RAG retrieval, routing, audit logs, and metrics. The frontend is an enterprise SaaS console with role-aware navigation.

The app defaults to mock AI mode for offline reliability. Optional OpenAI-compatible and Ollama providers are selected by `AI_PROVIDER`.
