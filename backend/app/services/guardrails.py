from typing import Any

CAPITALIZATION_THRESHOLD = 5000


class GuardrailService:
    """Deterministic rules for the demo. These mirror expert-confirmed rules."""

    def evaluate(self, action: str, case_data: dict[str, Any]) -> dict[str, Any]:
        if action != "save_attempted":
            return {
                "allowed": True,
                "matched_rule_id": None,
                "severity": "info",
                "explanation": "Action permitted.",
                "evidence_step_id": None,
                "next_question": None,
            }

        cost_center = case_data.get("cost_center") or case_data.get("proposed_cost_center")
        amount = case_data.get("amount")
        asset_number = case_data.get("asset_number")

        is_capex = cost_center == "CAPEX"
        above_threshold = isinstance(amount, (int, float)) and amount >= CAPITALIZATION_THRESHOLD

        if is_capex and above_threshold and not asset_number:
            return {
                "allowed": False,
                "matched_rule_id": "require_asset_number",
                "severity": "block",
                "explanation": (
                    "Equipment above the capitalization threshold must have an asset number "
                    "before submission. Add an asset number or escalate to your supervisor."
                ),
                "evidence_step_id": "require_asset_number",
                "next_question": "What asset number should be recorded for this purchase?",
            }

        if (not is_capex) and above_threshold and asset_number:
            return {
                "allowed": False,
                "matched_rule_id": "capex_requires_capitalization",
                "severity": "warn",
                "explanation": (
                    "An asset number was entered for an above-threshold purchase recorded as OPEX. "
                    "Confirm whether this should be capitalized instead."
                ),
                "evidence_step_id": "capex_requires_capitalization",
                "next_question": "Does this purchase meet the capitalization policy?",
            }

        return {
            "allowed": True,
            "matched_rule_id": None,
            "severity": "info",
            "explanation": "No confirmed guardrail applies. Save permitted.",
            "evidence_step_id": None,
            "next_question": None,
        }
