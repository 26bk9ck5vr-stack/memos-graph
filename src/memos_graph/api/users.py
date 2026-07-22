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


class UserMergeRequest(BaseModel):
    """Merge user profiles request (cross-source identity resolution)."""
    source_user_id: str
    target_user_id: str
    merge_strategy: str = "overwrite"  # overwrite | merge | keep_both


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


@router.post("/users/{user_id}/merge")
async def merge_user_profiles(
    user_id: str,
    merge_request: UserMergeRequest,
    session: AsyncSession = Depends(get_session),
):
    """Merge two user profiles (cross-source user identity resolution)."""
    # Get target profile
    target_result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == merge_request.target_user_id)
    )
    target_profile = target_result.scalar_one_or_none()
    
    if not target_profile:
        target_profile = UserProfile(user_id=merge_request.target_user_id, attributes={})
        session.add(target_profile)
    
    # Get source profile
    source_result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == merge_request.source_user_id)
    )
    source_profile = source_result.scalar_one_or_none()
    
    if not source_profile:
        raise HTTPException(status_code=404, detail="Source user profile not found")
    
    # Merge based on strategy
    if merge_request.merge_strategy == "overwrite":
        if source_profile.display_name:
            target_profile.display_name = source_profile.display_name
        if source_profile.attributes:
            target_profile.attributes.update(source_profile.attributes)
    elif merge_request.merge_strategy == "merge":
        if not target_profile.display_name and source_profile.display_name:
            target_profile.display_name = source_profile.display_name
        if source_profile.attributes:
            for key, value in source_profile.attributes.items():
                if key not in target_profile.attributes:
                    target_profile.attributes[key] = value
    elif merge_request.merge_strategy == "keep_both":
        if "merged_from" not in target_profile.attributes:
            target_profile.attributes["merged_from"] = []
        target_profile.attributes["merged_from"].append(merge_request.source_user_id)
    
    await session.commit()
    await session.refresh(target_profile)
    
    return UserProfileResponse(
        user_id=target_profile.user_id,
        display_name=target_profile.display_name,
        attributes=target_profile.attributes,
        updated_at=target_profile.updated_at,
    )
