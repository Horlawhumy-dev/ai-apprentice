from typing import Any

from app.services.guardrails import GuardrailService


class TutorService:
    def __init__(self, db: Any | None = None):
        self.db = db
        self.gr = GuardrailService()

    def evaluate(self, action: str, case_data: dict[str, Any]) -> dict[str, Any]:
        return self.gr.evaluate(action, case_data)
