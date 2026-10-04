from typing import Any

from sqlalchemy.orm import Session

from app.models import models


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

        for event in events:
            data = event.data or {}
            action = data.get("action") or event.type
            decision = data.get("decision")
            reason = data.get("reason")
            guardrails: list[dict] = []

            if isinstance(data.get("guardrails"), list):
                guardrails.extend(g for g in data["guardrails"] if isinstance(g, dict))

            if event.type == "field_changed":
                field = data.get("field")
                action = data.get("action") or (f"change_{field}" if field else "field_changed")
                decision = data.get("new_value", decision)
                if field == "cost_center":
                    action = "change_cost_center"
                    if decision == "CAPEX":
                        reason = reason or _find_reason(
                            segments, ["capital", "asset", "threshold", "equipment"]
                        ) or "Equipment above the configured threshold is capitalized."
                        guardrails.append(
                            {
                                "rule": "Require an asset number before submission",
                                "severity": "block",
                                "confirmed_by_expert": False,
                                "rule_id": "require_asset_number",
                            }
                        )
            elif event.type in ("save_attempted", "submit"):
                action = data.get("action") or "save"
                decision = data.get("decision", decision)
                reason = reason or _find_reason(
                    segments, ["escalate", "stop", "refer", "supervisor"]
                ) or "Escalate to a supervisor when the capitalization policy is unclear."
                guardrails.append(
                    {
                        "rule": "Escalate when policy is unclear",
                        "severity": "warn",
                        "confirmed_by_expert": False,
                        "rule_id": "escalate_unclear_policy",
                    }
                )

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

        for seg in segments:
            step = models.WorkflowStep(
                workflow_id=workflow.id,
                timestamp_ms=seg.timestamp_ms,
                action="transcript_note",
                context={"speaker": seg.speaker},
                decision=None,
                reason=seg.text,
                guardrails=[],
                evidence={"event_ids": [], "transcript_segment_ids": [seg.id]},
                confidence=0.95,
                review_status="proposed",
            )
            self.db.add(step)

        # Dedicated guardrail step so Tutor mode can link back to the expert moment.
        # Only emitted when the session actually shows capitalization signals, so real
        # systems instrumented via the SDK are not polluted with the invoice-specific rule.
        has_asset_signal = any(
            e.type == "asset_number_entered"
            or (e.type == "field_changed" and (e.data or {}).get("field") == "cost_center")
            for e in events
        )
        if has_asset_signal:
            wm_reason = _find_reason(segments, ["capital", "asset", "threshold", "equipment"])
            self.db.add(
                models.WorkflowStep(
                    workflow_id=workflow.id,
                    timestamp_ms=(events[0].timestamp_ms if events else 0),
                    action="require_asset_number",
                    context={"rule_id": "require_asset_number"},
                    decision="CAPEX",
                    reason=wm_reason
                    or "Equipment above the configured threshold is capitalized and requires an asset number.",
                    guardrails=[
                        {
                            "rule": "Require an asset number before submission",
                            "severity": "block",
                            "confirmed_by_expert": False,
                            "rule_id": "require_asset_number",
                        }
                    ],
                    evidence={
                        "event_ids": [e.id for e in events if e.type == "field_changed"],
                        "transcript_segment_ids": [s.id for s in segments],
                    },
                    confidence=0.85,
                    review_status="proposed",
                )
            )

        answered = (
            self.db.query(models.Question)
            .filter_by(session_id=session.id)
            .filter(models.Question.answer_text.isnot(None))
            .order_by(models.Question.timestamp_ms)
            .all()
        )
        for q in answered:
            self.db.add(
                models.WorkflowStep(
                    workflow_id=workflow.id,
                    timestamp_ms=q.timestamp_ms,
                    action="expert_answer",
                    context={"question_type": q.question_type, "question_text": q.question_text},
                    decision=None,
                    reason=q.answer_text,
                    guardrails=[],
                    evidence={"event_ids": [], "transcript_segment_ids": []},
                    confidence=1.0,
                    review_status="proposed",
                )
            )

        self.db.commit()
        self.db.refresh(workflow)
        return workflow

    def get_workflow(self, db: Session = None, workflow_id: str | None = None) -> models.Workflow | None:
        if workflow_id is None:
            raise ValueError("workflow_id is required")
        db_ = db or self.db
        if db_ is None:
            raise ValueError("db is required")
        return db_.get(models.Workflow, workflow_id)

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
