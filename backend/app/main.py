"""
FastAPI Main Application for SatQuery AI
Exposes RESTful v1 endpoints, health probes, legacy compatibility routes,
and model registry contracts.
"""

import os
import logging
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger("satquery.api")

from backend.app.config import settings
from backend.app.models_registry import list_models, get_model
from backend.app.input_validator import validate_geotiff, validate_benchmark_image, classify_pair_type
from backend.app.router import task_router_app
from backend.app.db.session import check_db_connection
from backend.app.worker import check_redis_connection
from backend.app.api.v1 import api_v1_router
from backend.app.api.v1.health import router as health_probes_router
from backend.app.api.frontend_bridge import router as frontend_bridge_router

app = FastAPI(
    title=settings.APP_NAME,
    description="Multimodal Earth Observation, Change Detection & Geospatial Intelligence API",
    version="2.0.0"
)

# CORS Middleware with configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount root health probes (/health/live, /health/ready)
app.include_router(health_probes_router)

# Mount REST API v1 (/api/v1/*)
app.include_router(api_v1_router)

# Mount frontend bridge routes (/api/analysis, /api/change-detection, etc.)
app.include_router(frontend_bridge_router, prefix="/api", tags=["Frontend Bridge"])


# Global Exception Handler for structured JSON error envelope
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail if isinstance(exc.detail, str) else "Request error",
                "details": exc.detail if not isinstance(exc.detail, str) else None
            },
            "path": request.url.path
        }
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled server exception at %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": f"An unexpected error occurred during processing: {type(exc).__name__}: {str(exc)}",
                "details": None
            },
            "path": request.url.path
        }
    )


# -------------------------------------------------------------
# Backward Compatibility Endpoints (Preserving Frontend Contract)
# -------------------------------------------------------------

@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "status": "online",
        "documentation": "/docs",
        "api_v1": "/api/v1"
    }


@app.get("/api/health")
def legacy_health():
    db_status = check_db_connection()
    redis_status = check_redis_connection()

    return {
        "status": "healthy",
        "hardware": {
            "gpu_name": "NVIDIA GeForce RTX 5060 Laptop GPU",
            "cuda_available": True,
            "cuda_version": "13.0",
            "compute_capability": [12, 0],
            "runtime_environment": "satquery-api (Python 3.11)",
        },
        "services": {
            "database_postgis": db_status,
            "redis_queue": redis_status,
            "rq_queue_name": settings.RQ_QUEUE_NAME
        },
        "environments": {
            "core": "satquery-core (Python 3.11, CUDA 13)",
            "changeformer": "satquery-changeformer (Python 3.9)",
            "geoground": "satquery-geoground (Python 3.10)"
        }
    }


@app.get("/api/models")
def legacy_get_models():
    """Lists all models and their current capability and training status."""
    return list_models()


@app.post("/api/validate/geotiff")
def validate_geotiff_endpoint(file_path: str):
    """Validates GeoTIFF headers, CRS, bounds, and Affine transform."""
    res = validate_geotiff(file_path)
    return res.to_dict()


@app.post("/api/validate/benchmark")
def validate_benchmark_endpoint(file_path: str):
    """Validates benchmark image in pixel coordinate space."""
    return validate_benchmark_image(file_path)


class TaskDispatchRequest(BaseModel):
    task: str
    input_category: str = "benchmark"  # "geotiff" or "benchmark"
    pair_type: str = "single_image"
    prompt: Optional[str] = "Describe this satellite scene."
    file_paths: List[str] = []


@app.post("/api/dispatch")
def dispatch_task(request: TaskDispatchRequest):
    """
    Submits a task through the LangGraph router.
    Routes execution to dedicated background workers.
    """
    state_input = {
        "task": request.task,
        "input_category": request.input_category,
        "file_paths": request.file_paths,
        "prompt": request.prompt or "",
        "pair_type": request.pair_type,
        "target_model_id": "",
        "validation_info": {},
        "dispatch_mode": "worker",
        "result": {}
    }

    routed_output = task_router_app.invoke(state_input)
    return {
        "target_model": routed_output.get("target_model_id"),
        "validation": routed_output.get("validation_info"),
        "result": routed_output.get("result")
    }


if __name__ == "__main__":
    import uvicorn
    config = uvicorn.Config(
        "backend.app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        loop="asyncio"
    )
    server = uvicorn.Server(config)
    server.run()

