from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.db.connection import get_db
from app.models import models
from app.services.workmap_service import WorkMapService

router = APIRouter(prefix="/workflows", tags=["Workflows"])


class StepUpdate(BaseModel):
    review_status: str | None = None
    reason: str | None = None
    decision: str | None = None
    action: str | None = None
    guardrails: list[dict] | None = None


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str, db: Session = Depends(get_db)):
    wm = WorkMapService(db)
    wf = wm.get_workflow(workflow_id=workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wm.to_response(wf)


@router.patch("/{workflow_id}")
def update_workflow(workflow_id: str, payload: dict, db: Session = Depends(get_db)):
    wm = WorkMapService(db)
    wf = wm.get_workflow(workflow_id=workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if payload.get("status") is not None:
        wf.status = payload["status"]
        if payload["status"] == "confirmed":
            wf.confirmed_at = utcnow()
    db.commit()
    db.refresh(wf)
    return wm.to_response(wf)


@router.patch("/{workflow_id}/steps/{step_id}")
def update_step(workflow_id: str, step_id: str, payload: StepUpdate, db: Session = Depends(get_db)):
    wf = db.get(models.Workflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    step = db.get(models.WorkflowStep, step_id)
    if not step or step.workflow_id != workflow_id:
        raise HTTPException(status_code=404, detail="Step not found")
    data = payload.model_dump(exclude_unset=True)
    for key in ("review_status", "reason", "decision", "action"):
        if key in data and data[key] is not None:
            setattr(step, key, data[key])
    if "guardrails" in data and data["guardrails"] is not None:
        step.guardrails = data["guardrails"]
    db.commit()
    db.refresh(step)
    return {
        "id": step.id,
        "review_status": step.review_status,
        "reason": step.reason,
        "decision": step.decision,
        "action": step.action,
        "guardrails": step.guardrails,
    }
