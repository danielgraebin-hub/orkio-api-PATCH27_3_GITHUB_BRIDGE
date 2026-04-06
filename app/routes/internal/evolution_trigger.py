from fastapi import APIRouter

router = APIRouter(prefix="/api/internal/evolution", tags=["evolution-trigger"])

@router.get("/trigger-health")
def evolution_trigger_health():
    return {"ok": True, "service": "evolution_trigger"}
