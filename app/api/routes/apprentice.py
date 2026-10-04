from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.models import models
from app.services.case_service import CaseService
from app.services.tutor_service import TutorService

router = APIRouter(prefix="/apprentice", tags=["Apprentice"])


class CreateApprenticeSessionRequest(BaseModel):
    workflow_id: str
    case_id: str = "case_alpha"


class EvaluateRequest(BaseModel):
    action: str
    case_data: dict[str, Any] = {}


@router.get("/cases")
def list_cases():
    return {"cases": CaseService().list_cases()}


@router.get("/cases/{case_id}")
def get_case(case_id: str):
    case = CaseService().get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("/sessions")
def create_apprentice_session(payload: CreateApprenticeSessionRequest, db: Session = Depends(get_db)):
    wf = db.get(models.Workflow, payload.workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    case = CaseService().get_case(payload.case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    asess = models.ApprenticeSession(workflow_id=wf.id, case_id=payload.case_id, status="in_progress")
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

    case = CaseService().get_case(asess.case_id) or {}
    merged = {**case, **{k: v for k, v in payload.case_data.items() if v is not None}}

    tutor = TutorService(db)
    res = tutor.evaluate(payload.action, merged)

    evidence_step_id = res.get("evidence_step_id")
    if evidence_step_id:
        step = (
            db.query(models.WorkflowStep)
            .filter_by(workflow_id=asess.workflow_id, action=evidence_step_id)
            .first()
        )
        if step:
            result = {
                "allowed": res.get("allowed", True),
                "matched_rule_id": res.get("matched_rule_id"),
                "severity": res.get("severity", "info"),
                "explanation": res.get("explanation", ""),
                "evidence_step_id": step.id,
                "evidence": {
                    "action": step.action,
                    "reason": step.reason,
                    "timestamp_ms": step.timestamp_ms,
                    "guardrails": step.guardrails,
                },
                "next_question": res.get("next_question"),
            }
        else:
            result = {**res}
    else:
        result = {**res}

    attempt = models.ApprenticeAttempt(
        apprentice_session_id=asess.id,
        action=payload.action,
        evaluated_rule_id=res.get("matched_rule_id"),
        outcome="allowed" if res.get("allowed") else "blocked",
        feedback=res.get("explanation"),
        timestamp_ms=int(datetime.utcnow().timestamp() * 1000),
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
    asess.finished_at = datetime.utcnow()
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
