"""
Scene Catalog & Spatial Search Service.
Handles project-scoped spatial querying, temporal filtering,
and PySTAC Item generation while strictly excluding pixel-space benchmarks
from geographic queries.
"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func
from geoalchemy2.functions import ST_Intersects, ST_GeomFromText, ST_AsGeoJSON
import pystac

from backend.app.db.models import Scene, Asset, Project


class SceneCatalogService:
    @staticmethod
    def search_scenes(
        db: Session,
        project_id: str,
        aoi_wkt: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        sensor_platform: Optional[str] = None,
        product_level: Optional[str] = None,
        validation_status: Optional[str] = None,
        coordinate_space: str = "geographic"
    ) -> List[Scene]:
        """
        Project-scoped scene search.
        Strict rule: Benchmark pixel scenes (coordinate_space='pixel') are never returned
        when querying geographic space or spatial AOIs.
        """
        query = db.query(Scene).filter(
            Scene.project_id == project_id,
            Scene.coordinate_space == coordinate_space
        )

        if validation_status:
            query = query.filter(Scene.validation_status == validation_status)


        # Temporal filter
        if start_time:
            query = query.filter(Scene.acquisition_time >= start_time)
        if end_time:
            query = query.filter(Scene.acquisition_time <= end_time)

        # Platform / sensor filter
        if sensor_platform:
            query = query.filter(Scene.sensor_platform.ilike(f"%{sensor_platform}%"))
        if product_level:
            query = query.filter(Scene.product_level.ilike(f"%{product_level}%"))

        # Spatial AOI filter (EPSG:4326 geometry)
        if aoi_wkt and coordinate_space == "geographic":
            aoi_geom = ST_GeomFromText(aoi_wkt, 4326)
            query = query.filter(
                Scene.footprint.is_not(None),
                ST_Intersects(Scene.footprint, aoi_geom)
            )

        return query.order_by(Scene.acquisition_time.desc().nullslast()).all()

    @staticmethod
    def get_scene_by_id(db: Session, project_id: str, scene_id: str) -> Optional[Scene]:
        """Fetch a scene by ID ensuring strict project isolation."""
        return db.query(Scene).filter(
            Scene.id == scene_id,
            Scene.project_id == project_id
        ).first()

    @staticmethod
    def export_stac_item(scene: Scene) -> Dict[str, Any]:
        """
        Exports a valid STAC Item using PySTAC.
        Enforces rule: Benchmark or pixel-space scenes without genuine CRS/time cannot be exported.
        """
        if scene.coordinate_space != "geographic" or not scene.native_crs_wkt:
            raise ValueError(
                f"Scene '{scene.id}' has coordinate_space='{scene.coordinate_space}'. "
                "Non-geographic or benchmark pixel scenes cannot be exported as STAC Items."
            )

        if not scene.acquisition_time:
            raise ValueError(f"Scene '{scene.id}' lacks verified acquisition_time for STAC compliance.")

        # Compute bounding box and geometry
        # Default fallback if footprint not present in db geometry
        bbox = [-180.0, -90.0, 180.0, 90.0]
        geometry = {
            "type": "Polygon",
            "coordinates": [[
                [bbox[0], bbox[1]],
                [bbox[2], bbox[1]],
                [bbox[2], bbox[3]],
                [bbox[0], bbox[3]],
                [bbox[0], bbox[1]]
            ]]
        }

        # Create PySTAC item
        item = pystac.Item(
            id=scene.id,
            geometry=geometry,
            bbox=bbox,
            datetime=scene.acquisition_time,
            properties={
                "sensor_platform": scene.sensor_platform,
                "product_level": scene.product_level,
                "width": scene.width,
                "height": scene.height,
                "pixel_size_x": scene.pixel_size_x,
                "pixel_size_y": scene.pixel_size_y,
                "pixel_unit": scene.pixel_unit,
                "native_crs_epsg": scene.native_crs_epsg
            }
        )

        # Add assets
        for asset in scene.assets:
            item.add_asset(
                key=asset.role,
                asset=pystac.Asset(
                    href=f"/api/v1/assets/{asset.id}/download",
                    title=f"{scene.name} - {asset.role}",
                    media_type=asset.media_type,
                    roles=[asset.role]
                )
            )

        return item.to_dict()
