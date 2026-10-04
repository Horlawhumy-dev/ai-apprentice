import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models import models

log = logging.getLogger(__name__)

# Acknowledgements and half-words are not reasoning; attaching them as guardrails
# would teach the apprentice to block on noise.
_FILLER_PHRASES = {
    "hmm", "hm", "mm", "uh", "um", "erm", "ah", "eh",
    "okay", "ok", "k", "yeah", "yep", "yes", "no", "nope", "sure", "right",
    "alright", "all right", "fine", "thanks", "thank you", "got it", "okay sure",
    "gotcha", "cool", "nice", "great", "perfect", "good", "exactly", "correct",
    "continue", "carry on", "go ahead", "please", "done", "hello", "hi",
}

# Wording that signals a hard rule rather than a passing comment.
_STRONG_RULE = re.compile(
    r"\b(must|never|always|only|require[sd]?|cannot|can't|do not|don't|no one|"
    r"at least|minimum|mandatory|refuse[sd]?|reject[sd]?)\b",
    re.IGNORECASE,
)
_THRESHOLD = re.compile(
    # A currency amount ("$2,000", "2000 dollars"), a quantity with a unit
    # ("30 hours", "14 days"), or a comma-grouped figure, which is nearly always a
    # magnitude someone is drawing a line at.
    r"(\$\s?\d[\d,.]*"
    r"|\b\d[\d,.]*\s*(?:k\b|%|percent|hours?|hrs?|minutes?|mins?|days?|dollars?)"
    r"|\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b)",
    re.IGNORECASE,
)


def _is_substantive(text: str | None) -> bool:
    """True when a transcript line carries enough substance to become a rule."""
    if not text:
        return False
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = cleaned.split()
    if not tokens:
        return False
    if cleaned.strip() in _FILLER_PHRASES or set(tokens) <= _FILLER_PHRASES:
        return False
    return len(cleaned.split()) >= 5


def _severity_for(text: str) -> str:
    if _STRONG_RULE.search(text):
        return "high"
    if _THRESHOLD.search(text):
        return "medium"
    return "low"


def _find_reason(segments: list[models.TranscriptSegment], keywords: list[str]) -> str | None:
    for seg in segments:
        text = (seg.text or "").lower()
        if any(k in text for k in keywords):
            return seg.text
    return None


