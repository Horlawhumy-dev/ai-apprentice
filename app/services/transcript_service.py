from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import models
from app.schemas.schemas import TranscriptSegmentPayload


class TranscriptService:
    def __init__(self, db: Session):
        self.db = db

    def add_segment(self, session: models.Session, payload: TranscriptSegmentPayload) -> models.TranscriptSegment:
        if session.status == "off_record":
            raise HTTPException(status_code=400, detail="Cannot add transcript while off record")
        if session.status == "finished":
            raise HTTPException(status_code=400, detail="Cannot add transcript to finished session")
        segment = models.TranscriptSegment(
            session_id=session.id,
            timestamp_ms=payload.timestamp_ms,
            speaker=payload.speaker,
            text=payload.text,
            source=payload.source,
            off_record=False,
        )
        self.db.add(segment)
        self.db.commit()
        self.db.refresh(segment)
        return segment

    def list_segments(self, session: models.Session) -> list[models.TranscriptSegment]:
        return (
            self.db.query(models.TranscriptSegment)
            .filter_by(session_id=session.id, off_record=False)
            .order_by(models.TranscriptSegment.timestamp_ms, models.TranscriptSegment.id)
            .all()
        )
