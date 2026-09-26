"""
SatQuery Subprocess Communication Protocol (v1)
Shared JSON protocol between the API/worker supervisor and isolated model/geospatial subprocesses.
This module has zero dependencies on PyTorch, GDAL, Rasterio, or CUDA.
"""

from typing import Any, Dict, List, Optional
import json

try:
    from pydantic import BaseModel, Field
except Exception:
    # Pure Python fallback when pydantic / pydantic_core binary extension is blocked or absent
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def model_dump(self) -> Dict[str, Any]:
            def _conv(v):
                if hasattr(v, "model_dump"):
                    return v.model_dump()
                elif isinstance(v, dict):
                    return {k: _conv(val) for k, val in v.items()}
                elif isinstance(v, list):
                    return [_conv(val) for val in v]
                return v
            return {k: _conv(v) for k, v in self.__dict__.items() if not k.startswith("_")}
        def model_dump_json(self, indent: int = 2) -> str:
            return json.dumps(self.model_dump(), indent=indent)

    def Field(default=None, default_factory=None, **kwargs):
        if default_factory is not None:
            return default_factory()
        return default

PROTOCOL_VERSION = "1.0"


class SubprocessRequest(BaseModel):
    protocol_version: str = PROTOCOL_VERSION
    job_id: str
    step_key: str
    attempt_id: str
    model_version_id: str
    task_type: str
    asset_references: Dict[str, str] = Field(default_factory=dict, description="role -> local file path or cache path")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    output_dir: str


class SubprocessMetrics(BaseModel):
    duration_ms: float
    peak_vram_mb: Optional[float] = None
    peak_ram_mb: Optional[float] = None
    device_name: Optional[str] = None
    cudnn_enabled: bool = False


class SubprocessResponse(BaseModel):
    protocol_version: str = PROTOCOL_VERSION
    success: bool
    job_id: str
    step_key: str
    attempt_id: str
    output_assets: Dict[str, str] = Field(default_factory=dict, description="asset_role -> absolute output path")
    output_metadata: Dict[str, Any] = Field(default_factory=dict)
    metrics: Optional[SubprocessMetrics] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
