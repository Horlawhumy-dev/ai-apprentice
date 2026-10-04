import httpx

from app.core.config import settings

_SIGNED_URL_ENDPOINT = "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url"
SIGNED_URL_TTL_SECONDS = 15 * 60


class VoiceNotConfigured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.elevenlabs_api_key and settings.elevenlabs_agent_id)


async def mint_signed_url() -> str:
    if not is_configured():
        raise VoiceNotConfigured()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            _SIGNED_URL_ENDPOINT,
            params={"agent_id": settings.elevenlabs_agent_id},
            headers={"xi-api-key": settings.elevenlabs_api_key},
        )
        response.raise_for_status()
        return response.json()["signed_url"]