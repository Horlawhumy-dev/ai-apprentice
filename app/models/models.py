from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.connection import Base


def uuid_str() -> str:
    return str(uuid4())


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    workflow_title: Mapped[str] = mapped_column(String(255), default="Untitled workflow")
    expert_name: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="created")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    events: Mapped[list["Event"]] = relationship("Event", back_populates="session")
    transcript_segments: Mapped[list["TranscriptSegment"]] = relationship(
        "TranscriptSegment", back_populates="session"
    )
    questions: Mapped[list["Question"]] = relationship("Question", back_populates="session")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"))
    client_event_id: Mapped[str] = mapped_column(String(36), unique=True)
    timestamp_ms: Mapped[int] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(100))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    frame_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    session: Mapped["Session"] = relationship("Session", back_populates="events")


Index("ix_events_session_timestamp", Event.session_id, Event.timestamp_ms)
Index("ix_events_client_id", Event.client_event_id)


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"))
    timestamp_ms: Mapped[int] = mapped_column(BigInteger)
    speaker: Mapped[str] = mapped_column(String(50))
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(100))
    off_record: Mapped[bool] = mapped_column(Boolean, default=False)

    session: Mapped["Session"] = relationship("Session", back_populates="transcript_segments")


Index("ix_transcript_session_timestamp", TranscriptSegment.session_id, TranscriptSegment.timestamp_ms)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessions.id"))
    timestamp_ms: Mapped[int] = mapped_column(BigInteger)
    question_type: Mapped[str] = mapped_column(String(100))
    question_text: Mapped[str] = mapped_column(Text)
    answer_text: Mapped[Optional[str]] = mapped_column(Text)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    session: Mapped["Session"] = relationship("Session", back_populates="questions")


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="needs_expert_review")
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    steps: Mapped[list["WorkflowStep"]] = relationship("WorkflowStep", back_populates="workflow")


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    workflow_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflows.id"))
    timestamp_ms: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(255))
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    decision: Mapped[Optional[str]] = mapped_column(Text)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    guardrails: Mapped[dict | list] = mapped_column(JSON, default=list)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    review_status: Mapped[str] = mapped_column(String(50), default="proposed")

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="steps")


class ApprenticeSession(Base):
    __tablename__ = "apprentice_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    workflow_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflows.id"))
    case_id: Mapped[str] = mapped_column(String(255))
    case_data: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(50), default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    attempts: Mapped[list["ApprenticeAttempt"]] = relationship(
        "ApprenticeAttempt", back_populates="apprentice_session"
    )


class ApprenticeAttempt(Base):
    __tablename__ = "apprentice_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    apprentice_session_id: Mapped[str] = mapped_column(String(36), ForeignKey("apprentice_sessions.id"))
    action: Mapped[str] = mapped_column(String(255))
    evaluated_rule_id: Mapped[Optional[str]] = mapped_column(String(255))
    outcome: Mapped[str] = mapped_column(String(50))
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    timestamp_ms: Mapped[int] = mapped_column(BigInteger)

    apprentice_session: Mapped["ApprenticeSession"] = relationship(
        "ApprenticeSession", back_populates="attempts"
    )
