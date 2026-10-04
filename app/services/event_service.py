from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import models
from app.schemas.schemas import EventPayload


class EventService:
    def __init__(self, db: Session):
        self.db = db

    def add_event(self, session: models.Session, payload: EventPayload) -> models.Event:
        if session.status == "off_record":
            raise HTTPException(status_code=400, detail="Cannot add events while off record")
        if session.status == "finished":
            raise HTTPException(status_code=400, detail="Cannot add events to finished session")
        existing = self.db.query(models.Event).filter_by(client_event_id=payload.client_event_id).first()
        if existing:
            return existing
        event = models.Event(
            session_id=session.id,
            client_event_id=payload.client_event_id,
            timestamp_ms=payload.timestamp_ms,
            source=payload.source,
            type=payload.type,
            data=payload.data or {},
            frame_id=payload.frame_id,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def list_events(self, session: models.Session) -> list[models.Event]:
        return (
            self.db.query(models.Event)
            .filter_by(session_id=session.id)
            .order_by(models.Event.timestamp_ms, models.Event.id)
            .all()
        )
