import json
from typing import Any


QUESTION_TYPES = ["rationale", "boundary", "guardrail", "exception", "alternative"]


def _event_data(obj: Any) -> dict:
    data = getattr(obj, "data", None)
    return data if isinstance(data, dict) else {}


def _event_type(obj: Any) -> str:
    return getattr(obj, "type", "") or ""



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


def _corpus(events: list[Any], segments: list[Any]) -> str:
    """Everything the capture actually stated, as one searchable blob.

    A generated question is only accepted when the evidence it cites appears here, which
    is what stops the model inventing domain facts ("approved", "amount") that nobody
    ever captured.
    """
    parts: list[str] = []
    for event in events:
        parts.append(_event_type(event))
        parts.append(json.dumps(_event_data(event), default=str))
    for seg in segments:
        parts.append(getattr(seg, "text", "") or "")
    return "\n".join(parts).lower()


def _is_grounded(quote: Any, corpus: str) -> bool:
    # Long enough that a token like "the" cannot pass as evidence, short enough that a
    # real short phrase from the capture still counts.
    if not isinstance(quote, str) or len(quote.strip()) < 8:
        return False
    return quote.strip().lower() in corpus


def _validate_decide(raw: Any, events: list[Any], corpus: str = "") -> dict[str, Any] | None:
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
    # Nothing captured means nothing to be curious about; stay silent rather than invent.
    if not _is_grounded(raw.get("evidence_quote"), corpus):
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


