"""
Geographic Location Identification & Spatial Overlap Resolver for SatQuery AI.
Derives evidence-based physical location (place, city, state, country) using:
1. Embedded GeoTIFF CRS and geotransform metadata.
2. Coordinate reprojection to WGS84 (EPSG:4326).
3. Common spatial footprint intersection for multi-image / temporal pairs.
4. Deterministic reverse geocoding via OpenStreetMap Nominatim with caching and graceful offline fallback.
Never hallucinates geographic names without empirical geospatial evidence.
"""

import os
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

logger = logging.getLogger("satquery.geo_lookup")

# Cache to avoid duplicate network requests
_GEO_CACHE: Dict[str, Dict[str, Any]] = {}


def extract_wgs84_bounds_and_center(file_path: str) -> Dict[str, Any]:
    """
    Extracts native CRS, bounds, and computes WGS84 (EPSG:4326) bounding box and centroid.
    """
    if not os.path.exists(file_path):
        return {"is_georeferenced": False, "error": f"File not found: {file_path}"}

    try:
        import rasterio
        from rasterio.warp import transform_bounds
        import pyproj
    except ImportError:
        return {
            "is_georeferenced": False,
            "error": "rasterio/pyproj not installed in runtime environment"
        }

    try:
        with rasterio.open(file_path) as src:
            if src.crs is None or src.transform.is_identity:
                return {
                    "is_georeferenced": False,
                    "file_name": Path(file_path).name,
                    "width": src.width,
                    "height": src.height,
                    "crs": None,
                    "limitations": ["Pixel-coordinate space only. Real-world CRS, geographic coordinates and physical area cannot be asserted."]
                }

            crs_str = src.crs.to_string()
            b = src.bounds
            native_bounds = [float(b.left), float(b.bottom), float(b.right), float(b.top)]

            # Transform to WGS84 EPSG:4326 if not already
            if src.crs.to_epsg() == 4326:
                wgs84_bounds = native_bounds
            else:
                wgs84_bounds = list(transform_bounds(src.crs, "EPSG:4326", *native_bounds))

            min_lon, min_lat, max_lon, max_lat = wgs84_bounds
            center_lat = float((min_lat + max_lat) / 2.0)
            center_lon = float((min_lon + max_lon) / 2.0)

            # Resolution calculation in metres
            res_x = abs(src.transform.a)
            resolution_m = round(float(res_x if src.crs.is_projected else res_x * 111320.0), 2)

            # Footprint area calculation
            from backend.app.services.raster_measurements import compute_geodesic_area_km2
            footprint_km2 = round(compute_geodesic_area_km2(
                (b.left, b.bottom, b.right, b.top),
                crs_str
            ), 3)

            return {
                "is_georeferenced": True,
                "file_name": Path(file_path).name,
                "crs": crs_str,
                "native_bounds": native_bounds,
                "wgs84_bounds": [round(c, 6) for c in wgs84_bounds],
                "center_lat": round(center_lat, 6),
                "center_lon": round(center_lon, 6),
                "resolution_m": resolution_m,
                "footprint_km2": footprint_km2
            }
    except Exception as e:
        logger.debug(f"Non-georeferenced or standard image {file_path}: {e}")
        return {
            "is_georeferenced": False,
            "file_name": Path(file_path).name,
            "limitations": [f"Image lacks genuine GeoTIFF geotransform: {str(e)}"]
        }


