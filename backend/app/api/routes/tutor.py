from fastapi import APIRouter

router = APIRouter(prefix="/tutor", tags=["Tutor"])


@router.get("/health")
def tutor_health():
    return {"status": "ok"}
