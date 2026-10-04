from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.connection import get_db
from app.models import models
from app.schemas.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    EventPayload,
    TranscriptSegmentPayload,
)
from app.services.event_service import EventService
from app.services.session_service import SessionService
from app.services.transcript_service import TranscriptService
from app.services.workmap_service import WorkMapService
from app.services.question_policy import QuestionPolicyService

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post("", response_model=CreateSessionResponse)
def create_session(payload: CreateSessionRequest, db: Session = Depends(get_db)):
    svc = SessionService(db)
    sess = svc.create_session(payload.workflow_title, payload.expert_name)
    return CreateSessionResponse(
        session_id=sess.id,
        workflow_title=sess.workflow_title,
        expert_name=sess.expert_name,
        status=sess.status,
    )


@router.get("/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    svc = SessionService(db)
    sess = svc.get_session(session_id)
    event_count = (
        db.query(func.count(models.Event.id)).filter(models.Event.session_id == sess.id).scalar() or 0
    )
    latest = (
        db.query(models.Event)
        .filter(models.Event.session_id == sess.id)
        .order_by(models.Event.timestamp_ms.desc())
        .first()
    )
    return {
        "session_id": sess.id,
        "status": sess.status,
        "workflow_title": sess.workflow_title,
        "expert_name": sess.expert_name,
        "started_at": sess.started_at,
        "ended_at": sess.ended_at,
        "event_count": event_count,
        "latest_event": (
            {
                "id": latest.id,
                "type": latest.type,
                "source": latest.source,
                "timestamp_ms": latest.timestamp_ms,
                "data": latest.data or {},
            }
            if latest
            else None
        ),
    }


@router.post("/{session_id}/start")
@router.post("/{session_id}/capture/start")
def start_capture(session_id: str, db: Session = Depends(get_db)):
    svc = SessionService(db)
    sess = svc.get_session(session_id)
    if sess.status != "capturing":
        sess = svc.set_status(sess, "capturing")
    return {"session_id": sess.id, "status": sess.status}


@router.post("/{session_id}/events")
def add_event(session_id: str, payload: EventPayload, db: Session = Depends(get_db)):
    sess_svc = SessionService(db)
    sess = sess_svc.get_session(session_id)
    ev_svc = EventService(db)
    ev = ev_svc.add_event(sess, payload)
    return {
        "id": ev.id,
        "client_event_id": ev.client_event_id,
        "timestamp_ms": ev.timestamp_ms,
        "source": ev.source,
        "type": ev.type,
    }


@router.post("/{session_id}/transcript")
def add_transcript(session_id: str, payload: TranscriptSegmentPayload, db: Session = Depends(get_db)):
    sess_svc = SessionService(db)
    sess = sess_svc.get_session(session_id)
    tr_svc = TranscriptService(db)
    seg = tr_svc.add_segment(sess, payload)
    return {
        "id": seg.id,
        "timestamp_ms": seg.timestamp_ms,
        "speaker": seg.speaker,
    }


@router.post("/{session_id}/pause")
def pause(session_id: str, db: Session = Depends(get_db)):
    svc = SessionService(db)
    sess = svc.get_session(session_id)
    sess = svc.pause(sess)
    return {"session_id": sess.id, "status": sess.status}


@router.post("/{session_id}/resume")
def resume(session_id: str, db: Session = Depends(get_db)):
    svc = SessionService(db)
    sess = svc.get_session(session_id)
    sess = svc.resume(sess)
    return {"session_id": sess.id, "status": sess.status}


@router.post("/{session_id}/off-record")
def off_record(session_id: str, db: Session = Depends(get_db)):
    svc = SessionService(db)
    sess = svc.get_session(session_id)
    sess = svc.off_record(sess)
    return {"session_id": sess.id, "status": sess.status}


@router.post("/{session_id}/finish")
def finish(session_id: str, db: Session = Depends(get_db)):
    svc = SessionService(db)
    sess = svc.get_session(session_id)
    if sess.status == "finished":
        return {"session_id": sess.id, "status": sess.status}
    sess = svc.finish(sess)
    if sess.status == "finishing":
        sess = svc.mark_finished(sess)
    return {"session_id": sess.id, "status": sess.status}


@router.post("/{session_id}/questions/decide")
def decide_question(session_id: str, db: Session = Depends(get_db)):
    sess_svc = SessionService(db)
    sess = sess_svc.get_session(session_id)
    ev_svc = EventService(db)
    tr_svc = TranscriptService(db)
    pol = QuestionPolicyService()
    events = ev_svc.list_events(sess)
    segs = tr_svc.list_segments(sess)
    questions = db.query(models.Question).filter_by(session_id=sess.id).all()
    res = pol.decide(list(events), list(segs), len(questions), budget=5, paused=(sess.status == "paused"))
    if res.get("should_ask"):
        q = models.Question(
            session_id=sess.id,
            timestamp_ms=int(datetime.utcnow().timestamp() * 1000),
            question_type=res["question_type"],
            question_text=res["question"],
        )
        db.add(q)
        db.commit()
        db.refresh(q)
        return {
            "should_ask": True,
            "question_id": q.id,
            "question_type": q.question_type,
            "question_text": q.question_text,
            "timestamp_ms": q.timestamp_ms,
        }
    return res


@router.post("/{session_id}/debrief")
def debrief(session_id: str, db: Session = Depends(get_db)):
    sess_svc = SessionService(db)
    sess = sess_svc.get_session(session_id)
    existing = (
        db.query(models.Question)
        .filter_by(session_id=sess.id)
        .order_by(models.Question.timestamp_ms)
        .all()
    )
    if existing:
        return {
            "session_id": sess.id,
            "questions": [
                {
                    "question_id": q.id,
                    "question_type": q.question_type,
                    "question_text": q.question_text,
                    "answer_text": q.answer_text,
                    "timestamp_ms": q.timestamp_ms,
                }
                for q in existing
            ],
        }

    pol = QuestionPolicyService()
    ev_svc = EventService(db)
    tr_svc = TranscriptService(db)
    events = ev_svc.list_events(sess)
    segs = tr_svc.list_segments(sess)
    prompts = pol.debrief(list(events), list(segs), count=3)
    questions = []
    for i, prompt in enumerate(prompts):
        q = models.Question(
            session_id=sess.id,
            timestamp_ms=int(datetime.utcnow().timestamp() * 1000) + i * 10,
            question_type=prompt.get("question_type", "rationale"),
            question_text=prompt.get("question") or "Tell me more about how you handle this step.",
        )
        db.add(q)
        db.commit()
        db.refresh(q)
        questions.append(
            {
                "question_id": q.id,
                "question_type": q.question_type,
                "question_text": q.question_text,
                "trigger_event_id": prompt.get("trigger_event_id"),
                "timestamp_ms": q.timestamp_ms,
            }
        )
    return {"session_id": sess.id, "questions": questions}


class AnswerPayload(BaseModel):
    answer_text: str


@router.post("/{session_id}/questions/{question_id}/answer")
def answer_question(session_id: str, question_id: str, payload: AnswerPayload, db: Session = Depends(get_db)):
    q = db.get(models.Question, question_id)
    if not q or q.session_id != session_id:
        raise HTTPException(status_code=404, detail="Question not found")
    q.answer_text = payload.answer_text
    q.answered_at = datetime.utcnow()
    db.commit()
    db.refresh(q)
    return {
        "question_id": q.id,
        "answer_text": q.answer_text,
        "answered_at": q.answered_at,
    }


@router.post("/{session_id}/work-map/generate")
def generate_work_map(session_id: str, db: Session = Depends(get_db)):
    sess_svc = SessionService(db)
    sess = sess_svc.get_session(session_id)
    ev_svc = EventService(db)
    tr_svc = TranscriptService(db)
    wm_svc = WorkMapService(db)
    events = ev_svc.list_events(sess)
    segments = tr_svc.list_segments(sess)
    wf = wm_svc.generate_workflow(sess, events, segments)
    return wm_svc.to_response(wf)
