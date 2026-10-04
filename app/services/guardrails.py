import json
import logging
from typing import Any

from app.services.llm import LLMClient

log = logging.getLogger(__name__)


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return True


def _matches(actual: Any, expected: Any) -> bool:
    """Equality that treats numeric strings and numbers as equal, because event
    payloads routinely carry "5000" where a rule says 5000."""
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            return float(actual) == float(expected)
        except (TypeError, ValueError):
            return False
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.strip().lower() == expected.strip().lower()
    return actual == expected


def _check_condition(condition: dict[str, Any], case_data: dict[str, Any]) -> tuple[bool, str]:
    """Evaluate a machine-checkable guardrail condition.

    Returns (violated, reason). Supports:
      when           - all key/value pairs must match the case data
      requires_fields- listed fields must be present and non-empty
      forbids_values - {field: [disallowed, ...]}
    """
    for field, expected in (condition.get("when") or {}).items():
        if not _matches(case_data.get(field), expected):
            return False, ""

    missing = [
        field
        for field in (condition.get("requires_fields") or [])
        if not _present(case_data.get(field))
    ]
    if missing:
        return True, f"missing required value for: {', '.join(missing)}"

    for field, disallowed in (condition.get("forbids_values") or {}).items():
        actual = case_data.get(field)
        if isinstance(disallowed, list) and any(_matches(actual, bad) for bad in disallowed):
            return True, f"{field} is set to a disallowed value ({actual})"

    return False, ""


class GuardrailService:
    """Evaluates an action against the guardrails captured for its own workflow.

    Guardrails are data, not code: they are produced during Map (from the expert's
    captured decisions, then confirmed) and stored on the work map. Nothing here is
    specific to a particular business domain.

    A guardrail carrying a `condition` is checked deterministically. A guardrail that
    is only natural language is adjudicated by the model, which must answer with the
    evidence it used. If no model is configured those rules cannot be adjudicated, so
    they are reported as unreviewed rather than silently treated as satisfied.
    """

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm if llm is not None else LLMClient()

    def evaluate(
        self,
        action: str,
        case_data: dict[str, Any],
        guardrails: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        rules = [g for g in (guardrails or []) if isinstance(g, dict)]
        if not rules:
            return _result(
                allowed=True,
                explanation="No guardrails are defined for this workflow yet, so nothing was blocked.",
            )

        for rule in rules:
            condition = rule.get("condition")
            if isinstance(condition, dict):
                violated, reason = _check_condition(condition, case_data)
                if violated:
                    return _block(rule, reason)

        pending = [r for r in rules if not isinstance(r.get("condition"), dict)]
        if not pending:
            return _result(
                allowed=True,
                explanation="All checkable guardrails passed.",
            )

        if not getattr(self.llm, "configured", False):
            return _result(
                allowed=True,
                severity="info",
                explanation=(
                    f"{len(pending)} guardrail(s) for this workflow are written in natural language and "
                    "need a model to adjudicate. Set LLM_API_KEY to have them reviewed."
                ),
                unreviewed=[r.get("rule_id") or r.get("rule") for r in pending],
            )

        return self._evaluate_with_llm(action, case_data, pending)

    def _evaluate_with_llm(
        self, action: str, case_data: dict[str, Any], rules: list[dict[str, Any]]
    ) -> dict[str, Any]:
        system = (
            "You enforce a company's workflow guardrails. Given the action a person is attempting "
            "and the data they supplied, decide whether it violates any of the guardrails. "
            "Judge only against the guardrails given; do not invent rules. "
            "Respond with strict JSON only: "
            '{"violated": bool, "rule_id": string|null, "explanation": string}. '
            "The explanation must state which guardrail was violated and cite the specific data."
        )
        user = json.dumps(
            {
                "action": action,
                "case_data": case_data,
                "guardrails": [
                    {"rule_id": r.get("rule_id"), "rule": r.get("rule"), "severity": r.get("severity")}
                    for r in rules
                ],
            }
        )
        raw = self.llm.complete_json(system, user, max_tokens=400)
        parsed = _parse_verdict(raw)
        if parsed is None:
            log.warning("Guardrail adjudication returned no usable verdict; allowing action")
            return _result(
                allowed=True,
                explanation="Guardrails could not be reviewed for this action, so it was allowed.",
                unreviewed=[r.get("rule_id") or r.get("rule") for r in rules],
            )

        if not parsed.get("violated"):
            return _result(
                allowed=True,
                explanation=parsed.get("explanation") or "No guardrail was violated.",
            )

        rule_id = parsed.get("rule_id")
        rule = next((r for r in rules if r.get("rule_id") == rule_id), None) if rule_id else None
        if rule is None:
            rule = next((r for r in rules if str(r.get("severity", "")).lower() == "block"), None)
        return _result(
            allowed=False,
            rule_id=rule_id,
            severity=(rule or {}).get("severity") or "warn",
            explanation=parsed.get("explanation") or "A guardrail was violated.",
            next_question=(rule or {}).get("next_question"),
        )


def _parse_verdict(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict) and "violated" in raw:
        return raw
    return None


def _result(
    allowed: bool,
    explanation: str,
    severity: str = "info",
    rule_id: str | None = None,
    next_question: str | None = None,
    unreviewed: list[Any] | None = None,
) -> dict[str, Any]:
    return {
        "allowed": allowed,
        "matched_rule_id": rule_id,
        "severity": severity,
        "explanation": explanation,
        "evidence_step_id": rule_id,
        "next_question": next_question,
        "unreviewed_rules": unreviewed or [],
    }


def _block(rule: dict[str, Any], reason: str) -> dict[str, Any]:
    severity = str(rule.get("severity") or "warn").lower()
    text = rule.get("rule") or "A guardrail for this workflow was not satisfied."
    explanation = f"{text} ({reason})" if reason else text
    # A "block" severity stops the action; a "warn" lets it through with an explanation.
    return _result(
        allowed=severity != "block",
        rule_id=rule.get("rule_id"),
        severity=severity,
        explanation=explanation,
        next_question=rule.get("next_question"),
    )