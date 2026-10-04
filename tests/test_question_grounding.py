from app.services.question_policy import _corpus, _is_grounded, _validate_debrief, _validate_decide


class _Ev:
    def __init__(self, eid, etype, data):
        self.id = eid
        self.type = etype
        self.data = data


class _Seg:
    def __init__(self, speaker, text):
        self.speaker = speaker
        self.text = text


EVENTS = [_Ev("e1", "ticket_opened", {"ticket": "T-1", "severity": "high"})]
SEGMENTS = [_Seg("expert", "I escalated it because tier1 was already at capacity.")]


def test_corpus_contains_captured_material():
    corpus = _corpus(EVENTS, SEGMENTS)
    assert '"ticket": "t-1"' in corpus
    assert "ticket_opened" in corpus
    assert "tier1 was already at capacity" in corpus


def test_grounding_requires_a_real_quote():
    corpus = _corpus(EVENTS, SEGMENTS)
    assert _is_grounded("tier1 was already at capacity", corpus)
    # invented domain language is not in the capture
    assert not _is_grounded("the amount exceeded the approval threshold", corpus)
    assert not _is_grounded("tier", corpus)
    assert not _is_grounded(None, corpus)


def test_debrief_drops_ungrounded_questions():
    raw = {
        "questions": [
            {
                "question_type": "guardrail",
                "question": "Which situations must never be approved automatically?",
                "evidence_quote": "invoices above ten thousand need a second approver",
                "rationale_for_internal_logging": "llm",
            }
        ]
    }
    assert _validate_debrief(raw, EVENTS, 3, _corpus(EVENTS, SEGMENTS)) is None


def test_debrief_keeps_grounded_questions():
    raw = {
        "questions": [
            {
                "question_type": "rationale",
                "question": "You escalated because tier1 was at capacity - what would have changed your mind?",
                "evidence_quote": "tier1 was already at capacity",
                "rationale_for_internal_logging": "llm",
            }
        ]
    }
    out = _validate_debrief(raw, EVENTS, 3, _corpus(EVENTS, SEGMENTS))
    assert out and len(out) == 1
    assert out[0]["question_type"] == "rationale"


def test_debrief_keeps_only_the_grounded_subset():
    raw = {
        "questions": [
            {
                "question_type": "rationale",
                "question": "Why escalate here?",
                "evidence_quote": "tier1 was already at capacity",
            },
            {
                "question_type": "boundary",
                "question": "If the amount were halved, would your process change?",
                "evidence_quote": "when the amount is halved the process changes",
            },
        ]
    }
    out = _validate_debrief(raw, EVENTS, 3, _corpus(EVENTS, SEGMENTS))
    assert [q["question_type"] for q in out] == ["rationale"]


def test_decide_rejects_ungrounded_question():
    raw = {
        "should_ask": True,
        "question_type": "exception",
        "question": "What is the most common exception you hit?",
        "evidence_quote": "the usual exception is a rush order",
    }
    assert _validate_decide(raw, EVENTS, _corpus(EVENTS, SEGMENTS)) is None


def test_decide_accepts_grounded_question():
    raw = {
        "should_ask": True,
        "question_type": "rationale",
        "question": "You moved it to tier2 - what drove that?",
        "evidence_quote": "tier1 was already at capacity",
    }
    out = _validate_decide(raw, EVENTS, _corpus(EVENTS, SEGMENTS))
    assert out and out["should_ask"] is True


def test_empty_capture_stays_silent_rather_than_inventing():
    raw = {
        "should_ask": True,
        "question_type": "guardrail",
        "question": "Which situations must never be approved automatically?",
        "evidence_quote": "anything above the limit needs review",
    }
    # nothing captured -> empty corpus -> the LLM answer is not trusted
    assert _validate_decide(raw, [], _corpus([], [])) is None