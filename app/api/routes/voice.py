import httpx
from fastapi import APIRouter, HTTPException

from app.services import voice_service

router = APIRouter(prefix="/voice", tags=["Voice"])


@router.get("/config")
def voice_config():
    configured = voice_service.is_configured()
    return {
        "provider": "elevenlabs",
        "configured": configured,
        "mode": "signed_url" if configured else "unavailable",
    }


@router.post("/token")
async def voice_token():
    if not voice_service.is_configured():
        raise HTTPException(status_code=503, detail="Voice provider is not configured")
    try:
        signed_url = await voice_service.mint_signed_url()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Voice provider request failed: {exc}") from exc
    return {"signed_url": signed_url, "expires_in": voice_service.SIGNED_URL_TTL_SECONDS}