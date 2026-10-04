import json
from typing import Any

import httpx

from app.core.config import settings


class LLMClient:
    """Thin Anthropic Messages API client that returns parsed JSON.

    Any failure (not configured, HTTP error, timeout, malformed JSON) returns None so
    callers can fall back to deterministic behavior. Never raises into request handlers.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        workspace_id: str | None = None,
        timeout: float = 6.0,
    ):
        self.api_key = settings.llm_api_key if api_key is None else api_key
        self.base_url = (base_url or settings.llm_base_url or "https://api.anthropic.com").rstrip("/")
        self.model = model or settings.llm_model
        self.workspace_id = settings.llm_workspace_id if workspace_id is None else workspace_id
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def complete_json(self, system: str, user: str, max_tokens: int = 1024) -> dict[str, Any] | list[Any] | None:
        if not self.configured:
            return None
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        if self.workspace_id:
            headers["anthropic-workspace-id"] = self.workspace_id
        try:
            response = httpx.post(
                f"{self.base_url}/v1/messages",
                headers=headers,
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
                timeout=self.timeout,
            )
            if response.status_code != 200:
                return None
            payload = response.json()
            text = "".join(
                block.get("text", "")
                for block in payload.get("content", [])
                if block.get("type") == "text"
            )
            return _extract_json(text)
        except Exception:
            return None


def _extract_json(text: str) -> Any | None:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text[3:]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip("` \n")
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start : end + 1])
    except Exception:
        return None
