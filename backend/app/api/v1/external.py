"""
External Provider Endpoints (ISRO/NRSC BHOONIDHI & Bhuvan).
Exposes catalog discovery, authenticated STAC search, staged import,
and allowlisted Bhuvan OGC map overlay layers and statistics.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import User
from backend.app.auth import get_current_user, verify_project_access
from backend.app.services.bhoonidhi import bhoonidhi_provider, SUPPORTED_COLLECTIONS
from backend.app.services.bhuvan import bhuvan_provider, ALLOWLISTED_BHUVAN_LAYERS

router = APIRouter(prefix="/external")


class BhoonidhiSearchRequest(BaseModel):
    collections: List[str] = Field(..., description="List of target collections e.g. ['RS2_LISS3']")
    bbox: Optional[List[float]] = Field(None, description="[min_lon, min_lat, max_lon, max_lat]")
    datetime_range: Optional[str] = Field(None, description="RFC3339 interval e.g. '2026-01-01T00:00:00Z/2026-03-31T23:59:59Z'")
    limit: int = Field(20, le=500, description="Page limit (max 500)")
    page: int = Field(1, ge=1)


class BhoonidhiImportRequest(BaseModel):
    project_id: str
    collection_id: str
    item_id: str


class BhuvanStatisticsRequest(BaseModel):
    project_id: str
    aoi_polygon: Dict[str, Any]
    layer_identifier: str = "bhuvan:lulc_50k"
    job_id: Optional[str] = None
    finding_id: Optional[str] = None


@router.get("/providers")
def get_external_providers():
    """Returns configured provider status and operations without exposing secrets."""
    return {
        "providers": [
            {
                "id": "bhoonidhi",
                "name": "ISRO / NRSC BHOONIDHI Geoportal",
                "service_type": "STAC_CATALOG_AND_DOWNLOAD",
                "status": "ONLINE",
                "rate_limits": {
                    "token_requests_per_hour": 20,
                    "search_requests_per_second": 3,
                    "max_concurrent_downloads": 1
                },
                "collections_count": len(SUPPORTED_COLLECTIONS)
            },
            {
                "id": "bhuvan",
                "name": "ISRO / NRSC Bhuvan Thematic Geo-platform",
                "service_type": "WMS_WMTS_AND_THEMATIC_STATS",
                "status": "ONLINE",
                "allowlisted_layers_count": len(ALLOWLISTED_BHUVAN_LAYERS)
            }
        ]
    }


@router.get("/bhoonidhi/collections")
def list_bhoonidhi_collections():
    """Lists supported satellite collections for BHOONIDHI."""
    return {"collections": bhoonidhi_provider.list_collections()}


@router.post("/bhoonidhi/search")
def search_bhoonidhi_catalog(
    req: BhoonidhiSearchRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Performs authenticated, rate-limited STAC metadata search on BHOONIDHI.
    Metadata search only; does not initiate downloading or model execution.
    """
    try:
        results = bhoonidhi_provider.search(
            collections=req.collections,
            bbox=req.bbox,
            datetime_range=req.datetime_range,
            limit=req.limit,
            page=req.page
        )
        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"BHOONIDHI upstream provider error: {str(e)}"
        )


@router.post("/bhoonidhi/imports", status_code=status.HTTP_202_ACCEPTED)
def import_bhoonidhi_product(
    req: BhoonidhiImportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Enqueues an explicitly selected online item for controlled staged download and validation.
    """
    verify_project_access(req.project_id, current_user, db)

    try:
        result = bhoonidhi_provider.import_product(
            db=db,
            project_id=req.project_id,
            collection_id=req.collection_id,
            item_id=req.item_id,
            user_id=current_user.id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to import product from BHOONIDHI: {str(e)}"
        )


@router.get("/bhuvan/layers")
def list_bhuvan_layers():
    """Lists locally allowlisted and live-checked Bhuvan map overlay layers."""
    return {"layers": bhuvan_provider.get_allowlisted_layers()}


@router.post("/bhuvan/statistics")
def query_bhuvan_thematic_statistics(
    req: BhuvanStatisticsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Queries documented AOI-wise thematic statistics from Bhuvan and records context provenance.
    """
    verify_project_access(req.project_id, current_user, db)

    try:
        res = bhuvan_provider.get_thematic_statistics(
            db=db,
            aoi_polygon=req.aoi_polygon,
            layer_identifier=req.layer_identifier,
            job_id=req.job_id,
            finding_id=req.finding_id
        )
        return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to query Bhuvan statistics: {str(e)}"
        )
