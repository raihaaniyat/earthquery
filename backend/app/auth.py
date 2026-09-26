"""
Authentication & Authorization for SatQuery Local Development Profile.
Implements high-entropy bearer tokens hashed with SHA-256 at rest.
Enforces project isolation and ownership checks.
"""

import hashlib
import secrets
from typing import Optional, Tuple
from datetime import datetime, timezone
from fastapi import Header, HTTPException, Depends, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import User, ApiToken, Project, ProjectMember

DEFAULT_DEV_TOKEN = "satquery_local_dev_token_2026_blackwell"


def hash_token(raw_token: str) -> str:
    """Hashes API token with SHA-256 for safe storage at rest."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def seed_local_user_and_token(db: Session) -> Tuple[User, str]:
    """Ensures at least one local developer user and API token exist."""
    user = db.query(User).filter(User.email == "developer@satquery.local").first()
    if not user:
        user = User(
            email="developer@satquery.local",
            hashed_password=hash_token("satquery_local_secret"),
            full_name="SatQuery Local Developer",
            is_active=True,
            is_admin=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Check for active token
    token_h = hash_token(DEFAULT_DEV_TOKEN)
    token = db.query(ApiToken).filter(ApiToken.token_hash == token_h).first()
    if not token:
        token = ApiToken(
            user_id=user.id,
            name="local_dev_token",
            token_hash=token_h
        )
        db.add(token)
        db.commit()

    return user, DEFAULT_DEV_TOKEN


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """
    Authenticates principal via Bearer token.
    In local development, if no Authorization header is provided, automatically
    seeds and defaults to the local developer user.
    """
    if not authorization:
        # Default local dev user
        user, _ = seed_local_user_and_token(db)
        return user

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'."
        )

    raw_token = parts[1]
    token_h = hash_token(raw_token)

    api_token = db.query(ApiToken).filter(
        ApiToken.token_hash == token_h,
        ApiToken.revoked_at.is_(None)
    ).first()

    if not api_token or not api_token.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API token."
        )

    return api_token.user


def verify_project_access(
    project_id: str,
    user: User,
    db: Session,
    required_role: Optional[str] = None
) -> Project:
    """Verifies that the user owns or is a member of the requested project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{project_id}' not found.")

    if project.owner_id == user.id or user.is_admin:
        return project

    membership = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user.id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have access to this project."
        )

    return project
