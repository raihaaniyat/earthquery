"""
Inference tasks executed by background workers.
Isolates each model to separate execution lifecycles to protect 8GB VRAM.
Zero PyTorch or NumPy imports in this module.
"""

import os
import uuid
from typing import Dict, Any, Optional, List
from pathlib import Path

from backend.app.config import settings
from backend.runtime.protocol import SubprocessRequest, SubprocessResponse
from backend.runtime.supervisor import supervisor


def execute_internvl_task(image_path: str, prompt: str = "Describe this satellite scene.", context: str = "") -> Dict[str, Any]:
    """Executes single-image VQA using InternVL3-2B in satquery-core."""
    req_id = str(uuid.uuid4())
    out_dir = str(Path(settings.SATQUERY_STORAGE_ROOT) / "scratch" / req_id)
    req = SubprocessRequest(
        job_id=req_id,
        step_key="internvl_vqa",
        attempt_id="1",
        model_version_id="internvl3",
        task_type="vqa",
        asset_references={"image": os.path.abspath(image_path)},
        parameters={"prompt": prompt, "max_tokens": settings.MAX_VQA_TOKENS, "context": context},
        output_dir=out_dir
    )
    resp: SubprocessResponse = supervisor.run_isolated_step(
        request=req,
        target_env=settings.CORE_ENV,
        entrypoint_module="backend.runtime.internvl",
        requires_gpu=True
    )
    return resp.model_dump()


def execute_croma_task(sentinel_1_path: Optional[str] = None, sentinel_2_path: Optional[str] = None) -> Dict[str, Any]:
    """Executes cross-modal feature extraction using CROMA in satquery-core."""
    req_id = str(uuid.uuid4())
    out_dir = str(Path(settings.SATQUERY_STORAGE_ROOT) / "scratch" / req_id)
    refs = {}
    if sentinel_1_path:
        refs["sentinel_1"] = os.path.abspath(sentinel_1_path)
    if sentinel_2_path:
        refs["sentinel_2"] = os.path.abspath(sentinel_2_path)

    req = SubprocessRequest(
        job_id=req_id,
        step_key="croma_features",
        attempt_id="1",
        model_version_id="croma",
        task_type="feature_extraction",
        asset_references=refs,
        parameters={},
        output_dir=out_dir
    )
    resp: SubprocessResponse = supervisor.run_isolated_step(
        request=req,
        target_env=settings.CORE_ENV,
        entrypoint_module="backend.runtime.croma",
        requires_gpu=True
    )
    return resp.model_dump()


def execute_changeformer_task(image_t1_path: str, image_t2_path: str) -> Dict[str, Any]:
    """Executes bitemporal change detection using ChangeFormerV6 in satquery-changeformer."""
    req_id = str(uuid.uuid4())
    out_dir = str(Path(settings.SATQUERY_STORAGE_ROOT) / "scratch" / req_id)
    req = SubprocessRequest(
        job_id=req_id,
        step_key="changeformer_cd",
        attempt_id="1",
        model_version_id="changeformer",
        task_type="bitemporal_change",
        asset_references={"image_t1": os.path.abspath(image_t1_path), "image_t2": os.path.abspath(image_t2_path)},
        parameters={},
        output_dir=out_dir
    )
    resp: SubprocessResponse = supervisor.run_isolated_step(
        request=req,
        target_env=settings.CHANGEFORMER_ENV,
        entrypoint_module="backend.runtime.changeformer",
        requires_gpu=False
    )
    return resp.model_dump()


def execute_upernet_task(image_path: str) -> Dict[str, Any]:
    """Executes land cover scene segmentation demo with UPerNet ConvNeXt in satquery-core."""
    req_id = str(uuid.uuid4())
    out_dir = str(Path(settings.SATQUERY_STORAGE_ROOT) / "scratch" / req_id)
    req = SubprocessRequest(
        job_id=req_id,
        step_key="upernet_segmentation",
        attempt_id="1",
        model_version_id="upernet",
        task_type="land_cover_segmentation",
        asset_references={"image": os.path.abspath(image_path)},
        parameters={},
        output_dir=out_dir
    )
    resp: SubprocessResponse = supervisor.run_isolated_step(
        request=req,
        target_env=settings.CORE_ENV,
        entrypoint_module="backend.runtime.upernet",
        requires_gpu=True
    )
    return resp.model_dump()


