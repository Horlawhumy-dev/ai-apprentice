import logging

from sqlalchemy.exc import SQLAlchemyError

from app.db.connection import Base, describe_target, engine
from app.models import models  # noqa: F401 ensure models registered

log = logging.getLogger(__name__)


def init_db() -> None:
    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError:
        log.exception("Database unreachable at %s; skipping schema creation", describe_target())