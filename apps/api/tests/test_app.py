import os

os.environ["DATABASE_URL"] = "sqlite:///./test_journeysync.db"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["AI_PROVIDER"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402

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
