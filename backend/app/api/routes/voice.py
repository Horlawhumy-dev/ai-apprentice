from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/voice", tags=["Voice"])


@router.get("/config")
def voice_config():
    configured = bool(settings.elevenlabs_api_key and settings.elevenlabs_agent_id)
    return {
        "provider": "elevenlabs" if configured else "prototype",
        "configured": configured,
        "agent_id": settings.elevenlabs_agent_id if configured else None,
        "mode": "realtime" if configured else "manual_transcript",
    }
