import json
from typing import Any


QUESTION_TYPES = ["rationale", "boundary", "guardrail", "exception", "alternative"]


def _event_data(obj: Any) -> dict:
    data = getattr(obj, "data", None)
    return data if isinstance(data, dict) else {}


def _event_type(obj: Any) -> str:
    return getattr(obj, "type", "") or ""


def _fmt_amount(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"
    return str(value)


def _json_block(payload: Any) -> str:
    return json.dumps(payload, default=str)


def _summarize_events(events: list[Any], limit: int = 10) -> list[dict[str, Any]]:
    return [
        {
            "id": getattr(event, "id", None),
            "type": _event_type(event),
            "data": _event_data(event),
            "timestamp_ms": getattr(event, "timestamp_ms", None),
        }
        for event in list(events)[-limit:]
    ]


def _summarize_segments(segments: list[Any], limit: int = 6) -> list[dict[str, Any]]:
    return [
        {"speaker": getattr(seg, "speaker", ""), "text": getattr(seg, "text", "")}
        for seg in list(segments)[-limit:]
    ]


def _validate_decide(raw: Any, events: list[Any]) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    if raw.get("should_ask") is False:
        return {
            "should_ask": False,
            "question_type": "rationale",
            "question": "",
            "trigger_event_id": None,
            "rationale_for_internal_logging": raw.get("rationale_for_internal_logging") or "llm_no_ask",
        }
    if raw.get("should_ask") is not True:
        return None
    question_type = raw.get("question_type")
    question = raw.get("question")
    if question_type not in QUESTION_TYPES or not isinstance(question, str) or not question.strip():
        return None
    event_ids = {getattr(event, "id", None) for event in events}
    trigger = raw.get("trigger_event_id")
    if trigger not in event_ids:
        trigger = None
    return {
        "should_ask": True,
        "question_type": question_type,
        "question": question.strip(),
        "trigger_event_id": trigger,
        "rationale_for_internal_logging": raw.get("rationale_for_internal_logging") or "llm",
    }


def _validate_debrief(raw: Any, events: list[Any], count: int) -> list[dict[str, Any]] | None:
    if isinstance(raw, dict):
        items = raw.get("questions")
    elif isinstance(raw, list):
        items = raw
    else:
        return None
    if not isinstance(items, list):
        return None
    event_ids = {getattr(event, "id", None) for event in events}
    result: list[dict[str, Any]] = []
    seen_types: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        question_type = item.get("question_type")
        question = item.get("question")
        if question_type not in QUESTION_TYPES or question_type in seen_types:
            continue
        if not isinstance(question, str) or not question.strip():
            continue
        seen_types.add(question_type)
        trigger = item.get("trigger_event_id")
        result.append(
            {
                "question_type": question_type,
                "question": question.strip(),
                "trigger_event_id": trigger if trigger in event_ids else None,
                "rationale_for_internal_logging": item.get("rationale_for_internal_logging") or "llm",
            }
        )
        if len(result) >= count:
            break
    return result or None


class QuestionPolicyService:
    def __init__(self, llm: Any = None):
        if llm is not None:
            self.llm = llm
        else:
            from app.services.llm import LLMClient

            self.llm = LLMClient()

    def decide(
        self,
        events: list[Any],
        segments: list[Any],
        questions_asked: int = 0,
        budget: int = 5,
        paused: bool = False,
    ) -> dict[str, Any]:
        if questions_asked < budget and (events or segments):
            result = self._decide_llm(events, segments, questions_asked, budget, paused)
            if result is not None:
                return result
        return self._decide_deterministic(events, segments, questions_asked, budget, paused)

    def debrief(self, events: list[Any], segments: list[Any], count: int = 3) -> list[dict[str, Any]]:
        llm_result = self._debrief_llm(events, segments, count) if (events or segments) else None
        deterministic = self._debrief_deterministic(events, segments, count)
        if not llm_result:
            return deterministic
        if len(llm_result) >= count:
            return llm_result[:count]
        merged = list(llm_result)
        seen_types = {q["question_type"] for q in merged}
        for question in deterministic:
            if len(merged) >= count:
                break
            if question["question_type"] in seen_types:
                continue
            seen_types.add(question["question_type"])
            merged.append(question)
        for question in deterministic:
            if len(merged) >= count:
                break
            if question not in merged:
                merged.append(question)
        return merged[:count]

    def _decide_llm(
        self,
        events: list[Any],
        segments: list[Any],
        questions_asked: int,
        budget: int,
        paused: bool,
    ) -> dict[str, Any] | None:
        if not getattr(self.llm, "configured", False):
            return None
        system = (
            "You are an expert interviewer observing someone perform a workflow. Stay silent during "
            "routine work and ask one concise question only at a meaningful decision point or pause. "
            "Question types: rationale (why did you change this), boundary (when would you not do this), "
            "guardrail (when should you stop and escalate), exception (what changes for this case), "
            "alternative (what if the value were different). "
            "Respond with strict JSON only, no prose, matching: "
            '{"should_ask": bool, "question_type": one of '
            '["rationale","boundary","guardrail","exception","alternative"], "question": string, '
            '"trigger_event_id": string|null, "rationale_for_internal_logging": string}. '
            "Do not reveal internal reasoning to the user; put it only in rationale_for_internal_logging."
        )
        user = _json_block(
            {
                "questions_asked": questions_asked,
                "question_budget": budget,
                "session_paused": paused,
                "recent_events": _summarize_events(events, limit=10),
                "recent_transcript": _summarize_segments(segments, limit=6),
            }
        )
        raw = self.llm.complete_json(system, user, max_tokens=400)
        return _validate_decide(raw, events)

    def _debrief_llm(self, events: list[Any], segments: list[Any], count: int) -> list[dict[str, Any]] | None:
        if not getattr(self.llm, "configured", False):
            return None
        system = (
            "You are an expert interviewer preparing a debrief. From the captured events and transcript, "
            "write follow-up questions that surface high-impact uncertainties or missing guardrails. "
            "Prefer questions about rationale for decisions, decision boundaries, exceptions, and "
            "when to stop or escalate. Avoid generic questions and avoid duplicates. "
            "Question types: rationale, boundary, guardrail, exception, alternative. "
            "Respond with strict JSON only, no prose, matching: "
            '{"questions": [{"question_type": string, "question": string, '
            '"trigger_event_id": string|null, "rationale_for_internal_logging": string}]}.'
        )
        user = _json_block(
            {
                "requested_count": count,
                "events": _summarize_events(events, limit=40),
                "transcript": _summarize_segments(segments, limit=20),
            }
        )
        raw = self.llm.complete_json(system, user, max_tokens=1024)
        return _validate_debrief(raw, events, count)

    def _decide_deterministic(
        self,
        events: list[Any],
        segments: list[Any],
        questions_asked: int = 0,
        budget: int = 5,
        paused: bool = False,
    ) -> dict[str, Any]:
        if questions_asked >= budget:
            return {
                "should_ask": False,
                "question_type": "rationale",
                "question": "",
                "trigger_event_id": None,
                "rationale_for_internal_logging": "budget_exceeded",
            }
        if not events and not segments:
            return {
                "should_ask": False,
                "question_type": "rationale",
                "question": "",
                "trigger_event_id": None,
                "rationale_for_internal_logging": "no_context",
            }

        last_event = events[-1] if events else None
        if last_event is not None:
            etype = _event_type(last_event)
            data = _event_data(last_event)
            if etype == "field_changed":
                if data.get("field") == "cost_center":
                    return {
                        "should_ask": True,
                        "question_type": "rationale",
                        "question": f"Why did you set cost center to {data.get('new_value')} for this invoice?",
                        "trigger_event_id": getattr(last_event, "id", None),
                        "rationale_for_internal_logging": "cost_center_change",
                    }
                if data.get("field") in ("amount", "total"):
                    return {
                        "should_ask": True,
                        "question_type": "boundary",
                        "question": "When would an amount be small enough that you would not capitalize it?",
                        "trigger_event_id": getattr(last_event, "id", None),
                        "rationale_for_internal_logging": "amount_change",
                    }
            if etype == "asset_number_entered":
                return {
                    "should_ask": True,
                    "question_type": "rationale",
                    "question": "How did you decide this invoice needed an asset number?",
                    "trigger_event_id": getattr(last_event, "id", None),
                    "rationale_for_internal_logging": "asset_number_entered",
                }
            if etype == "supplier_history_viewed":
                return {
                    "should_ask": True,
                    "question_type": "exception",
                    "question": "What did the supplier history tell you, and what would change for a new supplier?",
                    "trigger_event_id": getattr(last_event, "id", None),
                    "rationale_for_internal_logging": "supplier_history_viewed",
                }
            if etype == "save_attempted":
                return {
                    "should_ask": True,
                    "question_type": "guardrail",
                    "question": "What conditions would require you to stop and escalate before saving?",
                    "trigger_event_id": getattr(last_event, "id", None),
                    "rationale_for_internal_logging": "save_attempt",
                }

        for seg in reversed(segments):
            text = (getattr(seg, "text", "") or "").lower()
            if "threshold" in text:
                return {
                    "should_ask": True,
                    "question_type": "boundary",
                    "question": "When would an amount fall below this threshold and not be capitalized?",
                    "trigger_event_id": None,
                    "rationale_for_internal_logging": "threshold_mentioned",
                }
            if "escalat" in text or "approval" in text:
                return {
                    "should_ask": True,
                    "question_type": "guardrail",
                    "question": "Who approves the escalation, and what evidence do they need?",
                    "trigger_event_id": None,
                    "rationale_for_internal_logging": "escalation_mentioned",
                }

        return {
            "should_ask": False,
            "question_type": "rationale",
            "question": "",
            "trigger_event_id": None,
            "rationale_for_internal_logging": "default",
        }

    def _debrief_deterministic(
        self, events: list[Any], segments: list[Any], count: int = 3
    ) -> list[dict[str, Any]]:
        amount: Any = None
        supplier: Any = None
        cost_center: Any = None
        asset_number: Any = None
        supplier_event = None
        save_event = None

        for ev in events:
            etype = _event_type(ev)
            data = _event_data(ev)
            if etype == "invoice_opened":
                amount = data.get("amount", amount)
                supplier = data.get("supplier", supplier)
            elif etype == "supplier_history_viewed":
                supplier = data.get("supplier", supplier)
                supplier_event = ev
            elif etype == "field_changed":
                if data.get("field") == "cost_center":
                    cost_center = data.get("new_value", cost_center)
            elif etype == "asset_number_entered":
                asset_number = data.get("new_value", asset_number)
            elif etype == "save_attempted":
                save_event = ev
                amount = data.get("amount", amount)
                cost_center = data.get("cost_center", cost_center)
                asset_number = data.get("asset_number", asset_number)

        candidates: list[dict[str, Any]] = []

        if save_event is not None:
            candidates.append(
                {
                    "question_type": "guardrail",
                    "question": "When this invoice is ready to save, what would make you stop and escalate to a human instead?",
                    "trigger_event_id": getattr(save_event, "id", None),
                    "rationale_for_internal_logging": "save_attempt_escalation",
                }
            )
        if asset_number:
            candidates.append(
                {
                    "question_type": "rationale",
                    "question": f"You added asset number {asset_number}. How did you decide this invoice needed to be capitalized?",
                    "trigger_event_id": None,
                    "rationale_for_internal_logging": "asset_number_rationale",
                }
            )
        if cost_center:
            candidates.append(
                {
                    "question_type": "rationale",
                    "question": f"You posted this invoice to cost center {cost_center}. What made that the right account rather than another one?",
                    "trigger_event_id": None,
                    "rationale_for_internal_logging": "cost_center_rationale",
                }
            )
        if supplier:
            candidates.append(
                {
                    "question_type": "exception",
                    "question": f"Your review of {supplier} shaped this decision. What changes if it is a brand-new supplier with no history?",
                    "trigger_event_id": getattr(supplier_event, "id", None) if supplier_event else None,
                    "rationale_for_internal_logging": "supplier_exception",
                }
            )
        if amount is not None:
            candidates.append(
                {
                    "question_type": "boundary",
                    "question": f"This invoice is {_fmt_amount(amount)}. What is your capitalization threshold, and what would you do just below it?",
                    "trigger_event_id": None,
                    "rationale_for_internal_logging": "amount_boundary",
                }
            )
        candidates.append(
            {
                "question_type": "guardrail",
                "question": "Which situations in this workflow must never be approved automatically?",
                "trigger_event_id": None,
                "rationale_for_internal_logging": "missing_guardrail",
            }
        )
        candidates.append(
            {
                "question_type": "alternative",
                "question": "If the amount were halved, would your process change, and how?",
                "trigger_event_id": None,
                "rationale_for_internal_logging": "alternative_amount",
            }
        )
        candidates.append(
            {
                "question_type": "exception",
                "question": "What is the most common exception you hit, and how do you resolve it?",
                "trigger_event_id": None,
                "rationale_for_internal_logging": "common_exception",
            }
        )

        seen_types: set[str] = set()
        result: list[dict[str, Any]] = []
        for candidate in candidates:
            if candidate["question_type"] in seen_types:
                continue
            seen_types.add(candidate["question_type"])
            result.append(candidate)
            if len(result) >= count:
                break

        if len(result) < count:
            for candidate in candidates:
                if candidate not in result:
                    result.append(candidate)
                if len(result) >= count:
                    break

        return result[:count]
