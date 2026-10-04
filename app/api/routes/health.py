from fastapi import APIRouter

from app.db.connection import check_connection, describe_target

router = APIRouter(tags=["Health"])


@router.get("/health")
def health():
    reachable = check_connection()
    return {
        "status": "ok" if reachable else "degraded",
        "service": "ai-apprentice-api",
        "database": {"reachable": reachable, "target": describe_target()},
    }