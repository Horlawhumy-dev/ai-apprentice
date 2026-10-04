QUESTION_TYPES = ["rationale", "boundary", "guardrail", "exception", "alternative"]


def decide_question(context: dict) -> dict:
    return {
        "should_ask": False,
        "question_type": "rationale",
        "question": "",
        "trigger_event_id": context.get("last_event_id"),
        "rationale_for_internal_logging": "no trigger",
    }
