from fastapi import APIRouter

router = APIRouter(prefix="/api/internal/evolution", tags=["evolution-internal"])

@router.get("/health")
def evolution_health():
    return {"ok": True, "service": "evolution_internal"}