def compute_common_wgs84_footprint(path1: str, path2: str) -> Dict[str, Any]:
    """
    Computes spatial overlap and intersection extent between two georeferenced observations.
    """
    g1 = extract_wgs84_bounds_and_center(path1)
    g2 = extract_wgs84_bounds_and_center(path2)

    if not g1.get("is_georeferenced") or not g2.get("is_georeferenced"):
        return {
            "is_georeferenced": False,
            "is_overlapping": False,
            "reason": "One or both images lack embedded georeferencing metadata."
        }

    b1 = g1["wgs84_bounds"]
    b2 = g2["wgs84_bounds"]

    inter_left = max(b1[0], b2[0])
    inter_bottom = max(b1[1], b2[1])
    inter_right = min(b1[2], b2[2])
    inter_top = min(b1[3], b2[3])

    if inter_left < inter_right and inter_bottom < inter_top:
        common_bounds = [round(inter_left, 6), round(inter_bottom, 6), round(inter_right, 6), round(inter_top, 6)]
        center_lat = round((inter_bottom + inter_top) / 2.0, 6)
        center_lon = round((inter_left + inter_right) / 2.0, 6)

        from backend.app.services.raster_measurements import compute_geodesic_area_km2
        common_area_km2 = round(compute_geodesic_area_km2(
            (inter_left, inter_bottom, inter_right, inter_top),
            "EPSG:4326"
        ), 3)

        min_fp = min(g1.get("footprint_km2") or 1.0, g2.get("footprint_km2") or 1.0)
        overlap_pct = round(min(100.0, (common_area_km2 / max(min_fp, 0.001)) * 100.0), 1)

        return {
            "is_georeferenced": True,
            "is_overlapping": True,
            "common_bounds_wgs84": common_bounds,
            "center_lat": center_lat,
            "center_lon": center_lon,
            "common_area_km2": common_area_km2,
            "overlap_pct": overlap_pct,
            "crs_1": g1.get("crs"),
            "crs_2": g2.get("crs"),
            "resolution_m": min(g1.get("resolution_m") or 10.0, g2.get("resolution_m") or 10.0)
        }
    else:
        return {
            "is_georeferenced": True,
            "is_overlapping": False,
            "reason": "Georeferenced bounding boxes do not intersect in geographic space."
        }


def reverse_geocode_coordinates(lat: float, lon: float) -> Dict[str, Any]:
    """
    Performs deterministic reverse geocoding via OpenStreetMap Nominatim with
    caching and timeout. Gracefully handles network failures without hallucinating.
    """
    cache_key = f"{lat:.4f},{lon:.4f}"
    if cache_key in _GEO_CACHE:
        return _GEO_CACHE[cache_key]

    url = (
        f"https://nominatim.openstreetmap.org/reverse?"
        f"lat={lat}&lon={lon}&format=json&zoom=14&addressdetails=1"
    )
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SatQuery-AI/2.0 (Geospatial Research Suite)"}
    )

    try:
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            addr = data.get("address", {})

            # Clean specific place / neighbourhood
            place = (
                addr.get("neighbourhood") or
                addr.get("suburb") or
                addr.get("commercial") or
                addr.get("industrial") or
                addr.get("road") or
                addr.get("county") or
                "Identified municipal district"
            )

            city = (
                addr.get("city") or
                addr.get("town") or
                addr.get("municipality") or
                addr.get("village") or
                addr.get("city_district") or
                addr.get("county") or
                "Not resolved"
            )

            state = (
                addr.get("state") or
                addr.get("province") or
                addr.get("state_district") or
                addr.get("region") or
                "Not resolved"
            )

            country = addr.get("country") or "Not resolved"
            display_name = data.get("display_name", "")

            result = {
                "resolved": True,
                "place": place,
                "city": city,
                "state": state,
                "country": country,
                "display_name": display_name,
                "lat": lat,
                "lon": lon
            }
            _GEO_CACHE[cache_key] = result
            return result

    except Exception as e:
        logger.info(f"Reverse geocode lookup bypassed or offline ({lat}, {lon}): {e}")
        # Deterministic honest fallback without hallucination
        fallback = {
            "resolved": False,
            "place": "Not reliably resolved from available offline cadastral data",
            "city": "Not resolved",
            "state": "Not resolved",
            "country": "Not resolved",
            "display_name": f"Coordinates: {lat:.5f}° N, {lon:.5f}° E",
            "lat": lat,
            "lon": lon,
            "lookup_note": "Coordinates established from georeferenced raster bounds; municipal names require network lookup."
        }
        _GEO_CACHE[cache_key] = fallback
        return fallback


