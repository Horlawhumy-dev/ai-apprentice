from app.db.connection import Base, engine
from app.models import models  # noqa: F401 ensure models registered


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
