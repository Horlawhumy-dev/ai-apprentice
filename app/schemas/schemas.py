from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    workflow_title: str = "Untitled workflow"
    expert_name: Optional[str] = "Expert"


class CreateSessionResponse(BaseModel):
    session_id: str
    workflow_title: str
    expert_name: Optional[str]
    status: str


class EventPayload(BaseModel):
    client_event_id: str
    timestamp_ms: int
    source: str
    type: str
    data: dict[str, Any] = Field(default_factory=dict)
    frame_id: Optional[str] = None


TranscriptSource = Literal["voice_provider", "prototype_transcript"]


class TranscriptSegmentPayload(BaseModel):
    segment_id: str
    timestamp_ms: int
    speaker: str
    text: str
    source: TranscriptSource


class Guardrail(BaseModel):
    rule: str
    severity: Literal["info", "warn", "block"]
    confirmed_by_expert: bool = False
    rule_id: Optional[str] = None


class Evidence(BaseModel):
    event_ids: list[str] = Field(default_factory=list)
    transcript_segment_ids: list[str] = Field(default_factory=list)
    frame_id: Optional[str] = None


class WorkflowStepSchema(BaseModel):
    id: str
    timestamp_ms: int
    action: str
    context: dict[str, Any] = Field(default_factory=dict)
    decision: Optional[str] = None
    reason: Optional[str] = None
    guardrails: list[Guardrail] = Field(default_factory=list)
    evidence: Evidence = Field(default_factory=Evidence)
    confidence: Optional[float] = None
    review_status: Literal["proposed", "confirmed", "rejected", "uncertain"] = "proposed"


class WorkMapResponse(BaseModel):
    id: str
    title: str
    status: str
    steps: list[WorkflowStepSchema] = Field(default_factory=list)


class QuestionResponse(BaseModel):
    question_id: str
    question_type: str
    question_text: str
    timestamp_ms: int
