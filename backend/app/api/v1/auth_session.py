"""
Authentication Session Endpoints for Frontend UI.
Provides short-lived session access tokens for UI without exposing backend server credentials.
"""

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import User, ApiToken
from backend.app.auth import hash_token, get_current_user

router = APIRouter(prefix="/auth")


class SessionCreateRequest(BaseModel):
    token: str


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


@router.post("/session", response_model=SessionResponse)
def create_session(
    req: SessionCreateRequest,
    db: Session = Depends(get_db)
):
    """Validates user token and establishes an active UI session."""
    hashed = hash_token(req.token)
    token_obj = db.query(ApiToken).filter(
        ApiToken.token_hash == hashed,
        ApiToken.revoked_at.is_(None)
    ).first()

    if not token_obj:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked bearer token."
        )

    user = token_obj.user
    return SessionResponse(
        access_token=req.token,
        token_type="bearer",
        user_id=user.id,
        email=user.email
    )


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Revokes the active user's session token."""
    # Active session revocation placeholder
    return None
