import os

import pytest

os.environ["DATABASE_URL"] = "sqlite:///./test_journeysync.db"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["AI_PROVIDER"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402
from app.database import sqlalchemy_url  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_database  # noqa: E402


client = TestClient(app)


def setup_module():
    seed_database(reset=True)


def token(email="agent@journeysync.demo", password="Agent123!"):
    res = client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()["access_token"]


def headers():
    return {"Authorization": f"Bearer {token()}"}


def auth_headers(access_token: str):
    return {"Authorization": f"Bearer {access_token}"}


def test_auth_and_role_authorization():
    assert client.post("/auth/login", json={"email": "agent@journeysync.demo", "password": "bad"}).status_code == 401
    assert client.get("/users", headers=headers()).status_code == 403
    admin = token("admin@journeysync.demo", "Admin123!")
    assert client.get("/users", headers={"Authorization": f"Bearer {admin}"}).status_code == 200


def test_health_reports_provider_status():
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "healthy"
    assert "configured_provider" in body
    assert "active_provider" in body
    assert "fallback_active" in body
    assert "database_mode" in body


def test_readiness_checks_database():
    res = client.get("/ready")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"


def test_production_settings_require_safe_values():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(
            environment="production",
            database_url="postgresql+psycopg://user:pass@db:5432/app",
            jwt_secret="local-demo-secret",
            seed_demo_data=False,
        )
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings(environment="production", database_url="sqlite:///./app.db", jwt_secret="prod-secret", seed_demo_data=False)
    with pytest.raises(ValueError, match="SEED_DEMO_DATA"):
        Settings(
            environment="production",
            database_url="postgresql+psycopg://user:pass@db:5432/app",
            jwt_secret="prod-secret",
            seed_demo_data=True,
        )


def test_plain_postgresql_url_uses_installed_psycopg_driver():
    assert sqlalchemy_url("postgresql://user:pass@db:5432/app") == "postgresql+psycopg://user:pass@db:5432/app"
    assert sqlalchemy_url("postgresql+psycopg://user:pass@db:5432/app") == "postgresql+psycopg://user:pass@db:5432/app"


def test_signup_invite_and_tenant_isolation():
    signup = client.post(
        "/auth/signup",
        json={
            "organization_name": "Acme CX",
            "name": "Acme Admin",
            "email": "admin@acme.example",
            "password": "StrongPass123!",
        },
    )
    assert signup.status_code == 200
    acme_token = signup.json()["access_token"]
    acme_headers = auth_headers(acme_token)
    assert signup.json()["organization"]["slug"] == "acme-cx"

    invited = client.post(
        "/users/invite",
        headers=acme_headers,
        json={
            "email": "agent@acme.example",
            "name": "Acme Agent",
            "role": "agent",
            "temporary_password": "TempPass123!",
        },
    )
    assert invited.status_code == 200
    assert invited.json()["organization_id"] == signup.json()["organization"]["id"]

    acme_users = client.get("/users", headers=acme_headers).json()
    assert {u["email"] for u in acme_users} == {"admin@acme.example", "agent@acme.example"}

    demo_customer = client.get("/customers", headers=headers()).json()[0]
    blocked_customer = client.get(f"/customers/{demo_customer['id']}", headers=acme_headers)
    assert blocked_customer.status_code == 404

    doc = client.post(
        "/knowledge",
        headers=acme_headers,
        json={"title": "Moonbase Returns", "content": "Moonbase warranty claims require orbital logistics approval."},
    )
    assert doc.status_code == 200
    assert client.get("/knowledge/search?q=moonbase", headers=acme_headers).json()[0]["title"] == "Moonbase Returns"
    assert client.get("/knowledge/search?q=moonbase", headers=headers()).json() == []


def test_customer_timeline_retrieval():
    customers = client.get("/customers", headers=headers()).json()
    res = client.get(f"/customers/{customers[0]['id']}/timeline", headers=headers())
    assert res.status_code == 200
    assert len(res.json()["events"]) >= 4


def test_message_creation_and_ai_validation():
    customer = client.get("/customers", headers=headers()).json()[0]
    res = client.post("/messages", headers=headers(), json={"customer_id": customer["id"], "channel": "email", "body": "This is urgent, my delivered product is damaged."})
    assert res.status_code == 200
    assert res.json()["analysis"]["intent"] == "damaged_order"
    assert res.json()["analysis"]["confidence"] <= 1


def test_knowledge_retrieval_fallback():
    res = client.get("/knowledge/search?q=damaged replacement", headers=headers())
    assert res.status_code == 200
    assert res.json()[0]["title"] in {"Damaged Orders", "Product Returns"}


def test_routing_rules_and_analytics():
    conv = client.get("/conversations", headers=headers()).json()[0]
    route = client.post(f"/routing/decide/{conv['id']}", headers=headers())
    assert route.status_code == 200
    assert route.json()["department"]
    metrics = client.get("/analytics/summary", headers=headers()).json()
    assert metrics["open_tickets"] >= 1


def test_human_approval_workflow_and_audit():
    conv = client.get("/conversations", headers=headers()).json()[0]
    detail = client.get(f"/conversations/{conv['id']}", headers=headers()).json()
    suggestion_id = detail["ai_suggestion"]["id"]
    res = client.post(f"/ai/suggestions/{suggestion_id}/approve", headers=headers(), json={"edited_response": "Edited empathetic response."})
    assert res.status_code == 200
    audit = client.get("/audit", headers=headers()).json()
    assert any(item["action"] == "ai_suggestion_approved" for item in audit)


def test_real_provider_failure_falls_back_to_mock(monkeypatch):
    from app.config import settings
    from app.database import SessionLocal
    from app.models import Customer
    from app.services import analyze_text

    monkeypatch.setattr(settings, "ai_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_base_url", "http://127.0.0.1:9")
    db = SessionLocal()
    try:
        customer = db.query(Customer).first()
        analysis = analyze_text(db, "My product arrived damaged and this is urgent.", customer)
    finally:
        db.close()
    assert analysis.intent == "damaged_order"
    assert analysis.urgency == "high"


def test_gemini_provider_missing_key_falls_back_to_mock(monkeypatch):
    from app.config import settings
    from app.database import SessionLocal
    from app.models import Customer
    from app.services import analyze_text

    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", "")
    db = SessionLocal()
    try:
        customer = db.query(Customer).first()
        analysis = analyze_text(db, "My order arrived broken and I need a replacement today.", customer)
    finally:
        db.close()
    assert analysis.intent == "damaged_order"
    assert analysis.urgency == "high"
