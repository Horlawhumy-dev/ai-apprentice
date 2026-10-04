from types import SimpleNamespace as NS

from app.services.question_policy import QuestionPolicyService

# Vocabulary that belonged to the invoice demo and must never be asserted again.
INVOICE_WORDS = ("amount", "invoice", "supplier", "cost center", "capitaliz", "asset number")


def _event(eid, etype, data=None):
    return NS(id=eid, type=etype, data=data or {}, timestamp_ms=eid * 10)


def _seg(text):
    return NS(text=text, speaker="expert", timestamp_ms=99)


OFFLINE = NS(configured=False)


def test_debrief_fallback_never_asserts_unobserved_domain_facts():
    """Unrecognised events carry no decision, so nothing specific may be claimed."""
    events = [_event(1, "heartbeat"), _event(2, "ping")]
    questions = QuestionPolicyService(llm=OFFLINE).debrief(events, [], 3, workflow_title="Fleet Telemetry Review")
    for q in questions:
        assert not any(w in q["question"].lower() for w in INVOICE_WORDS), q["question"]


def test_debrief_fallback_asks_from_recorded_reasons():
    events = [_event(1, "field_changed", {"field": "queue", "new_value": "tier2",
                                           "decision": "tier2",
                                           "reason": "tier1 was at capacity"})]
    questions = QuestionPolicyService(llm=OFFLINE).debrief(events, [], 3, workflow_title="Incident Triage")
    joined = " ".join(q["question"] for q in questions)
    assert "tier1 was at capacity" in joined
    assert "tier2" in joined


def test_debrief_uses_guardrails_the_expert_recorded():
    events = [_event(1, "save_attempted", {"reason": "checked the runbook",
                                            "guardrails": [{"rule": "Escalate anything novel"}]})]
    questions = QuestionPolicyService(llm=OFFLINE).debrief(events, [], 3, workflow_title="Incident Triage")
    assert any("Escalate anything novel" in q["question"] for q in questions)


def test_debrief_with_nothing_captured_still_names_the_workflow():
    questions = QuestionPolicyService(llm=OFFLINE).debrief(
        [], [], 3, workflow_title="Fleet Telemetry Review"
    )
    assert questions
    assert all("Fleet Telemetry Review" in q["question"] for q in questions)


def test_debrief_fallback_without_a_title_stays_generic():
    questions = QuestionPolicyService(llm=OFFLINE).debrief([], [], 3)
    for q in questions:
        assert not any(w in q["question"].lower() for w in INVOICE_WORDS)


def test_debrief_flags_that_it_fell_back():
    questions = QuestionPolicyService(llm=OFFLINE).debrief([], [], 3, workflow_title="Incident Triage")
    assert all(q["source"] == "deterministic" for q in questions)


def test_generic_event_types_are_not_special_cased():
    """No event type is privileged, so an arbitrary one is handled the same way."""
    events = [_event(1, "totally_custom_event", {"reason": "because the runbook said so"})]
    questions = QuestionPolicyService(llm=OFFLINE).debrief(events, [], 3, workflow_title="Incident Triage")
    assert any("the runbook said so" in q["question"] for q in questions)


def test_decide_fallback_asks_something_grounded_when_events_are_unrecognised():
    result = QuestionPolicyService(llm=OFFLINE).decide(
        [_event(1, "heartbeat")], [], 0, budget=5, workflow_title="Fleet Telemetry Review"
    )
    assert result["should_ask"] is True
    assert "Fleet Telemetry Review" in result["question"]
    assert not any(w in result["question"].lower() for w in INVOICE_WORDS)


def test_decide_respects_budget_and_flags_the_source():
    qp = QuestionPolicyService(llm=OFFLINE)
    over = qp.decide([_event(1, "heartbeat")], [], 5, budget=5, workflow_title="Fleet Telemetry Review")
    assert over["should_ask"] is False
    assert over["source"] == "deterministic"
    empty = qp.decide([], [], 0, budget=5, workflow_title="Fleet Telemetry Review")
    assert empty["should_ask"] is False


def test_llm_result_is_marked_as_such():
    class StubLLM:
        configured = True

        def complete_json(self, system, user, max_tokens=1024):
            assert "Incident Triage" in user, "workflow context must reach the prompt"
            return {
                "questions": [
                    {
                        "question_type": "boundary",
                        "question": "What severity would keep this in tier2?",
                        "evidence_quote": "escalated",
                        "trigger_event_id": None,
                        "rationale_for_internal_logging": "tier",
                    }
                ]
            }

    questions = QuestionPolicyService(llm=StubLLM()).debrief(
        [_event(1, "ticket_opened", {"severity": "high"})], [_seg("escalated")], 1,
        workflow_title="Incident Triage",
    )
    assert len(questions) == 1
    assert questions[0]["question"] == "What severity would keep this in tier2?"
    assert questions[0]["source"] == "llm"


def test_llm_prompts_forbid_invoice_vocabulary():
    captured = []

    class CapturingLLM:
        configured = True

        def complete_json(self, system, user, max_tokens=1024):
            captured.append((system, user))
            return None

    qp = QuestionPolicyService(llm=CapturingLLM())
    qp.debrief([_event(1, "ticket_opened")], [_seg("hi")], 3, workflow_title="Incident Triage")
    qp.decide([_event(1, "ticket_opened")], [], 0, budget=5, workflow_title="Incident Triage")
    assert len(captured) == 2
    for system, user in captured:
        # Both prompts must forbid introducing concepts the capture never mentions.
        assert "never introduce" in system, system
        assert "Incident Triage" in user, "workflow context must reach the prompt"