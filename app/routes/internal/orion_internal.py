from fastapi import APIRouter

router = APIRouter(prefix="/api/internal/orion", tags=["orion-internal"])

@router.get("/health")
def orion_health():
    return {"ok": True, "service": "orion_internal"}
