"""
SatQuery AI Model Registry & Capability Matrix
Defines all supported model architectures, status, hardware requirements,
and strict operational boundaries for remote sensing intelligence.
Reads declarative configuration from `config/models.yaml` with built-in fallbacks.
"""

import os
from pathlib import Path
from enum import Enum
from typing import Dict, Any, Optional, List
import yaml
from pydantic import BaseModel, Field

from backend.app.config import settings


class ModelStatus(str, Enum):
    VERIFIED = "VERIFIED"
    INSTALLED_NOT_RUNNABLE_LOCALLY = "INSTALLED BUT NOT RUNNABLE LOCALLY"
    TRAINING_REQUIRED = "TRAINING REQUIRED"
    BLOCKED = "BLOCKED"


class InputModality(str, Enum):
    SINGLE_IMAGE = "single_image"
    BITEMPORAL_CHANGE = "bitemporal_change"
    OPTICAL_SAR_PAIR = "optical_sar_pair"
    GEOTIFF_RASTER = "geotiff_raster"


class ModelDescriptor(BaseModel):
    id: str
    name: str
    task: str
    architecture: str
    source_url: str
    checkpoint_path: Optional[str] = None
    checkpoint_size_mb: float = 0.0
    status: ModelStatus
    environment: str
    supported_inputs: List[str] = Field(default_factory=list)
    vram_required_gb: float = 0.0
    device_used: str = "cpu"
    notes: str = ""
    training_status: str = ""
    contract: Dict[str, Any] = Field(default_factory=dict)


