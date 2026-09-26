"""
SatQuery AI REST API v1 Package.
"""

from fastapi import APIRouter

from backend.app.api.v1.health import router as health_router
from backend.app.api.v1.capabilities import router as capabilities_router
from backend.app.api.v1.projects import router as projects_router
from backend.app.api.v1.scenes import router as scenes_router
from backend.app.api.v1.pairs import router as pairs_router
from backend.app.api.v1.jobs import router as jobs_router
from backend.app.api.v1.findings import router as findings_router
from backend.app.api.v1.assets import router as assets_router
from backend.app.api.v1.reports import router as reports_router
from backend.app.api.v1.models import router as models_router
from backend.app.api.v1.auth_session import router as auth_session_router
from backend.app.api.v1.external import router as external_router

api_v1_router = APIRouter(prefix="/api/v1")

api_v1_router.include_router(auth_session_router, tags=["Authentication & Sessions"])
api_v1_router.include_router(capabilities_router, tags=["Capabilities"])
api_v1_router.include_router(projects_router, tags=["Projects"])
api_v1_router.include_router(scenes_router, tags=["Scenes"])
api_v1_router.include_router(pairs_router, tags=["Scene Pairs"])
api_v1_router.include_router(jobs_router, tags=["Analysis Jobs"])
api_v1_router.include_router(findings_router, tags=["Findings & Evidence"])
api_v1_router.include_router(assets_router, tags=["Assets"])
api_v1_router.include_router(reports_router, tags=["Reports"])
api_v1_router.include_router(models_router, tags=["Model Versions"])
api_v1_router.include_router(external_router, tags=["External Providers (ISRO/NRSC)"])

