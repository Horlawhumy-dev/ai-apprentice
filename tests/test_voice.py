from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def _create_session():
    res = client.post("/api/sessions", json={"workflow_title": "Invoice Processing", "expert_name": "Demo Expert"})
    assert res.status_code == 200
    return res.json()["session_id"]


def _segment(source: str):
    return {
        "segment_id": str(uuid4()),
        "timestamp_ms": 1000,
        "speaker": "expert",
        "text": "Above the capitalization threshold, so this needs an asset number.",
        "source": source,
    }


def test_voice_config_reports_prototype_when_unconfigured():
    res = client.get("/api/voice/config")
    assert res.status_code == 200
    body = res.json()
    assert body["configured"] is False
    assert body["provider"] == "prototype"
    assert body["mode"] == "manual_transcript"


def test_voice_config_never_exposes_agent_id_or_api_key():
    body = client.get("/api/voice/config").json()
    assert "agent_id" not in body
    assert "api_key" not in body


def test_voice_token_is_503_when_unconfigured():
    res = client.post("/api/voice/token")
    assert res.status_code == 503


def test_transcript_accepts_known_sources():
    sid = _create_session()
    client.post(f"/api/sessions/{sid}/start")
    for source in ("voice_provider", "prototype_transcript"):
        res = client.post(f"/api/sessions/{sid}/transcript", json=_segment(source))
        assert res.status_code == 200, source
        assert res.json()["speaker"] == "expert"


def test_transcript_rejects_unknown_source():
    sid = _create_session()
    client.post(f"/api/sessions/{sid}/start")
    res = client.post(f"/api/sessions/{sid}/transcript", json=_segment("mystery_source"))
    assert res.status_code == 422


def test_transcript_still_gated_by_off_record():
    sid = _create_session()
    client.post(f"/api/sessions/{sid}/start")
    client.post(f"/api/sessions/{sid}/off-record")
    res = client.post(f"/api/sessions/{sid}/transcript", json=_segment("voice_provider"))
    assert res.status_code == 400


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_voice_token_mints_signed_url_and_keeps_the_key_server_side(monkeypatch):
    captured = {}

    async def fake_get(self, url, params=None, headers=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return _FakeResponse({"signed_url": "wss://example.invalid/conversation?signature=abc"})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(settings, "elevenlabs_api_key", "sk-test-secret")
    monkeypatch.setattr(settings, "elevenlabs_agent_id", "agent_123")

    res = client.post("/api/voice/token")

    assert res.status_code == 200
    body = res.json()
    assert body["signed_url"] == "wss://example.invalid/conversation?signature=abc"
    assert body["expires_in"] == 900
    assert captured["url"].endswith("/v1/convai/conversation/get-signed-url")
    assert captured["headers"]["xi-api-key"] == "sk-test-secret"
    assert captured["params"]["agent_id"] == "agent_123"
    assert "sk-test-secret" not in res.text
    assert "agent_123" not in res.text


def test_voice_token_surfaces_provider_failure_as_502(monkeypatch):
    async def fake_get(self, url, params=None, headers=None):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr(settings, "elevenlabs_api_key", "sk-test-secret")
    monkeypatch.setattr(settings, "elevenlabs_agent_id", "agent_123")

    res = client.post("/api/voice/token")
    assert res.status_code == 502