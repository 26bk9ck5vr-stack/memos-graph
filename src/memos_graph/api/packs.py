"""Agent Pack management endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from memos_graph.db.session import get_session
from memos_graph.db.models import Pack
from memos_graph.pack.loader import PackLoader
from memos_graph.pack.installer import PackInstaller
from datetime import datetime, timezone
from pathlib import Path

router = APIRouter()


class PackResponse(BaseModel):
    """Pack response."""
    id: str
    name: str
    version: str
    manifest: Dict[str, Any] = {}
    install_path: Optional[str] = None
    enabled: bool = True
    installed_at: datetime
    updated_at: datetime


class PackCreate(BaseModel):
    """Pack creation request (deprecated - use PackInstallRequest)."""
    id: str
    name: str
    version: str
    manifest: Optional[Dict[str, Any]] = None
    install_path: Optional[str] = None


class PackInstallRequest(BaseModel):
    """Pack installation request."""
    source_path: str
    pack_id: Optional[str] = None


@router.post("/packs/install", response_model=PackResponse)
async def install_pack(
    request: PackInstallRequest,
    session: AsyncSession = Depends(get_session),
):
    """Install a pack from local path."""
    source_path = Path(request.source_path)
    
    # Check if pack already exists
    if not request.pack_id:
        # Try to load pack.yaml to get ID
        try:
            pack_id, _, _, _ = PackLoader.load_minimal(source_path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse pack.yaml: {e}")
    else:
        pack_id = request.pack_id
    
    # Check if already registered
    result = await session.execute(select(Pack).where(Pack.id == pack_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Pack already exists")
    
    # Install pack
    installer = PackInstaller()
    try:
        installed_id = installer.install_local(source_path, pack_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Load manifest for registration
    manifest = PackLoader.load(Path(installer.get_install_path(installed_id)))
    
    # Register in database
    new_pack = Pack(
        id=installed_id,
        name=manifest.get('name', installed_id),
        version=manifest.get('version', '0.1.0'),
        manifest=manifest,
        install_path=str(installer.get_install_path(installed_id)),
        enabled=True,
    )
    session.add(new_pack)
    await session.commit()
    await session.refresh(new_pack)
    
    return PackResponse(
        id=new_pack.id,
        name=new_pack.name,
        version=new_pack.version,
        manifest=new_pack.manifest or {},
        install_path=new_pack.install_path,
        enabled=new_pack.enabled,
        installed_at=new_pack.installed_at,
        updated_at=new_pack.updated_at,
    )


@router.get("/packs", response_model=List[PackResponse])
async def list_packs(
    enabled_only: bool = False,
    session: AsyncSession = Depends(get_session),
):
    """List all registered packs."""
    query = select(Pack)
    if enabled_only:
        query = query.where(Pack.enabled == True)
    
    result = await session.execute(query.order_by(Pack.name))
    packs = result.scalars().all()
    
    return [
        PackResponse(
            id=pack.id,
            name=pack.name,
            version=pack.version,
            manifest=pack.manifest or {},
            install_path=pack.install_path,
            enabled=pack.enabled,
            installed_at=pack.installed_at or datetime.now(timezone.utc),
            updated_at=pack.updated_at or datetime.now(timezone.utc),
        )
        for pack in packs
    ]


@router.get("/packs/{pack_id}", response_model=PackResponse)
async def get_pack(
    pack_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get pack by ID."""
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
        manifest=pack.manifest or {},
        install_path=pack.install_path,
        enabled=pack.enabled,
        installed_at=pack.installed_at or datetime.now(timezone.utc),
        updated_at=pack.updated_at or datetime.now(timezone.utc),
    )


@router.post("/packs", response_model=PackResponse)
async def register_pack(
    pack: PackCreate,
    session: AsyncSession = Depends(get_session),
):
    """Register a new pack."""
    # Check if pack already exists
    result = await session.execute(
        select(Pack).where(Pack.id == pack.id)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Pack already exists")
    
    # Create new pack
    new_pack = Pack(
        id=pack.id,
        name=pack.name,
        version=pack.version,
        manifest=pack.manifest or {},
        install_path=pack.install_path,
        enabled=True,
    )
    session.add(new_pack)
    await session.commit()
    await session.refresh(new_pack)
    
    return PackResponse(
        id=new_pack.id,
        name=new_pack.name,
        version=new_pack.version,
        manifest=new_pack.manifest or {},
        install_path=new_pack.install_path,
        enabled=new_pack.enabled,
        installed_at=new_pack.installed_at,
        updated_at=new_pack.updated_at,
    )


@router.put("/packs/{pack_id}/enable", response_model=PackResponse)
async def enable_pack(
    pack_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Enable a pack."""
    result = await session.execute(
        select(Pack).where(Pack.id == pack_id)
    )
    pack = result.scalar_one_or_none()
    
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    
    pack.enabled = True
    pack.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(pack)
    
    return PackResponse(
        id=pack.id,
        name=pack.name,
        version=pack.version,
        manifest=pack.manifest or {},
        install_path=pack.install_path,
        enabled=pack.enabled,
        installed_at=pack.installed_at,
        updated_at=pack.updated_at,
    )


@router.put("/packs/{pack_id}/disable", response_model=PackResponse)
async def disable_pack(
    pack_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Disable a pack."""
    result = await session.execute(
        select(Pack).where(Pack.id == pack_id)
    )
    pack = result.scalar_one_or_none()
    
    if not pack:
        raise HTTPException(status_code=404, detail="Pack not found")
    
    pack.enabled = False
    pack.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(pack)
    
    return PackResponse(
        id=pack.id,
        name=pack.name,
        version=pack.version,
        manifest=pack.manifest or {},
        install_path=pack.install_path,
        enabled=pack.enabled,
        installed_at=pack.installed_at,
        updated_at=pack.updated_at,
    )


@router.post("/heartbeat/check")
async def check_heartbeats(session: AsyncSession = Depends(get_session)):
    """Check and schedule pending heartbeats for all agents."""
    from memos_graph.heartbeat.scheduler import HeartbeatScheduler
    
    scheduler = HeartbeatScheduler(session)
    agent_ids = await scheduler.check_and_schedule()
    
    return {
        "scheduled": agent_ids,
        "count": len(agent_ids),
    }


@router.get("/heartbeat/pending")
async def get_pending_heartbeats(session: AsyncSession = Depends(get_session)):
    """Get all agents with pending heartbeats."""
    from memos_graph.heartbeat.scheduler import HeartbeatScheduler
    
    scheduler = HeartbeatScheduler(session)
    states = await scheduler.get_pending_heartbeats()
    
    return [
        {
            "agent_id": state.agent_id,
            "stage": state.stage,
            "affinity": state.affinity,
            "mood": state.mood,
            "last_interaction": state.last_interaction,
        }
        for state in states
    ]


@router.post("/heartbeat/{agent_id}/send")
async def send_heartbeat(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Mark a heartbeat as sent for an agent."""
    from memos_graph.heartbeat.scheduler import HeartbeatScheduler
    
    scheduler = HeartbeatScheduler(session)
    await scheduler.mark_heartbeat_sent(agent_id)
    
    return {"agent_id": agent_id, "status": "sent"}
