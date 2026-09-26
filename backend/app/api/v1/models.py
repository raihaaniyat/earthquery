"""
Model Versions API Endpoints.
"""

from typing import List
from fastapi import APIRouter
from backend.app.models_registry import list_models, ModelDescriptor

router = APIRouter(prefix="/model-versions")


@router.get("", response_model=List[ModelDescriptor])
def list_model_versions():
    """Lists verified model versions, architectures, and verification status."""
    return list_models()
