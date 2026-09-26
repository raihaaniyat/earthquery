"""
Health Check Endpoints.
Implements bounded liveness and readiness probes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.db.session import get_db, check_db_connection
from backend.app.worker import check_redis_connection
from backend.app.services.storage import object_store

router = APIRouter()


@router.get("/health/live")
def live():
    """Fast process liveness check. Zero model or heavy resource initialization."""
    return {"status": "live"}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    """Readiness probe checking database, redis, and storage dependencies."""
    db_status = check_db_connection()
    redis_status = check_redis_connection()
    s3_available = object_store.is_s3_available()

    is_ready = db_status["connected"]

    resp = {
        "status": "ready" if is_ready else "not_ready",
        "database": db_status,
        "redis": redis_status,
        "object_storage": {
            "s3_endpoint": object_store.endpoint_url,
            "s3_available": s3_available,
            "local_storage_root": str(object_store.local_storage_root)
        }
    }

    if not is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=resp
        )

    return resp
