from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.time import epoch_ms, utcnow
from app.db.connection import get_db
from app.models import models
from app.services.case_service import CaseService
from app.services.tutor_service import TutorService

router = APIRouter(prefix="/apprentice", tags=["Apprentice"])


class CreateApprenticeSessionRequest(BaseModel):
    workflow_id: str
    case_id: str = "case"
    case_data: dict[str, Any] = Field(default_factory=dict)


class EvaluateRequest(BaseModel):
    action: str
    case_data: dict[str, Any] = {}


@router.get("/cases")
def list_cases(workflow_id: str | None = None, db: Session = Depends(get_db)):
    """Cases actually in use, taken from apprentice sessions rather than a fixture."""
    query = db.query(models.ApprenticeSession)
    if workflow_id:
        query = query.filter_by(workflow_id=workflow_id)
    seen: set[str] = set()
    cases: list[dict] = []
    for session in query.all():
        if session.case_id in seen:
            continue
        seen.add(session.case_id)
        cases.append(CaseService.normalise(session.case_id, session.case_data or {}))
    return {"cases": cases}


@router.get("/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)):
    session = db.query(models.ApprenticeSession).filter_by(case_id=case_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Case not found")
    return CaseService.normalise(session.case_id, session.case_data or {})


@router.post("/sessions")
def create_apprentice_session(payload: CreateApprenticeSessionRequest, db: Session = Depends(get_db)):
    wf = db.get(models.Workflow, payload.workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    case = CaseService.normalise(payload.case_id, payload.case_data)
    asess = models.ApprenticeSession(
        workflow_id=wf.id,
        case_id=payload.case_id,
        case_data=payload.case_data,
        status="in_progress",
    )
    db.add(asess)
    db.commit()
    db.refresh(asess)
    return {
        "id": asess.id,
        "workflow_id": asess.workflow_id,
        "case_id": asess.case_id,
        "status": asess.status,
        "started_at": asess.started_at,
        "case": case,
    }


@router.get("/sessions/{session_id}")
def get_apprentice_session(session_id: str, db: Session = Depends(get_db)):
    asess = db.get(models.ApprenticeSession, session_id)
    if not asess:
        raise HTTPException(status_code=404, detail="Apprentice session not found")
    attempts = [
        {
            "id": a.id,
            "action": a.action,
            "outcome": a.outcome,
            "matched_rule_id": a.evaluated_rule_id,
            "feedback": a.feedback,
            "timestamp_ms": a.timestamp_ms,
        }
        for a in asess.attempts
    ]
    return {
        "id": asess.id,
        "status": asess.status,
        "workflow_id": asess.workflow_id,
        "case_id": asess.case_id,
        "started_at": asess.started_at,
        "finished_at": asess.finished_at,
        "attempts": attempts,
    }


@router.post("/sessions/{session_id}/evaluate")
def evaluate(session_id: str, payload: EvaluateRequest, db: Session = Depends(get_db)):
    asess = db.get(models.ApprenticeSession, session_id)
    if not asess:
        raise HTTPException(status_code=404, detail="Apprentice session not found")
    if asess.status != "in_progress":
        raise HTTPException(status_code=400, detail="Session not in progress")

    merged = {**(asess.case_data or {}), **{k: v for k, v in (payload.case_data or {}).items() if v is not None}}

    # Guardrails are data captured for this specific workflow, not built into the code.
    workflow_steps = (
        db.query(models.WorkflowStep).filter_by(workflow_id=asess.workflow_id).all()
    )
    workflow_guardrails: list[dict] = []
    for step in workflow_steps:
        for rule in step.guardrails or []:
            if isinstance(rule, dict):
                workflow_guardrails.append({**rule, "_step_id": step.id})

    tutor = TutorService(db)
    res = tutor.evaluate(payload.action, merged, workflow_guardrails)

    result = {**res}
    # Link a blocked action back to the step that actually defined the rule, so the
    # apprentice can see the expert's own reasoning. The rule id is the reliable link;
    # a step's `action` is frequently something else entirely.
    matched_rule_id = res.get("matched_rule_id")
    if matched_rule_id:
        source = next(
            (r for r in workflow_guardrails if r.get("rule_id") == matched_rule_id), None
        )
        step = db.get(models.WorkflowStep, (source or {}).get("_step_id") or "")
        if step:
            result["evidence_step_id"] = step.id
            result["evidence"] = {
                "action": step.action,
                "reason": step.reason,
                "timestamp_ms": step.timestamp_ms,
                "guardrails": step.guardrails,
            }

    attempt = models.ApprenticeAttempt(
        apprentice_session_id=asess.id,
        action=payload.action,
        evaluated_rule_id=res.get("matched_rule_id"),
        outcome="allowed" if res.get("allowed") else "blocked",
        feedback=res.get("explanation"),
        timestamp_ms=epoch_ms(),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    result["attempt_id"] = attempt.id
    return result


@router.post("/sessions/{session_id}/finish")
def finish_apprentice(session_id: str, db: Session = Depends(get_db)):
    asess = db.get(models.ApprenticeSession, session_id)
    if not asess:
        raise HTTPException(status_code=404, detail="Apprentice session not found")
    if asess.status == "finished":
        return {"id": asess.id, "status": asess.status, "finished_at": asess.finished_at}
    asess.status = "finished"
    asess.finished_at = utcnow()
    db.commit()
    db.refresh(asess)
    blocked = [a for a in asess.attempts if a.outcome == "blocked"]
    allowed = [a for a in asess.attempts if a.outcome == "allowed"]
    return {
        "id": asess.id,
        "status": asess.status,
        "finished_at": asess.finished_at,
        "summary": {
            "attempts": len(asess.attempts),
            "blocked": len(blocked),
            "allowed": len(allowed),
        },
    }