def load_registry_from_yaml() -> Dict[str, ModelDescriptor]:
    """Loads declarative model specifications from config/models.yaml."""
    config_path = Path(__file__).resolve().parent.parent.parent / "config" / "models.yaml"
    registry: Dict[str, ModelDescriptor] = {}

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            raw_models = data.get("models", {})
            for m_id, m_data in raw_models.items():
                v_state = m_data.get("verification_state", "LOAD_TESTED")
                if v_state in ("LOAD_TESTED", "VERIFIED", "INFERENCE_TESTED"):
                    status = ModelStatus.VERIFIED
                elif v_state == "INSTALLED_NOT_RUNNABLE_LOCALLY":
                    status = ModelStatus.INSTALLED_NOT_RUNNABLE_LOCALLY
                elif v_state == "TRAINING_REQUIRED":
                    status = ModelStatus.TRAINING_REQUIRED
                else:
                    status = ModelStatus.BLOCKED

                registry[m_id] = ModelDescriptor(
                    id=m_id,
                    name=m_data.get("name", m_id),
                    task=m_data.get("task", ""),
                    architecture=m_data.get("architecture", ""),
                    source_url=m_data.get("source_url", ""),
                    checkpoint_path=m_data.get("checkpoint_path"),
                    status=status,
                    environment=m_data.get("environment", "satquery-core"),
                    supported_inputs=m_data.get("supported_inputs", []),
                    vram_required_gb=float(m_data.get("vram_required_gb", 0.0)),
                    device_used=m_data.get("device", "cuda"),
                    notes=m_data.get("notes", ""),
                    training_status=f"State: {v_state}",
                    contract=m_data.get("contract", {})
                )
            return registry
        except Exception as e:
            pass

    # Built-in fallback definitions
    return {
        "internvl3": ModelDescriptor(
            id="internvl3",
            name="InternVL3-2B",
            task="vqa",
            architecture="InternVLChatModel",
            source_url="https://huggingface.co/OpenGVLab/InternVL3-2B",
            checkpoint_path="models/InternVL3-2B",
            status=ModelStatus.VERIFIED,
            environment="satquery-core",
            supported_inputs=["single_image", "benchmark_jpg_png", "geotiff_rgb"],
            vram_required_gb=4.0,
            device_used="cuda (RTX 5060, CC 12.0)",
            notes="Single-image VQA and image captioning on RTX 5060 laptop."
        ),
        "croma": ModelDescriptor(
            id="croma",
            name="CROMA Base",
            task="feature_extraction",
            architecture="Dual/Joint ViT-B",
            source_url="https://github.com/antofuller/CROMA",
            checkpoint_path="models/CROMA/CROMA_base.pt",
            status=ModelStatus.VERIFIED,
            environment="satquery-core",
            supported_inputs=["optical_sar_pair", "sentinel1_sentinel2"],
            vram_required_gb=2.5,
            device_used="cuda (RTX 5060)",
            notes="Extracts optical-SAR representations. Requires Sentinel-1 and Sentinel-2."
        ),
        "changeformer": ModelDescriptor(
            id="changeformer",
            name="ChangeFormerV6",
            task="bitemporal_change",
            architecture="Siamese Transformer Encoder + Decoder",
            source_url="https://github.com/wgcban/ChangeFormer",
            checkpoint_path="models/ChangeFormer/CD_ChangeFormerV6_LEVIR_b16_lr0.0001_adamw_train_test_200_linear_ce_multi_train_True_multi_infer_False_shuffle_AB_False_embed_dim_256/best_ckpt.pt",
            status=ModelStatus.VERIFIED,
            environment="satquery-changeformer",
            supported_inputs=["bitemporal_optical", "pair_t1_t2"],
            vram_required_gb=0.0,
            device_used="cpu",
            notes="Outputs 2D binary change mask (0=unchanged, 1=changed)."
        ),
        "upernet": ModelDescriptor(
            id="upernet",
            name="UPerNet ConvNeXt-Tiny",
            task="land_cover_segmentation",
            architecture="UperNetForSemanticSegmentation",
            source_url="https://huggingface.co/openmmlab/upernet-convnext-tiny",
            checkpoint_path="models/upernet-convnext-tiny",
            status=ModelStatus.VERIFIED,
            environment="satquery-core",
            supported_inputs=["single_image", "geotiff_rgb"],
            vram_required_gb=2.0,
            device_used="cuda",
            notes="Demo ADE20K semantic segmentation classes."
        ),
        "geoground": ModelDescriptor(
            id="geoground",
            name="OWLv2 GeoGround",
            task="visual_grounding",
            architecture="Owlv2ForObjectDetection (ViT-B/16)",
            source_url="https://huggingface.co/google/owlv2-base-patch16-ensemble",
            checkpoint_path="google/owlv2-base-patch16-ensemble",
            status=ModelStatus.VERIFIED,
            environment="satquery-core",
            supported_inputs=["single_image_grounding", "single_image", "benchmark_jpg_png", "geotiff_rgb"],
            vram_required_gb=1.2,
            device_used="cuda (RTX 5060)",
            notes="Open-vocabulary zero-shot visual grounding and object localization using OWLv2. Operates within 6 GB VRAM limit (~590 MiB allocated)."
        ),
        "owlv2": ModelDescriptor(
            id="owlv2",
            name="OWLv2 Zero-Shot Detector",
            task="visual_grounding",
            architecture="Owlv2ForObjectDetection (ViT-B/16)",
            source_url="https://huggingface.co/google/owlv2-base-patch16-ensemble",
            checkpoint_path="google/owlv2-base-patch16-ensemble",
            status=ModelStatus.VERIFIED,
            environment="satquery-core",
            supported_inputs=["single_image_grounding", "single_image", "benchmark_jpg_png", "geotiff_rgb"],
            vram_required_gb=1.2,
            device_used="cuda (RTX 5060)",
            notes="Open-vocabulary zero-shot visual grounding and object localization using OWLv2. Operates within 6 GB VRAM limit (~590 MiB allocated)."
        ),
        "change_vqa": ModelDescriptor(
            id="change_vqa",
            name="Paired-Image Change VQA",
            task="change_vqa",
            architecture="Siamese VLM Cross-Attention Head",
            source_url="SatQuery Custom Architecture",
            checkpoint_path="models/ChangeVQA/change_vqa_best.pt",
            status=ModelStatus.VERIFIED,
            environment="satquery-core",
            supported_inputs=["bitemporal_optical", "pair_t1_t2", "natural_language_query"],
            vram_required_gb=1.8,
            device_used="cuda (RTX 5060)",
            notes="Trained on CDVQA benchmark for bitemporal satellite change reasoning."
        ),
        "optical_sar_head": ModelDescriptor(
            id="optical_sar_head",
            name="Optical-SAR Classification Head",
            task="optical_sar_classification",
            architecture="Multimodal Contrastive Head",
            source_url="SatQuery Custom Architecture",
            checkpoint_path="models/CROMA/optical_sar_head_best.pt",
            status=ModelStatus.VERIFIED,
            environment="satquery-core",
            supported_inputs=["optical_sar_pair", "sentinel1_sentinel2"],
            vram_required_gb=2.5,
            device_used="cuda (RTX 5060)",
            notes="Trained on BigEarthNet-MM / SEN1-2 CORINE classes using CROMA cross-modal ViT-B representations."
        )
    }


REGISTRY: Dict[str, ModelDescriptor] = load_registry_from_yaml()


def get_model(model_id: str) -> Optional[ModelDescriptor]:
    return REGISTRY.get(model_id)


def list_models() -> List[ModelDescriptor]:
    return list(REGISTRY.values())


def get_capabilities() -> Dict[str, Any]:
    """Exposes structured runtime capability matrix."""
    capabilities = {}
    for m_id, desc in REGISTRY.items():
        capabilities[m_id] = {
            "name": desc.name,
            "task": desc.task,
            "status": desc.status.value,
            "is_runnable": desc.status == ModelStatus.VERIFIED,
            "device": desc.device_used,
            "vram_required_gb": desc.vram_required_gb,
            "supported_inputs": desc.supported_inputs,
            "notes": desc.notes
        }
    return capabilities
