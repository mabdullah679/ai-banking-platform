from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from platform_api.db import get_db

router = APIRouter(tags=["health"])


# Liveness: "is the process alive?" Kubernetes restarts the pod if this fails. No database check.
@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Readiness: "can I take traffic?" Fails with 503 when the database cannot be reached.
@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database not reachable") from None
    return {"status": "ready"}