def identify_location_for_scenes(file_paths: List[str]) -> Dict[str, Any]:
    """
    Master location resolver for one or paired scenes.
    Calculates geographic intersection, resolves coordinates, and performs reverse geocoding.
    """
    valid_paths = [p for p in file_paths if os.path.exists(p)]
    if not valid_paths:
        return {
            "is_georeferenced": False,
            "resolved": False,
            "message": "No observation files supplied to resolve location."
        }

    if len(valid_paths) >= 2:
        pair_geo = compute_common_wgs84_footprint(valid_paths[0], valid_paths[1])
        if pair_geo.get("is_overlapping"):
            lat = pair_geo["center_lat"]
            lon = pair_geo["center_lon"]
            geo_info = reverse_geocode_coordinates(lat, lon)
            return {
                "is_temporal_pair": True,
                "is_georeferenced": True,
                "is_overlapping": True,
                "common_area_km2": pair_geo["common_area_km2"],
                "overlap_pct": pair_geo["overlap_pct"],
                "resolution_m": pair_geo["resolution_m"],
                "crs": pair_geo.get("crs_1"),
                "coordinates": {"lat": lat, "lon": lon},
                "place": geo_info["place"],
                "city": geo_info["city"],
                "state": geo_info["state"],
                "country": geo_info["country"],
                "display_name": geo_info.get("display_name"),
                "resolved": geo_info["resolved"]
            }
        elif pair_geo.get("is_georeferenced"):
            return {
                "is_temporal_pair": True,
                "is_georeferenced": True,
                "is_overlapping": False,
                "message": "Both scenes are georeferenced but do not share a common geographic footprint."
            }
        else:
            # Fallback to inspecting individual first image
            single_geo = extract_wgs84_bounds_and_center(valid_paths[0])
            if single_geo.get("is_georeferenced"):
                lat = single_geo["center_lat"]
                lon = single_geo["center_lon"]
                geo_info = reverse_geocode_coordinates(lat, lon)
                return {
                    "is_temporal_pair": True,
                    "is_georeferenced": True,
                    "is_overlapping": True,
                    "common_area_km2": single_geo.get("footprint_km2"),
                    "resolution_m": single_geo.get("resolution_m"),
                    "crs": single_geo.get("crs"),
                    "coordinates": {"lat": lat, "lon": lon},
                    "place": geo_info["place"],
                    "city": geo_info["city"],
                    "state": geo_info["state"],
                    "country": geo_info["country"],
                    "display_name": geo_info.get("display_name"),
                    "resolved": geo_info["resolved"]
                }
            return {
                "is_temporal_pair": True,
                "is_georeferenced": False,
                "resolved": False,
                "message": "Observation imagery is in pixel-coordinate space without embedded georeferencing metadata."
            }
    else:
        # Single image
        single_geo = extract_wgs84_bounds_and_center(valid_paths[0])
        if single_geo.get("is_georeferenced"):
            lat = single_geo["center_lat"]
            lon = single_geo["center_lon"]
            geo_info = reverse_geocode_coordinates(lat, lon)
            return {
                "is_temporal_pair": False,
                "is_georeferenced": True,
                "is_overlapping": True,
                "common_area_km2": single_geo.get("footprint_km2"),
                "resolution_m": single_geo.get("resolution_m"),
                "crs": single_geo.get("crs"),
                "coordinates": {"lat": lat, "lon": lon},
                "place": geo_info["place"],
                "city": geo_info["city"],
                "state": geo_info["state"],
                "country": geo_info["country"],
                "display_name": geo_info.get("display_name"),
                "resolved": geo_info["resolved"]
            }
        else:
            return {
                "is_temporal_pair": False,
                "is_georeferenced": False,
                "resolved": False,
                "message": "The uploaded image is in pixel-coordinate space without embedded geographic coordinate reference system (CRS) or GPS geotransform metadata."
            }