def _validate_debrief(raw: Any, events: list[Any], count: int, corpus: str = "") -> list[dict[str, Any]] | None:
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
        # A question the capture cannot back up is discarded, not softened.
        if not _is_grounded(item.get("evidence_quote"), corpus):
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
        self._used_llm = False

    def decide(
        self,
        events: list[Any],
        segments: list[Any],
        questions_asked: int = 0,
        budget: int = 5,
        paused: bool = False,
        workflow_title: str = "",
    ) -> dict[str, Any]:
        result: dict[str, Any] | None = None
        if questions_asked < budget and (events or segments):
            result = self._decide_llm(events, segments, questions_asked, budget, paused, workflow_title)
        if result is None:
            result = self._decide_deterministic(
                events, segments, questions_asked, budget, paused, workflow_title
            )
        result["source"] = "llm" if self._used_llm else "deterministic"
        return result

    def debrief(
        self,
        events: list[Any],
        segments: list[Any],
        count: int = 3,
        workflow_title: str = "",
    ) -> list[dict[str, Any]]:
        llm_result = self._debrief_llm(events, segments, count, workflow_title) if (events or segments) else None
        deterministic = self._debrief_deterministic(events, segments, count, workflow_title)
        used_llm = bool(llm_result)
        if not llm_result:
            merged = deterministic
        elif len(llm_result) >= count:
            merged = llm_result[:count]
        else:
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
            merged = merged[:count]
        for question in merged:
            question["source"] = "llm" if used_llm else "deterministic"
        return merged

    def _decide_llm(
        self,
        events: list[Any],
        segments: list[Any],
        questions_asked: int,
        budget: int,
        paused: bool,
        workflow_title: str = "",
    ) -> dict[str, Any] | None:
        if not getattr(self.llm, "configured", False):
            self._used_llm = False
            return None
        system = (
            "You are an expert interviewer observing someone perform a workflow. Stay silent during "
            "routine work and ask one concise question only at a meaningful decision point or pause. "
            "Question types: rationale (why did you change this), boundary (when would you not do this), "
            "guardrail (when should you stop and escalate), exception (what changes for this case), "
            "alternative (what if the value were different). "
            "Ground every question in this specific workflow and the captured evidence. Use only vocabulary "
            "that appears in the evidence: never introduce a field, system, or concept the capture does not "
            "mention, and never reuse a generic template. "
            'Copy an "evidence_quote" verbatim from the events or transcript that the question depends on. '
            "If nothing in the capture supports a question, set should_ask to false instead of inventing one. "
            "Respond with strict JSON only, no prose, matching: "
            '{"should_ask": bool, "question_type": one of '
            '["rationale","boundary","guardrail","exception","alternative"], "question": string, '
            '"evidence_quote": string, '
            '"trigger_event_id": string|null, "rationale_for_internal_logging": string}. '
            "Do not reveal internal reasoning to the user; put it only in rationale_for_internal_logging."
        )
        user = _json_block(
            {
                "workflow": workflow_title or "(unspecified)",
                "questions_asked": questions_asked,
                "question_budget": budget,
                "session_paused": paused,
                "recent_events": _summarize_events(events, limit=10),
                "recent_transcript": _summarize_segments(segments, limit=6),
            }
        )
        raw = self.llm.complete_json(system, user, max_tokens=400)
        validated = _validate_decide(raw, events, _corpus(events, segments))
        self._used_llm = validated is not None
        return validated

    def _debrief_llm(
        self,
        events: list[Any],
        segments: list[Any],
        count: int,
        workflow_title: str = "",
    ) -> list[dict[str, Any]] | None:
        if not getattr(self.llm, "configured", False):
            self._used_llm = False
            return None
        system = (
            "You are an expert interviewer preparing a debrief. From the captured events and transcript, "
            "write follow-up questions that surface high-impact uncertainties or missing guardrails. "
            "Prefer questions about rationale for decisions, decision boundaries, exceptions, and "
            "when to stop or escalate. Avoid generic questions and avoid duplicates. "
            "Ground every question in this specific workflow and the evidence given. Use only vocabulary "
            "that appears in the evidence: never introduce a field, system, or concept the capture does not "
            "mention, and never reuse a generic template. "
            "Each question must carry an \"evidence_quote\" copied verbatim from the events or transcript. "
            "A question without a real quote is discarded, so never invent one. If the capture supports "
            "fewer questions than requested, return fewer rather than inventing detail. "
            "Question types: rationale, boundary, guardrail, exception, alternative. "
            "Respond with strict JSON only, no prose, matching: "
            '{"questions": [{"question_type": string, "question": string, "evidence_quote": string, '
            '"trigger_event_id": string|null, "rationale_for_internal_logging": string}]}.'
        )
        user = _json_block(
            {
                "workflow": workflow_title or "(unspecified)",
                "requested_count": count,
                "events": _summarize_events(events, limit=40),
                "transcript": _summarize_segments(segments, limit=20),
            }
        )
        raw = self.llm.complete_json(system, user, max_tokens=1024)
        validated = _validate_debrief(raw, events, count, _corpus(events, segments))
        self._used_llm = validated is not None
        return validated

    def _decide_deterministic(
        self,
        events: list[Any],
        segments: list[Any],
        questions_asked: int = 0,
        budget: int = 5,
        paused: bool = False,
        workflow_title: str = "",
    ) -> dict[str, Any]:
        self._used_llm = False
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

        # Without a model there is no domain knowledge to draw on, so only what the
        # capture itself states is safe to ask about. Anything else would assert facts
        # about a workflow we have not seen.
        last_event = events[-1] if events else None
        if last_event is not None:
            stated_reason = _event_data(last_event).get("reason")
            if isinstance(stated_reason, str) and stated_reason.strip():
                return {
                    "should_ask": True,
                    "question_type": "rationale",
                    "question": f"You recorded the reason \"{stated_reason.strip()}\". What drove that?",
                    "trigger_event_id": getattr(last_event, "id", None),
                    "rationale_for_internal_logging": "stated_reason",
                }

        for seg in reversed(segments):
            text = (getattr(seg, "text", "") or "").strip()
            if not text:
                continue
            lowered = text.lower()
            if any(word in lowered for word in ("escalat", "refer", "supervisor", "manager")):
                return {
                    "should_ask": True,
                    "question_type": "guardrail",
                    "question": f"You said \"{text}\" - what would you need in order to decide that on your own?",
                    "trigger_event_id": None,
                    "rationale_for_internal_logging": "referral_mentioned",
                }
            if any(word in lowered for word in ("threshold", "limit", "maximum", "minimum")):
                return {
                    "should_ask": True,
                    "question_type": "boundary",
                    "question": f"You mentioned \"{text}\" - where exactly is that line, and what changes on either side of it?",
                    "trigger_event_id": None,
                    "rationale_for_internal_logging": "threshold_mentioned",
                }

        # No usable evidence for a single question type, but the workflow itself is
        # known, so ask something grounded rather than staying silent or inventing
        # domain details.
        subject = workflow_title.strip() or "this step"
        return {
            "should_ask": True,
            "question_type": "rationale",
            "question": f"Walk me through how you approach {subject}.",
            "trigger_event_id": None,
            "rationale_for_internal_logging": "workflow_walkthrough",
        }

    def _debrief_deterministic(
        self,
        events: list[Any],
        segments: list[Any],
        count: int = 3,
        workflow_title: str = "",
    ) -> list[dict[str, Any]]:
        """Fallback debrief built only from what the capture itself states.

        Every candidate is anchored to a recorded reason, decision, or piece of spoken
        evidence, so no assumption is made about the business domain. When nothing was
        captured the result is a single grounded prompt rather than invented filler.
        """
        candidates: list[dict[str, Any]] = []

        for ev in events:
            data = _event_data(ev)
            reason = data.get("reason")
            decision = data.get("decision")
            if not (isinstance(reason, str) and reason.strip()):
                continue
            step_id = getattr(ev, "id", None)
            candidates.append(
                {
                    "question_type": "rationale",
                    "question": f"You recorded \"{reason.strip()}\" - what evidence drove that, and what would have led you elsewhere?",
                    "trigger_event_id": step_id,
                    "rationale_for_internal_logging": f"stated_reason:{step_id}",
                }
            )
            if decision not in (None, ""):
                candidates.append(
                    {
                        "question_type": "boundary",
                        "question": f"You settled on \"{decision}\" here. At what point would you choose differently?",
                        "trigger_event_id": step_id,
                        "rationale_for_internal_logging": f"stated_decision:{step_id}",
                    }
                )
            for rule in data.get("guardrails") or []:
                if isinstance(rule, dict) and rule.get("rule"):
                    candidates.append(
                        {
                            "question_type": "guardrail",
                            "question": f"You noted the rule \"{rule['rule']}\" - when does it apply, and who checks it?",
                            "trigger_event_id": step_id,
                            "rationale_for_internal_logging": f"stated_guardrail:{step_id}",
                        }
                    )

        for seg in segments:
            text = (getattr(seg, "text", "") or "").strip()
            if len(text) < 15:
                continue
            candidates.append(
                {
                    "question_type": "exception",
                    "question": f"You said \"{text[:160]}\" - how often does that happen, and what do you do about it?",
                    "trigger_event_id": None,
                    "rationale_for_internal_logging": "transcript_claim",
                }
            )

        subject = workflow_title.strip() or "this workflow"
        if not candidates:
            candidates.append(
                {
                    "question_type": "rationale",
                    "question": f"Nothing was captured to review yet. What is the first decision you would make during {subject}?",
                    "trigger_event_id": None,
                    "rationale_for_internal_logging": "empty_capture",
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
