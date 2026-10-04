import pytest

from app.services.workmap_service import WorkMapService, _is_substantive, _severity_for


@pytest.mark.parametrize(
    "text,expected",
    [
        ("I set the cost centre to CAPEX because this compressor is equipment.", True),
        ("High severity goes straight to tier2 because ties must escalate.", True),
        ("Hmm?", False),
        ("Okay.", False),
        ("...", False),
        ("yeah", False),
        ("Okay. All right.", False),
        ("I-", False),
        ("yes no sure", False),
        ("", False),
        (None, False),
    ],
)
def test_filler_is_not_substantive(text, expected):
    assert _is_substantive(text) is expected


@pytest.mark.parametrize(
    "text,severity",
    [
        ("You must never apply reverse charge without a certificate.", "high"),
        ("Anything over two thousand dollars requires a second approver.", "high"),
        ("The cut-off for that is $2,000 so I check it there.", "medium"),
        ("I usually pick the cheaper supplier when the lead time is fine.", "low"),
    ],
)
def test_severity_reflects_rule_strength(text, severity):
    assert _severity_for(text) == severity


class _FakeStep:
    def __init__(self, timestamp_ms):
        self.timestamp_ms = timestamp_ms
        self.guardrails = []
        self.evidence = {"event_ids": [], "transcript_segment_ids": []}
        self.reason = None
        self.confidence = 0.6


class _FakeSeg:
    def __init__(self, sid, timestamp_ms, text):
        self.id = sid
        self.timestamp_ms = timestamp_ms
        self.text = text


def test_reasoning_attaches_to_the_step_being_explained():
    steps = [_FakeStep(10_000), _FakeStep(50_000), _FakeStep(90_000)]
    segments = [
        _FakeSeg("s1", 55_000, "I escalated it because the SLA for high severity is 15 minutes."),
        _FakeSeg("s2", 95_000, "I close the alert only when telemetry has been stable."),
    ]

    for seg in segments:
        step = WorkMapService._nearest_step(steps, seg.timestamp_ms)
        assert step is not None
        step.guardrails = list(step.guardrails or []) + [
            {"severity": _severity_for(seg.text), "rule": seg.text}
        ]
        if not step.reason:
            step.reason = seg.text

    assert steps[0].guardrails == []
    assert [g["rule"] for g in steps[1].guardrails] == [segments[0].text]
    assert [g["rule"] for g in steps[2].guardrails] == [segments[1].text]
    assert steps[1].reason == segments[0].text


def test_nearest_step_prefers_the_most_recent_prior_step():
    steps = [_FakeStep(10_000), _FakeStep(50_000), _FakeStep(90_000)]
    assert WorkMapService._nearest_step(steps, 89_000) is steps[1]
    assert WorkMapService._nearest_step(steps, 90_000) is steps[2]
    # spoken before any step existed -> fall back to the earliest step
    assert WorkMapService._nearest_step(steps, 1_000) is steps[0]
    assert WorkMapService._nearest_step([], 1_000) is None