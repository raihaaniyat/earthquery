"""
Scenes & Ingestion API Endpoints.
Handles bounded streaming uploads, scene metadata inspection, spatial search,
and PySTAC item generation.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import Scene, User
from backend.app.auth import get_current_user, verify_project_access
from backend.app.services.ingestion import IngestionService
from backend.app.services.catalog import SceneCatalogService

router = APIRouter()


@router.post("/projects/{project_id}/scenes", status_code=status.HTTP_201_CREATED)
async def upload_scene(
    project_id: str,
    file: UploadFile = File(...),
    sensor_platform: Optional[str] = Form(None),
    product_level: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Streams file upload directly to storage and initiates ingestion metadata extraction.
    """
    verify_project_access(project_id, current_user, db)

    try:
        scene, asset = IngestionService.ingest_upload_stream(
            db=db,
            project_id=project_id,
            filename=file.filename,
            stream=file.file,
            media_type=file.content_type or "application/octet-stream",
            sensor_platform=sensor_platform,
            product_level=product_level
        )
        return {
            "scene_id": scene.id,
            "asset_id": asset.id,
            "filename": scene.name,
            "coordinate_space": scene.coordinate_space,
            "validation_status": scene.validation_status,
            "width": scene.width,
            "height": scene.height
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload ingestion failed: {str(e)}"
        )


@router.get("/projects/{project_id}/scenes")
def search_scenes(
    project_id: str,
    aoi_wkt: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    sensor_platform: Optional[str] = Query(None),
    product_level: Optional[str] = Query(None),
    validation_status: Optional[str] = Query(None),
    coordinate_space: str = Query("geographic"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Project-scoped scene search with spatial, temporal, and coordinate space filtering."""
    verify_project_access(project_id, current_user, db)

    scenes = SceneCatalogService.search_scenes(
        db=db,
        project_id=project_id,
        aoi_wkt=aoi_wkt,
        start_time=start_time,
        end_time=end_time,
        sensor_platform=sensor_platform,
        product_level=product_level,
        validation_status=validation_status,
        coordinate_space=coordinate_space
    )


    return [
        {
            "id": s.id,
            "name": s.name,
            "sensor_platform": s.sensor_platform,
            "product_level": s.product_level,
            "coordinate_space": s.coordinate_space,
            "acquisition_time": s.acquisition_time.isoformat() if s.acquisition_time else None,
            "width": s.width,
            "height": s.height,
            "validation_status": s.validation_status,
            "assets": [{"id": a.id, "role": a.role, "sha256": a.sha256_hash} for a in s.assets]
        } for s in scenes
    ]


@router.get("/scenes/{scene_id}")
def get_scene(
    scene_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves full scene metadata and associated assets."""
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found.")
    
    verify_project_access(scene.project_id, current_user, db)

    return {
        "id": scene.id,
        "project_id": scene.project_id,
        "name": scene.name,
        "sensor_platform": scene.sensor_platform,
        "product_level": scene.product_level,
        "coordinate_space": scene.coordinate_space,
        "native_crs_wkt": scene.native_crs_wkt,
        "native_crs_epsg": scene.native_crs_epsg,
        "width": scene.width,
        "height": scene.height,
        "pixel_size_x": scene.pixel_size_x,
        "pixel_size_y": scene.pixel_size_y,
        "pixel_unit": scene.pixel_unit,
        "validation_status": scene.validation_status,
        "validation_error": scene.validation_error,
        "assets": [
            {
                "id": a.id,
                "role": a.role,
                "byte_size": a.byte_size,
                "media_type": a.media_type,
                "sha256": a.sha256_hash
            } for a in scene.assets
        ]
    }


@router.get("/scenes/{scene_id}/stac")
def get_scene_stac(
    scene_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Exports compliant PySTAC Item for genuine geographic scenes."""
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene not found.")

    verify_project_access(scene.project_id, current_user, db)

    try:
        return SceneCatalogService.export_stac_item(scene)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
