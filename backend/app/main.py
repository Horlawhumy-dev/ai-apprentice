from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, sessions, workflows, apprentice, tutor, voice
from app.core.config import settings
from app.db.init_db import init_db

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.on_event("startup")
def on_startup():
    init_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=None if settings.environment == "production" else r"https?://.*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(workflows.router, prefix="/api")
app.include_router(apprentice.router, prefix="/api")
app.include_router(tutor.router, prefix="/api")
app.include_router(voice.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "AI Apprentice API", "docs": "/docs"}
