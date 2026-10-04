from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _create_session():
    res = client.post("/api/sessions", json={"workflow_title": "Invoice Processing", "expert_name": "Demo Expert"})
    assert res.status_code == 200
    return res.json()["session_id"]


def test_full_capture_map_teach_loop():
    sid = _create_session()

    res = client.post(f"/api/sessions/{sid}/start")
    assert res.status_code == 200
    assert res.json()["status"] == "capturing"

    events = [
        {
            "client_event_id": str(uuid4()),
            "timestamp_ms": 1000,
            "source": "demo_erp",
            "type": "invoice_opened",
            "data": {"invoice_id": "INV-4471", "amount": 7200},
        },
        {
            "client_event_id": str(uuid4()),
            "timestamp_ms": 2000,
            "source": "demo_erp",
            "type": "field_changed",
            "data": {"field": "cost_center", "old_value": "OPEX", "new_value": "CAPEX", "invoice_id": "INV-4471"},
        },
        {
            "client_event_id": str(uuid4()),
            "timestamp_ms": 3000,
            "source": "demo_erp",
            "type": "save_attempted",
            "data": {"invoice_id": "INV-4471", "asset_number": ""},
        },
    ]
    for ev in events:
        assert client.post(f"/api/sessions/{sid}/events", json=ev).status_code == 200

    # idempotent event submission
    assert client.post(f"/api/sessions/{sid}/events", json=events[0]).status_code == 200

    res = client.post(
        f"/api/sessions/{sid}/transcript",
        json={
            "segment_id": str(uuid4()),
            "timestamp_ms": 2500,
            "speaker": "expert",
            "text": "This equipment is above our capitalization threshold, so it needs an asset number.",
            "source": "voice_provider",
        },
    )
    assert res.status_code == 200

    # decisions/questions
    res = client.post(f"/api/sessions/{sid}/questions/decide")
    assert res.status_code == 200

    # finish is idempotent
    assert client.post(f"/api/sessions/{sid}/finish").json()["status"] == "finished"
    assert client.post(f"/api/sessions/{sid}/finish").json()["status"] == "finished"

    # work map generation
    wm = client.post(f"/api/sessions/{sid}/work-map/generate").json()
    assert wm["status"] == "needs_expert_review"
    actions = {s["action"] for s in wm["steps"]}
    assert "change_cost_center" in actions
    assert "require_asset_number" in actions

    guardrail_step = next(s for s in wm["steps"] if s["action"] == "require_asset_number")
    assert guardrail_step["guardrails"][0]["rule_id"] == "require_asset_number"
    assert guardrail_step["evidence"]["transcript_excerpts"], "guardrail step should link transcript evidence"

    # expert confirms the workflow
    res = client.patch(f"/api/workflows/{wm['id']}", json={"status": "confirmed"})
    assert res.json()["status"] == "confirmed"

    # confirm the guardrail step
    res = client.patch(
        f"/api/workflows/{wm['id']}/steps/{guardrail_step['id']}",
        json={"review_status": "confirmed"},
    )
    assert res.json()["review_status"] == "confirmed"

    # apprentice uses a different case that exercises the same rule
    res = client.post("/api/apprentice/sessions", json={"workflow_id": wm["id"], "case_id": "case_alpha"})
    assert res.status_code == 200
    asess = res.json()
    assert asess["case"]["title"] == "Invoice INV-5120"
    aid = asess["id"]

    # wrong: CAPEX above threshold with no asset number -> blocked with evidence link
    blocked = client.post(
        f"/api/apprentice/sessions/{aid}/evaluate",
        json={"action": "save_attempted", "case_data": {"asset_number": ""}},
    ).json()
    assert blocked["allowed"] is False
    assert blocked["matched_rule_id"] == "require_asset_number"
    assert blocked["evidence_step_id"] == guardrail_step["id"]
    assert blocked["evidence"]["action"] == "require_asset_number"

    # corrected: asset number supplied -> allowed
    allowed = client.post(
        f"/api/apprentice/sessions/{aid}/evaluate",
        json={"action": "save_attempted", "case_data": {"asset_number": "A-1001"}},
    ).json()
    assert allowed["allowed"] is True

    summary = client.post(f"/api/apprentice/sessions/{aid}/finish").json()
    assert summary["summary"]["attempts"] == 2
    assert summary["summary"]["blocked"] == 1
    assert summary["summary"]["allowed"] == 1


def test_off_record_blocks_capture_and_excludes_events():
    sid = _create_session()
    client.post(f"/api/sessions/{sid}/start")
    client.post(f"/api/sessions/{sid}/off-record")
    res = client.post(
        f"/api/sessions/{sid}/events",
        json={
            "client_event_id": str(uuid4()),
            "timestamp_ms": 10,
            "source": "demo_erp",
            "type": "field_changed",
            "data": {},
        },
    )
    assert res.status_code == 400

    # resume and add an on-record event
    client.post(f"/api/sessions/{sid}/resume")
    client.post(
        f"/api/sessions/{sid}/events",
        json={
            "client_event_id": str(uuid4()),
            "timestamp_ms": 20,
            "source": "demo_erp",
            "type": "invoice_opened",
            "data": {},
        },
    )
    client.post(f"/api/sessions/{sid}/finish")
    wm = client.post(f"/api/sessions/{sid}/work-map/generate").json()
    client_ids = [e for s in wm["steps"] for e in s["evidence"].get("event_ids", [])]
    # exactly one on-record event should have made it into the map
    assert len(client_ids) == 1
