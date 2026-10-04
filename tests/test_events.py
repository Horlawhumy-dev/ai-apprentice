from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_event_and_offrecord_rejection():
    res = client.post("/api/sessions", json={"workflow_title": "T", "expert_name": "E"})
    sid = res.json()["session_id"]
    client.post(f"/api/sessions/{sid}/start")
    client.post(f"/api/sessions/{sid}/off-record")
    res = client.post(
        f"/api/sessions/{sid}/events",
        json={
            "client_event_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp_ms": 1000,
            "source": "demo_erp",
            "type": "field_changed",
            "data": {},
        },
    )
    assert res.status_code == 400
