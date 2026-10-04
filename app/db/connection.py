import os

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings

_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

if _serverless:
    engine = create_engine(settings.database_url, poolclass=NullPool, future=True)
else:
    engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def describe_target() -> str:
    try:
        url = make_url(settings.database_url)
    except ArgumentError:
        return "<unparseable DATABASE_URL>"
    host = url.host or "[unix socket]"
    port = f":{url.port}" if url.port else ""
    database = f"/{url.database}" if url.database else ""
    return f"{url.drivername}://{host}{port}{database}"


def check_connection() -> bool:
    try:
        with engine.connect():
            return True
    except SQLAlchemyError:
        return False


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()