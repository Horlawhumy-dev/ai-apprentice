from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

WORKFLOW = "Incident Triage"


def _create_session(title=WORKFLOW):
    res = client.post("/api/sessions", json={"workflow_title": title, "expert_name": "Sam"})
    assert res.status_code == 200
    return res.json()["session_id"]


def _event(etype, data, ts, source="ticketing_app"):
    return {
        "client_event_id": str(uuid4()),
        "timestamp_ms": ts,
        "source": source,
        "type": etype,
        "data": data,
    }


def test_full_capture_map_teach_loop():
    """Capture -> Map -> Teach, driven entirely by the workflow's own data.

    Nothing here depends on a built-in business domain: the guardrail is supplied by
    the captured session and the case is supplied by the caller.
    """
    sid = _create_session()

    res = client.post(f"/api/sessions/{sid}/start")
    assert res.status_code == 200
    assert res.json()["status"] == "capturing"

    events = [
        _event("ticket_opened", {"ticket": "T-1", "severity": "high"}, 1000),
        _event(
            "field_changed",
            {
                "field": "queue",
                "old_value": "tier1",
                "new_value": "tier2",
                "decision": "tier2",
                "reason": "SLA for high severity is 15 minutes and tier1 was at capacity",
                "guardrails": [
                    {
                        "rule_id": "require_owner",
                        "rule": "Every reassignment needs a named owner",
                        "severity": "block",
                        "condition": {"requires_fields": ["owner"]},
                    }
                ],
            },
            2000,
        ),
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
            "text": "High severity goes straight to tier2 because tier1 was already at capacity.",
            "source": "voice_provider",
        },
    )
    assert res.status_code == 200

    res = client.post(f"/api/sessions/{sid}/questions/decide")
    assert res.status_code == 200

    # finish is idempotent
    assert client.post(f"/api/sessions/{sid}/finish").json()["status"] == "finished"
    assert client.post(f"/api/sessions/{sid}/finish").json()["status"] == "finished"

    wm = client.post(f"/api/sessions/{sid}/work-map/generate").json()
    assert wm["status"] == "needs_expert_review"
    assert {s["action"] for s in wm["steps"]} >= {"ticket_opened", "change_queue"}
    # Spoken reasoning is filed against the step the expert was on, not as its own
    # step, so every action carries its own justification and rules.
    assert not any(s["action"] == "transcript_note" for s in wm["steps"])
    assert all(s["reason"] for s in wm["steps"]), "each step should carry the expert's reasoning"

    # The machine-checkable rule the expert attached to the event is carried onto its
    # step. Spoken reasoning also becomes a rule (with a generated id), so select the
    # structured one the event supplied.
    guardrail_step = next(s for s in wm["steps"] if any("condition" in g for g in s["guardrails"]))
    rule = next(g for g in guardrail_step["guardrails"] if "condition" in g)
    assert rule["rule_id"] == "require_owner"
    assert rule["condition"] == {"requires_fields": ["owner"]}

    # Prose rules captured from speech are addressable too, so a violation can always
    # be traced back to the step that set the rule.
    assert all(g.get("rule_id") for s in wm["steps"] for g in s["guardrails"])

    res = client.patch(f"/api/workflows/{wm['id']}", json={"status": "confirmed"})
    assert res.json()["status"] == "confirmed"

    res = client.patch(
        f"/api/workflows/{wm['id']}/steps/{guardrail_step['id']}",
        json={"review_status": "confirmed"},
    )
    assert res.json()["review_status"] == "confirmed"

    # the unseen case is supplied by the caller, not looked up
    res = client.post(
        "/api/apprentice/sessions",
        json={
            "workflow_id": wm["id"],
            "case_id": "case_t2_backlog",
            "case_data": {"ticket": "T-2", "severity": "high", "queue": "tier2"},
        },
    )
    assert res.status_code == 200
    aid = res.json()["id"]
    assert res.json()["case"]["case_id"] == "case_t2_backlog"
    assert res.json()["case"]["severity"] == "high"

    # missing required owner -> blocked, linked back to the step that defined the rule
    blocked = client.post(
        f"/api/apprentice/sessions/{aid}/evaluate",
        json={"action": "change_queue", "case_data": {"owner": ""}},
    ).json()
    assert blocked["allowed"] is False
    assert blocked["matched_rule_id"] == "require_owner"
    assert blocked["evidence"]["action"] == guardrail_step["action"]

    # owner supplied -> allowed
    allowed = client.post(
        f"/api/apprentice/sessions/{aid}/evaluate",
        json={"action": "change_queue", "case_data": {"owner": "dana"}},
    ).json()
    assert allowed["allowed"] is True

    summary = client.post(f"/api/apprentice/sessions/{aid}/finish").json()
    assert summary["summary"]["attempts"] == 2
    assert summary["summary"]["blocked"] == 1
    assert summary["summary"]["allowed"] == 1


def test_workflow_without_guardrails_blocks_nothing():
    """A workflow with no captured guardrails must not invent any."""
    sid = _create_session("Fleet Telemetry Review")
    client.post(f"/api/sessions/{sid}/start")
    client.post(f"/api/sessions/{sid}/events", json=_event("ping", {}, 10))
    client.post(f"/api/sessions/{sid}/finish")
    wm = client.post(f"/api/sessions/{sid}/work-map/generate").json()

    aid = client.post(
        "/api/apprentice/sessions",
        json={"workflow_id": wm["id"], "case_id": "c1", "case_data": {"x": 1}},
    ).json()["id"]

    res = client.post(
        f"/api/apprentice/sessions/{aid}/evaluate",
        json={"action": "anything", "case_data": {}},
    ).json()
    assert res["allowed"] is True
    assert res["matched_rule_id"] is None


def test_off_record_blocks_capture_and_excludes_events():
    sid = _create_session()
    client.post(f"/api/sessions/{sid}/start")
    client.post(f"/api/sessions/{sid}/off-record")
    res = client.post(f"/api/sessions/{sid}/events", json=_event("field_changed", {}, 10))
    assert res.status_code == 400

    # resume and add an on-record event
    client.post(f"/api/sessions/{sid}/resume")
    client.post(f"/api/sessions/{sid}/events", json=_event("ticket_opened", {}, 20))
    client.post(f"/api/sessions/{sid}/finish")
    wm = client.post(f"/api/sessions/{sid}/work-map/generate").json()
    client_ids = [e for s in wm["steps"] for e in s["evidence"].get("event_ids", [])]
    # exactly one on-record event should have made it into the map
    assert len(client_ids) == 1