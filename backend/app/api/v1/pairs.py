"""
Scene Pairs Endpoints.
Validates bitemporal optical and optical-SAR pairs against scientific pairing policies.
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import Scene, Asset, ScenePair, User
from backend.app.auth import get_current_user, verify_project_access
from backend.app.services.pairing import PairValidationService

router = APIRouter(prefix="/scene-pairs")


class CreatePairRequest(BaseModel):
    project_id: str
    scene_a_id: str
    scene_b_id: str
    asset_a_id: str
    asset_b_id: str
    pair_type: str  # 'bitemporal_optical' or 'optical_sar'
    policy_overrides: Optional[Dict[str, Any]] = None


@router.post("", status_code=status.HTTP_201_CREATED)
def validate_and_create_pair(
    req: CreatePairRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    verify_project_access(req.project_id, current_user, db)

    scene_a = db.query(Scene).filter(Scene.id == req.scene_a_id, Scene.project_id == req.project_id).first()
    scene_b = db.query(Scene).filter(Scene.id == req.scene_b_id, Scene.project_id == req.project_id).first()
    asset_a = db.query(Asset).filter(Asset.id == req.asset_a_id, Asset.project_id == req.project_id).first()
    asset_b = db.query(Asset).filter(Asset.id == req.asset_b_id, Asset.project_id == req.project_id).first()

    if not scene_a or not scene_b or not asset_a or not asset_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more specified scenes or assets were not found in this project."
        )

    if req.pair_type == "bitemporal_optical":
        pair = PairValidationService.validate_bitemporal_optical_pair(
            db=db,
            project_id=req.project_id,
            scene_a=scene_a,
            scene_b=scene_b,
            asset_a=asset_a,
            asset_b=asset_b,
            policy=req.policy_overrides
        )
    elif req.pair_type == "optical_sar":
        pair = PairValidationService.validate_optical_sar_pair(
            db=db,
            project_id=req.project_id,
            optical_scene=scene_a,
            sar_scene=scene_b,
            optical_asset=asset_a,
            sar_asset=asset_b,
            policy=req.policy_overrides
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported pair_type '{req.pair_type}'. Expected 'bitemporal_optical' or 'optical_sar'."
        )

    return {
        "id": pair.id,
        "project_id": pair.project_id,
        "pair_type": pair.pair_type,
        "status": pair.status,
        "rejection_reason": pair.rejection_reason,
        "time_gap_seconds": pair.time_gap_seconds,
        "overlap_fraction_a": pair.overlap_fraction_a,
        "overlap_fraction_b": pair.overlap_fraction_b,
        "alignment_method": pair.alignment_method,
        "policy_version": pair.policy_version
    }


@router.get("/{pair_id}")
def get_pair(
    pair_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pair = db.query(ScenePair).filter(ScenePair.id == pair_id).first()
    if not pair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scene pair not found.")

    verify_project_access(pair.project_id, current_user, db)

    return {
        "id": pair.id,
        "project_id": pair.project_id,
        "source_scene_a_id": pair.source_scene_a_id,
        "source_scene_b_id": pair.source_scene_b_id,
        "pair_type": pair.pair_type,
        "status": pair.status,
        "rejection_reason": pair.rejection_reason,
        "time_gap_seconds": pair.time_gap_seconds,
        "alignment_error": pair.alignment_error,
        "alignment_units": pair.alignment_units,
        "policy_version": pair.policy_version
    }
