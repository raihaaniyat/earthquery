"""
Geospatial and Benchmark Ingestion & Preprocessing Subprocess.
Runs inside `satquery-core` with native GDAL, Rasterio, PyProj, Shapely.
Adheres strictly to the SubprocessRequest / SubprocessResponse protocol.
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure project root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np
from PIL import Image

try:
    import rasterio
    import rasterio.warp
    from rasterio.enums import Resampling
    from shapely.geometry import box, mapping, MultiPolygon, Polygon
    import pyproj
    HAS_GEO = True
except ImportError:
    HAS_GEO = False

from backend.runtime.protocol import (
    SubprocessRequest,
    SubprocessResponse,
    SubprocessMetrics,
    PROTOCOL_VERSION
)


def extract_raster_metadata(input_path: str, output_dir: str) -> Dict[str, Any]:
    """
    Inspects input file, determining whether it is a GeoTIFF with genuine CRS/transform
    or a benchmark pixel-space image (PNG/JPG).
    """
    path_obj = Path(input_path)
    ext = path_obj.suffix.lower()
    t0 = time.time()
    
    is_geotiff = ext in [".tif", ".tiff"]
    
    metadata = {
        "file_name": path_obj.name,
        "coordinate_space": "pixel",
        "native_crs_epsg": None,
        "native_crs_wkt": None,
        "width": 0,
        "height": 0,
        "band_count": 0,
        "dtype": "uint8",
        "nodata_value": None,
        "affine_transform": None,
        "footprint_geojson": None,
        "pixel_size_x": 1.0,
        "pixel_size_y": 1.0,
        "pixel_unit": "pixel",
        "preview_path": None,
        "cog_path": None,
    }

    out_dir_path = Path(output_dir)
    out_dir_path.mkdir(parents=True, exist_ok=True)
    preview_path = str(out_dir_path / f"{path_obj.stem}_preview.png")

    if is_geotiff and HAS_GEO:
        try:
            with rasterio.open(input_path) as src:
                metadata["width"] = src.width
                metadata["height"] = src.height
                metadata["band_count"] = src.count
                metadata["dtype"] = str(src.dtypes[0])
                metadata["nodata_value"] = src.nodata
                
                # Check for genuine georeferencing
                if src.crs is not None and not src.transform.is_identity:
                    metadata["coordinate_space"] = "geographic"
                    metadata["native_crs_wkt"] = src.crs.to_wkt()
                    metadata["native_crs_epsg"] = src.crs.to_epsg()
                    metadata["affine_transform"] = json.dumps(list(src.transform)[:6])
                    metadata["pixel_size_x"] = abs(src.transform.a)
                    metadata["pixel_size_y"] = abs(src.transform.e)
                    metadata["pixel_unit"] = "degree" if src.crs.is_geographic else "metre"
                    
                    # Compute WGS84 footprint
                    bounds = src.bounds
                    src_crs = src.crs
                    wgs84 = rasterio.crs.CRS.from_epsg(4326)
                    
                    left, bottom, right, top = rasterio.warp.transform_bounds(
                        src_crs, wgs84, bounds.left, bounds.bottom, bounds.right, bounds.top
                    )
                    poly = Polygon([(left, bottom), (right, bottom), (right, top), (left, top), (left, bottom)])
                    multi_poly = MultiPolygon([poly])
                    metadata["footprint_geojson"] = mapping(multi_poly)
                else:
                    metadata["coordinate_space"] = "pixel"

                # Read sample for preview
                # Handle multichannel or single-channel
                if src.count >= 3:
                    r = src.read(1)
                    g = src.read(2)
                    b = src.read(3)
                    rgb = np.stack([r, g, b], axis=-1)
                else:
                    g = src.read(1)
                    rgb = np.stack([g, g, g], axis=-1)
                
                # Normalize to 0-255 uint8
                if rgb.dtype != np.uint8:
                    p2, p98 = np.percentile(rgb, (2, 98))
                    if p98 > p2:
                        rgb = np.clip((rgb - p2) / (p98 - p2) * 255.0, 0, 255).astype(np.uint8)
                    else:
                        rgb = np.zeros_like(rgb, dtype=np.uint8)
                
                img = Image.fromarray(rgb)
                img.thumbnail((512, 512))
                img.save(preview_path, format="PNG")
                metadata["preview_path"] = preview_path

        except Exception as e:
            # Fallback if rasterio fails
            is_geotiff = False

    if not is_geotiff or metadata["width"] == 0:
        # Standard benchmark image (PNG/JPG)
        with Image.open(input_path) as pil_img:
            metadata["width"] = pil_img.width
            metadata["height"] = pil_img.height
            metadata["band_count"] = len(pil_img.getbands())
            metadata["dtype"] = "uint8"
            metadata["coordinate_space"] = "pixel"
            metadata["native_crs_epsg"] = None
            metadata["native_crs_wkt"] = None
            metadata["footprint_geojson"] = None
            
            # Save thumbnail preview
            thumb = pil_img.copy()
            thumb.thumbnail((512, 512))
            thumb.save(preview_path, format="PNG")
            metadata["preview_path"] = preview_path

    metadata["duration_ms"] = (time.time() - t0) * 1000.0
    return metadata


def main():
    parser = argparse.ArgumentParser(description="SatQuery Geospatial Ingestion Preprocessor")
    parser.add_argument("--request-json", type=str, required=True, help="Path to request JSON or JSON string")
    parser.add_argument("--response-json", type=str, required=True, help="Path to write response JSON")
    args = parser.parse_args()

    t_start = time.time()

    # Load request
    if os.path.exists(args.request_json):
        with open(args.request_json, "r", encoding="utf-8") as f:
            req_data = json.load(f)
    else:
        req_data = json.loads(args.request_json)

    req = SubprocessRequest(**req_data)
    
    try:
        input_file = req.asset_references.get("original")
        if not input_file or not os.path.exists(input_file):
            raise FileNotFoundError(f"Input asset 'original' not found: {input_file}")

        meta = extract_raster_metadata(input_file, req.output_dir)
        
        output_assets = {}
        if meta.get("preview_path"):
            output_assets["preview"] = meta["preview_path"]
        if meta.get("cog_path"):
            output_assets["cog"] = meta["cog_path"]

        resp = SubprocessResponse(
            protocol_version=PROTOCOL_VERSION,
            success=True,
            job_id=req.job_id,
            step_key=req.step_key,
            attempt_id=req.attempt_id,
            output_assets=output_assets,
            output_metadata=meta,
            metrics=SubprocessMetrics(
                duration_ms=(time.time() - t_start) * 1000.0,
                cudnn_enabled=False
            )
        )
    except Exception as e:
        resp = SubprocessResponse(
            protocol_version=PROTOCOL_VERSION,
            success=False,
            job_id=req.job_id,
            step_key=req.step_key,
            attempt_id=req.attempt_id,
            error_code="PREPROCESS_ERROR",
            error_message=str(e),
            metrics=SubprocessMetrics(
                duration_ms=(time.time() - t_start) * 1000.0,
                cudnn_enabled=False
            )
        )

    with open(args.response_json, "w", encoding="utf-8") as f:
        f.write(resp.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
