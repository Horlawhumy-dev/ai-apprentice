from typing import Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models import models


SessionStatus = Literal[
    "created",
    "capturing",
    "paused",
    "off_record",
    "finishing",
    "finished",
]


class InvalidStateTransition(Exception):
    pass


class SessionService:
    def __init__(self, db: Session):
        self.db = db

    def create_session(self, workflow_title: str, expert_name: str | None) -> models.Session:
        session = models.Session(
            workflow_title=workflow_title,
            expert_name=expert_name or "Expert",
            status="created",
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: str) -> models.Session:
        session = self.db.get(models.Session, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    def set_status(self, session: models.Session, new_status: SessionStatus) -> models.Session:
        transitions = self._allowed_transitions(session.status)
        if new_status not in transitions:
            raise HTTPException(status_code=400, detail=f"Invalid transition from {session.status} to {new_status}")
        session.status = new_status
        now = utcnow()
        if new_status == "capturing" and not session.started_at:
            session.started_at = now
        if new_status == "finishing":
            # mark as finishing; end time set on finish
            pass
        if new_status == "finished":
            session.ended_at = session.ended_at or now
        self.db.commit()
        self.db.refresh(session)
        return session

    def pause(self, session: models.Session) -> models.Session:
        return self.set_status(session, "paused")

    def resume(self, session: models.Session) -> models.Session:
        if session.status == "paused":
            return self.set_status(session, "capturing")
        if session.status == "off_record":
            return self.set_status(session, "capturing")
        raise HTTPException(status_code=400, detail="Can only resume from paused or off_record")

    def off_record(self, session: models.Session) -> models.Session:
        if session.status == "off_record":
            return session
        return self.set_status(session, "off_record")

    def finish(self, session: models.Session) -> models.Session:
        if session.status == "finished":
            return session
        if session.status == "created":
            return self.mark_finished(session)
        return self.set_status(session, "finishing")

    def mark_finished(self, session: models.Session) -> models.Session:
        session.status = "finished"
        session.ended_at = session.ended_at or utcnow()
        self.db.commit()
        self.db.refresh(session)
        return session

    @staticmethod
    def _allowed_transitions(current: str) -> set[str]:
        table = {
            "created": {"capturing"},
            "capturing": {"paused", "off_record", "finishing"},
            "paused": {"capturing", "off_record", "finishing"},
            "off_record": {"capturing", "finishing"},
            "finishing": {"finished"},
            "finished": set(),
        }
        return table.get(current, set())
