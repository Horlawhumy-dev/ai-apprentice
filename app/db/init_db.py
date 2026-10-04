import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.connection import Base, describe_target, engine
from app.models import models  # noqa: F401 ensure models registered

log = logging.getLogger(__name__)

# `create_all` never alters an existing table, so columns added after a database was
# first created need an explicit, idempotent migration.
_ADDITIVE_COLUMNS = (
    "ALTER TABLE apprentice_sessions ADD COLUMN IF NOT EXISTS case_data JSON",
)


def init_db() -> None:
    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError:
        log.exception("Database unreachable at %s; skipping schema creation", describe_target())
        return

    if engine.dialect.name != "postgresql":
        return
    for statement in _ADDITIVE_COLUMNS:
        try:
            with engine.begin() as conn:
                conn.execute(text(statement))
        except SQLAlchemyError:
            log.exception("Additive migration failed: %s", statement)
            return