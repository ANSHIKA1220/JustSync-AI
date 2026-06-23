# Deployment Runbook

This runbook turns the hackathon prototype into a deployment-ready service baseline using the selected free-first stack:

- Frontend: Cloudflare Pages Free.
- Backend: Render Free Web Service.
- Database: Neon Free PostgreSQL.
- Primary AI: Gemini API with a Flash-family model.
- AI fallback: deterministic mock provider.
- Knowledge-file storage: Cloudflare R2 Free Tier, added after basic deployment.
- Email invites/password reset: Resend Free Tier, added after a domain or subdomain is ready.

## Required Production Settings

Start from `.env.production.example` and provide real values through your hosting platform's secret manager. Do not commit filled production env files.

The API refuses to boot with unsafe production values when `ENVIRONMENT=production`:

- `JWT_SECRET` must not be a demo/default secret.
- `DATABASE_URL` must not use SQLite.
- `SEED_DEMO_DATA` must be `false`.

Use `CORS_ORIGINS` as a comma-separated allowlist of deployed frontend origins.

For this deployment profile:

- Set `DATABASE_URL` to your Neon pooled or direct PostgreSQL URL.
- Set `AI_PROVIDER=gemini`.
- Set `GEMINI_API_KEY` from Google AI Studio.
- Keep `SEED_DEMO_DATA=false` for production-like environments.
- Use the Cloudflare Pages URL as `FRONTEND_URL` and in `CORS_ORIGINS`.
- Use the Render backend URL as `NEXT_PUBLIC_API_URL` when building the frontend.

## Database And Migrations

The API container runs:

```bash
alembic upgrade head
```

before starting Uvicorn. This keeps schema changes explicit and repeatable. Demo seed data only loads when `SEED_DEMO_DATA=true`, which should be limited to local/dev environments.

## Container Flow

Local smoke test:

```bash
cp .env.example .env
docker compose up --build
```

Production shape:

1. Create a Neon PostgreSQL database.
2. Create a Render web service from `apps/api`.
3. Add production environment variables in Render.
4. Create a Cloudflare Pages project from `apps/web`.
5. Set `NEXT_PUBLIC_API_URL` in Cloudflare Pages to the Render API URL.
6. Point health checks at:
   - API liveness/provider status: `/health`
   - API readiness/database check: `/ready`

## Render Backend

Recommended free-tier settings:

- Root directory: `apps/api`
- Build command: `pip install -r requirements.txt`
- Start command: `sh start.sh`
- Health check path: `/ready`

Render free services can sleep after inactivity. The first request after sleep may be slow, so keep the deterministic mock fallback enabled for demo resilience.

## Cloudflare Pages Frontend

Recommended settings:

- Root directory: `apps/web`
- Build command: `npm ci && npm run build`
- Output directory: `.next`
- Environment variable: `NEXT_PUBLIC_API_URL=https://<your-render-service>.onrender.com`

If the Next.js adapter requires a different Cloudflare Pages output mode later, adjust this section after the first deployment test.

## Release Checklist

- Run backend tests: `cd apps/api && py -m pytest`
- Run backend lint: `cd apps/api && py -m ruff check app tests`
- Run frontend tests: `cd apps/web && npm test`
- Run frontend lint/build: `cd apps/web && npm run lint && npm run build`
- Confirm `/ready` succeeds against the production database.
- Confirm demo credentials are not presented as production credentials.
- Confirm CORS only includes trusted frontend origins.
- Confirm AI provider keys are stored as secrets.
- Confirm Gemini quota behavior before a live presentation.
- Confirm mock fallback appears when `GEMINI_API_KEY` is missing or quota is exhausted.

## Current Product Hardening Backlog

- Replace seeded/demo users with a real user provisioning flow or SSO.
- Add password reset, account lockout, and audit views for auth events.
- Add structured logging and request correlation IDs.
- Add hosted file ingestion for knowledge documents.
- Add real channel connectors with webhook signature verification.
- Add vector embeddings for retrieval quality at production scale.
- Add SLA jobs and notification delivery through a queue.
- Add per-tenant data isolation tests before multi-tenant rollout.
