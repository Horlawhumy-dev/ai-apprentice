from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/sessions", tags=["Sessions"])


class CreateSessionRequest(BaseModel):
    workflow_title: str = "Untitled workflow"
    expert_name: str = "Expert"


@router.post("")
def create_session(payload: CreateSessionRequest):
    return {
        "session_id": str(uuid4()),
        "workflow_title": payload.workflow_title,
        "expert_name": payload.expert_name,
        "status": "created",
    }
