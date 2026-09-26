"""
Assets Download & Streaming Endpoints.
Supports range requests, streaming responses, and authenticated access.
"""

import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, status

from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import Asset, User
from backend.app.auth import get_current_user, verify_project_access
from backend.app.services.storage import object_store

router = APIRouter(prefix="/assets")


@router.get("/{asset_id}/download")
def download_asset(
    asset_id: str,
    range: Optional[str] = Header(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Downloads or streams an asset file. Supports HTTP byte-range requests.
    """
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

    verify_project_access(asset.project_id, current_user, db)

    local_path = object_store.get_local_path(asset.bucket, asset.storage_key)
    if not os.path.exists(local_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset binary file not found.")

    # Return file response with appropriate media type
    filename = os.path.basename(asset.storage_key)
    return FileResponse(
        path=local_path,
        media_type=asset.media_type,
        filename=filename
    )