class WorkMapService:
    def __init__(self, db: Session | None = None):
        self.db = db

    def generate_workflow(
        self,
        session: models.Session,
        events: list[models.Event],
        segments: list[models.TranscriptSegment],
    ) -> models.Workflow:
        if self.db is None:
            raise ValueError("db is required")

        workflow = models.Workflow(title=session.workflow_title, status="needs_expert_review", version=1)
        self.db.add(workflow)
        self.db.commit()
        self.db.refresh(workflow)

        steps: list[models.WorkflowStep] = []

        for event in events:
            data = event.data or {}
            action = data.get("action") or event.type
            decision = data.get("decision")
            reason = data.get("reason")
            guardrails: list[dict] = []

            if isinstance(data.get("guardrails"), list):
                guardrails.extend(g for g in data["guardrails"] if isinstance(g, dict))

            # Steps are derived from whatever the instrumented app emits; no domain
            # is assumed here. A field_changed event still counts as a decision point,
            # and the expert's own `reason` / `guardrails` are carried through verbatim.
            if event.type == "field_changed":
                field = data.get("field")
                action = data.get("action") or (f"change_{field}" if field else "field_changed")
                decision = data.get("new_value", decision)

            step = models.WorkflowStep(
                workflow_id=workflow.id,
                timestamp_ms=event.timestamp_ms,
                action=action,
                context=data,
                decision=decision,
                reason=reason,
                guardrails=guardrails,
                evidence={"event_ids": [event.id], "transcript_segment_ids": [], "frame_id": event.frame_id},
                confidence=0.9 if reason else 0.6,
                review_status="proposed",
            )
            self.db.add(step)
            steps.append(step)

        # The expert narrates *while* working, so their reasoning belongs to the step
        # they were on when they said it. Filing it as a separate `transcript_note`
        # step left every action rule-less and the apprentice with nothing to enforce.
        reasoning = [s for s in segments if _is_substantive(s.text)]
        for seg in reasoning:
            step = self._nearest_step(steps, seg.timestamp_ms)
            if step is None:
                continue
            self._attach_reasoning(step, seg)

        # A step the expert said nothing about still needs an enforceable rule, or the
        # apprentice has nothing to be held to. Fall back to the closest thing they did
        # say so no step in the map is silently rule-less.
        for step in steps:
            if step.reason or not reasoning:
                continue
            nearest = min(reasoning, key=lambda s: abs(s.timestamp_ms - step.timestamp_ms))
            self._attach_reasoning(step, nearest)

        # With no instrumented app there are no event steps to attach to; keep the
        # expert's own reasoning as the steps so the Work Map is still usable.
        if not steps:
            for seg in reasoning:
                step = models.WorkflowStep(
                    workflow_id=workflow.id,
                    timestamp_ms=seg.timestamp_ms,
                    action="narrated_decision",
                    context={"speaker": seg.speaker},
                    decision=None,
                    reason=seg.text,
                    guardrails=[{"severity": _severity_for(seg.text), "rule": seg.text.strip()}],
                    evidence={"event_ids": [], "transcript_segment_ids": [seg.id]},
                    confidence=0.9,
                    review_status="proposed",
                )
                self.db.add(step)
                steps.append(step)

        self._ensure_rule_ids(steps)
        self.db.commit()
        self.db.refresh(workflow)
        return workflow

    @staticmethod
    def _ensure_rule_ids(steps: list[models.WorkflowStep]) -> None:
        """Give every rule a stable id.

        Rules a step picks up from spoken reasoning have no id of their own, so the
        evaluator has nothing to report back and a matched rule cannot be traced to
        the step that defined it. Ids that already exist are left untouched.
        """
        n = 0
        for step in steps:
            guardrails = list(step.guardrails or [])
            changed = False
            for rule in guardrails:
                if not rule.get("rule_id"):
                    n += 1
                    rule["rule_id"] = f"r{n}"
                    changed = True
            if changed:
                step.guardrails = guardrails

    @staticmethod
    def _attach_reasoning(step: models.WorkflowStep, seg: models.TranscriptSegment) -> None:
        """Record the expert's words as a rule on the step they were explaining."""
        text = seg.text.strip()
        if not text:
            return
        if step.evidence is None:
            step.evidence = {}
        ids = step.evidence.setdefault("transcript_segment_ids", [])
        if seg.id not in ids:
            ids.append(seg.id)
        guardrails = list(step.guardrails or [])
        if not any(g.get("rule") == text for g in guardrails):
            guardrails.append({"severity": _severity_for(text), "rule": text})
        step.guardrails = guardrails
        if not step.reason:
            step.reason = text
        step.confidence = max(step.confidence or 0.0, 0.95)

    @staticmethod
    def _nearest_step(steps: list[models.WorkflowStep], timestamp_ms: int) -> models.WorkflowStep | None:
        """The step the expert was on when they spoke (prefer the most recent prior step)."""
        if not steps:
            return None
        prior = [s for s in steps if s.timestamp_ms <= timestamp_ms]
        if prior:
            return max(prior, key=lambda s: s.timestamp_ms)
        return min(steps, key=lambda s: s.timestamp_ms)

    def get_workflow(self, db: Session = None, workflow_id: str | None = None) -> models.Workflow | None:
        if workflow_id is None:
            raise ValueError("workflow_id is required")
        db_ = db or self.db
        if db_ is None:
            raise ValueError("db is required")
        return db_.get(models.Workflow, workflow_id)

    def latest_workflow(self) -> models.Workflow | None:
        """The most recently captured work map, or None if the user has not captured one.

        Used by the UI's "latest work map" link so it always shows real output from the
        user's own testing rather than seeded sample data.
        """
        if self.db is None:
            raise ValueError("db is required")
        return (
            self.db.query(models.Workflow)
            .order_by(models.Workflow.created_at.desc(), models.Workflow.id.desc())
            .first()
        )

    def to_response(self, workflow: models.Workflow) -> dict[str, Any]:
        steps = sorted(workflow.steps, key=lambda s: s.timestamp_ms)
        segment_cache: dict[str, models.TranscriptSegment] = {}
        if self.db is not None:
            for seg in self.db.query(models.TranscriptSegment).all():
                segment_cache[seg.id] = seg
        return {
            "id": workflow.id,
            "title": workflow.title,
            "status": workflow.status,
            "steps": [
                {
                    "id": step.id,
                    "timestamp_ms": step.timestamp_ms,
                    "action": step.action,
                    "context": step.context or {},
                    "decision": step.decision,
                    "reason": step.reason,
                    "guardrails": step.guardrails or [],
                    "evidence": self._enrich_evidence(step.evidence or {}, segment_cache),
                    "confidence": step.confidence,
                    "review_status": step.review_status,
                }
                for step in steps
            ],
        }

    @staticmethod
    def _enrich_evidence(
        evidence: dict[str, Any], segment_cache: dict[str, models.TranscriptSegment]
    ) -> dict[str, Any]:
        ids = evidence.get("transcript_segment_ids") or []
        excerpts = [
            {"id": sid, "speaker": segment_cache[sid].speaker, "text": segment_cache[sid].text}
            for sid in ids
            if sid in segment_cache
        ]
        if excerpts:
            return {**evidence, "transcript_excerpts": excerpts}
        return evidence
