# Enterprise SaaS Roadmap

JourneySync AI is being rebuilt from a hackathon prototype into a multi-tenant enterprise SaaS platform. The current implementation has started with the platform foundation because every later feature depends on tenant isolation, authenticated organizations, and repeatable deployment.

## Phase 1: SaaS Foundation

Status: started.

Implemented:

- Organization metadata with slug, plan, and status.
- Default workspace model.
- Signup endpoint that creates an organization and administrator.
- Admin invite endpoint for organization-scoped users.
- JWT tenant context.
- Tenant-scoped users, customers, conversations, tickets, knowledge, routing, analytics, and audit logs.
- Tenant isolation test coverage.
- Organization settings page in the frontend.
- Database migration for tenant foundation.

Next:

- Replace temporary-password invites with email-based invite tokens.
- Add account status, last login, and auth event audit logs.
- Add password reset and email verification.
- Add permission names beyond coarse roles.

## Phase 2: Enterprise App Shell

Next implementation targets:

- Organization switcher and workspace switcher.
- Account/profile page.
- Admin settings for team management.
- Onboarding checklist for connecting first channel and uploading knowledge.
- Error boundaries and stronger API failure messaging.

## Phase 3: Connectors

Initial connector order:

1. Web chat widget.
2. Email ingestion.
3. CRM import/export.
4. WhatsApp/SMS.
5. Social and helpdesk integrations.

Connector requirements:

- OAuth or API key storage through a secrets manager.
- Webhook signature verification.
- Retry handling.
- Connector health checks.
- Per-tenant connector configuration.

## Phase 4: Production AI And RAG

Target:

- Tenant-isolated document ingestion.
- Chunk metadata and source citations.
- Embeddings with pgvector first.
- AI gateway for provider calls, validation, rate limits, cost logging, and fallback.
- Human approval workflow for risky actions.

## Phase 5: Workflow Automation

Target:

- SLA policies.
- Assignment rules.
- Escalation policies.
- Saved queues and views.
- Notification rules.
- Internal notes and approval flows.

## Phase 6: Analytics And Reporting

Target:

- Event-backed metrics.
- SLA reporting.
- Agent performance.
- AI adoption and deflection metrics.
- CSV/PDF exports.

## Phase 7: Security, Compliance, Reliability

Target:

- Tenant isolation tests across all resources.
- Structured logs with request IDs.
- Sentry/OpenTelemetry.
- Dependency scanning.
- Backup/restore documentation.
- Data export/delete flows.
- Immutable audit log strategy.

## Phase 8: Billing And Plans

Target:

- Stripe subscriptions.
- Seat limits.
- AI usage limits.
- Feature gates.
- Billing portal.

## Inputs And Accesses Needed

I can continue locally through the core SaaS build. To ship the full product, I will need:

- Deployment target: Render, Railway, Fly.io, AWS, Azure, GCP, or another host.
- Deployment target selected: Render for backend and Cloudflare Pages for frontend.
- Domain name and DNS access later; free platform URLs are enough initially.
- Managed PostgreSQL selected: Neon.
- Email provider selected for phase 2: Resend.
- Primary AI provider selected: Gemini API.
- Object storage selected for later: Cloudflare R2.
- Error tracking: Sentry DSN or preferred observability platform.
- Optional billing: Stripe test keys.
- Optional connectors: API credentials/webhook config for email, CRM, WhatsApp/SMS, and social channels.

## Current Milestone Definition

Milestone 1 is complete when a new organization can sign up, invite an agent, see only its own data, upload/search its own knowledge, and operate conversations without data leaking across tenants.