def execute_geoground_task(image_path: str, prompt: str = "locate objects") -> Dict[str, Any]:
    """Executes open-vocabulary visual grounding with OWLv2 in satquery-core (<6GB VRAM limit)."""
    req_id = str(uuid.uuid4())
    out_dir = str(Path(settings.SATQUERY_STORAGE_ROOT) / "scratch" / req_id)
    req = SubprocessRequest(
        job_id=req_id,
        step_key="geoground_detection",
        attempt_id="1",
        model_version_id="geoground",
        task_type="visual_grounding",
        asset_references={"image": os.path.abspath(image_path)},
        parameters={"prompt": prompt, "threshold": 0.1},
        output_dir=out_dir
    )
    resp: SubprocessResponse = supervisor.run_isolated_step(
        request=req,
        target_env=settings.CORE_ENV,
        entrypoint_module="backend.runtime.geoground",
        requires_gpu=True,
        required_vram_mib=1024
    )
    return resp.model_dump()


def execute_change_vqa_task(image_t1_path: str, image_t2_path: str, prompt: str = "What changed between these two dates?") -> Dict[str, Any]:
    """Executes bitemporal natural language change reasoning using ChangeVQA in satquery-core."""
    req_id = str(uuid.uuid4())
    out_dir = str(Path(settings.SATQUERY_STORAGE_ROOT) / "scratch" / req_id)
    req = SubprocessRequest(
        job_id=req_id,
        step_key="change_vqa_reasoning",
        attempt_id="1",
        model_version_id="change_vqa",
        task_type="change_vqa",
        asset_references={"image_t1": os.path.abspath(image_t1_path), "image_t2": os.path.abspath(image_t2_path)},
        parameters={"prompt": prompt},
        output_dir=out_dir
    )
    resp: SubprocessResponse = supervisor.run_isolated_step(
        request=req,
        target_env=settings.CORE_ENV,
        entrypoint_module="backend.runtime.change_vqa",
        requires_gpu=True,
        required_vram_mib=1536
    )
    return resp.model_dump()


def execute_optical_sar_task(sentinel_1_path: Optional[str] = None, sentinel_2_path: Optional[str] = None) -> Dict[str, Any]:
    """Executes multi-label land cover classification using Optical-SAR Head in satquery-core."""
    req_id = str(uuid.uuid4())
    out_dir = str(Path(settings.SATQUERY_STORAGE_ROOT) / "scratch" / req_id)
    refs = {}
    if sentinel_1_path:
        refs["sentinel_1"] = os.path.abspath(sentinel_1_path)
    if sentinel_2_path:
        refs["sentinel_2"] = os.path.abspath(sentinel_2_path)

    req = SubprocessRequest(
        job_id=req_id,
        step_key="optical_sar_classification",
        attempt_id="1",
        model_version_id="optical_sar_head",
        task_type="optical_sar_classification",
        asset_references=refs,
        parameters={},
        output_dir=out_dir
    )
    resp: SubprocessResponse = supervisor.run_isolated_step(
        request=req,
        target_env=settings.CORE_ENV,
        entrypoint_module="backend.runtime.optical_sar_head",
        requires_gpu=True,
        required_vram_mib=2560
    )
    return resp.model_dump()


def execute_pipeline_task(
    file_paths: List[str],
    prompt: str = "Analyze this satellite scene.",
    pair_type: str = "single_image",
    user_intent: str = "scene_description",
    diagnostic_override: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the comprehensive multi-model collaborative analysis pipeline.
    Orchestrates all applicable models sequentially under the GPU lock.
    """
    from backend.app.services.multi_model_pipeline import run_multi_model_pipeline
    return run_multi_model_pipeline(
        file_paths=file_paths,
        prompt=prompt,
        pair_type=pair_type,
        user_intent=user_intent,
        diagnostic_override=diagnostic_override
    )



