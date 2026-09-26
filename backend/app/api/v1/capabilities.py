"""
Capabilities Endpoint.
Exposes per-task supported inputs, available models, hardware parameters, and blocking reasons.
"""

from fastapi import APIRouter
from backend.app.models_registry import get_capabilities

router = APIRouter()


@router.get("/capabilities")
def list_capabilities():
    """Returns the operational capability matrix and scientific boundaries."""
    return {
        "capabilities": get_capabilities(),
        "hardware_profile": {
            "gpu": "NVIDIA GeForce RTX 5060 Laptop (8GB VRAM, sm_120 Blackwell)",
            "system_ram": "32 GB",
            "execution_strategy": "Subprocess-isolated environments + cross-process GPU filelock"
        }
    }
