"""Pack management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from memos_graph.db.session import get_session
from memos_graph.db.models import Pack
from datetime import datetime

router = APIRouter()


class PackResponse(BaseModel):
    """Pack response."""
    id: str
    name: str
    version: str
    enabled: bool
    install_path: Optional[str]
    installed_at: datetime
    updated_at: datetime


@router.get("/packs", response_model=list[PackResponse])
async def list_packs(
    session: AsyncSession = Depends(get_session),
):
    """List all installed packs."""
    result = await session.execute(select(Pack))
    packs = result.scalars().all()

    return [
        PackResponse(
            id=p.id,
            name=p.name,
            version=p.version,
            enabled=p.enabled,
            install_path=p.install_path,
            installed_at=p.installed_at,
            updated_at=p.updated_at,
        )
        for p in packs
    ]


@router.get("/packs/{pack_id}", response_model=PackResponse)
async def get_pack(
    pack_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get a pack by ID."""
    result = await session.execute(
        select(Pack).where(Pack.id == pack_id)
    )
    pack = result.scalar_one_or_none()

    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")

    return PackResponse(
        id=pack.id,
        name=pack.name,
        version=pack.version,
        enabled=pack.enabled,
        install_path=pack.install_path,
        installed_at=pack.installed_at,
        updated_at=pack.updated_at,
    )
