"""User profile endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from memos_graph.db.session import get_session
from memos_graph.db.models import UserProfile
from datetime import datetime

router = APIRouter()


class UserProfileUpdate(BaseModel):
    """Update user profile."""
    display_name: Optional[str] = None
    attributes: Optional[dict[str, Any]] = None


class UserProfileResponse(BaseModel):
    """User profile response."""
    user_id: str
    display_name: Optional[str]
    attributes: dict[str, Any]
    updated_at: datetime


@router.get("/users/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get user profile."""
    result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")

    return UserProfileResponse(
        user_id=profile.user_id,
        display_name=profile.display_name,
        attributes=profile.attributes,
        updated_at=profile.updated_at,
    )


@router.put("/users/{user_id}/profile", response_model=UserProfileResponse)
async def update_user_profile(
    user_id: str,
    update: UserProfileUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update user profile."""
    result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        # Create new profile
        profile = UserProfile(
            user_id=user_id,
            display_name=update.display_name,
            attributes=update.attributes or {},
        )
        session.add(profile)
    else:
        if update.display_name is not None:
            profile.display_name = update.display_name
        if update.attributes is not None:
            profile.attributes = update.attributes

    profile.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(profile)

    return UserProfileResponse(
        user_id=profile.user_id,
        display_name=profile.display_name,
        attributes=profile.attributes,
        updated_at=profile.updated_at,
    )
