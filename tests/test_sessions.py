from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_create_session():
    res = client.post("/api/sessions", json={"workflow_title": "Invoice Processing", "expert_name": "Demo"})
    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data
    assert data["status"] == "created"


def test_pause_offrecord_finish_flow():
    res = client.post("/api/sessions", json={"workflow_title": "Test", "expert_name": "X"})
    sid = res.json()["session_id"]

    client.post(f"/api/sessions/{sid}/start")
    res = client.post(f"/api/sessions/{sid}/pause")
    assert res.status_code == 200
    assert res.json()["status"] == "paused"

    res = client.post(f"/api/sessions/{sid}/off-record")
    assert res.status_code == 200
    assert res.json()["status"] == "off_record"

    res = client.post(f"/api/sessions/{sid}/resume")
    assert res.status_code == 200
    assert res.json()["status"] == "capturing"

    res = client.post(f"/api/sessions/{sid}/finish")
    assert res.status_code == 200
    assert res.json()["status"] in ("finishing", "finished")

    res2 = client.post(f"/api/sessions/{sid}/finish")
    assert res2.status_code == 200
