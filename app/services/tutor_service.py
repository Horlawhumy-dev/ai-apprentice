from typing import Any

from app.services.guardrails import GuardrailService


class TutorService:
    def __init__(self, db: Any | None = None, guardrails: GuardrailService | None = None):
        self.db = db
        self.gr = guardrails if guardrails is not None else GuardrailService()

    def evaluate(
        self,
        action: str,
        case_data: dict[str, Any],
        guardrails: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return self.gr.evaluate(action, case_data, guardrails)