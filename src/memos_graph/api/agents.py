"""Agent state endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from memos_graph.db.session import get_session
from memos_graph.db.models import AgentState
from datetime import datetime, timezone

router = APIRouter()


class AgentStateResponse(BaseModel):
    """Agent state response."""
    agent_id: str
    pack_id: str
    stage: int
    affinity: float
    mood: float
    energy: float
    last_interaction: Optional[datetime] = None
    last_heartbeat: Optional[datetime] = None
    pending_heartbeat: bool = False
    state: Dict[str, Any] = {}
    version: int
    updated_at: datetime


class AgentStateUpdate(BaseModel):
    """Agent state update request."""
    stage: Optional[int] = None
    affinity: Optional[float] = None
    mood: Optional[float] = None
    energy: Optional[float] = None
    pending_heartbeat: Optional[bool] = None
    state: Optional[Dict[str, Any]] = None


@router.get("/agents/{agent_id}/state", response_model=AgentStateResponse)
async def get_agent_state(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get agent state."""
    result = await session.execute(
        select(AgentState).where(AgentState.agent_id == agent_id)
    )
    state = result.scalar_one_or_none()
    
    if not state:
        # Return default state if not exists
        return AgentStateResponse(
            agent_id=agent_id,
            pack_id="default",
            stage=1,
            affinity=0.0,
            mood=50.0,
            energy=50.0,
            last_interaction=None,
            last_heartbeat=None,
            pending_heartbeat=False,
            state={},
            version=1,
            updated_at=datetime.now(timezone.utc),
        )
    
    return AgentStateResponse(
        agent_id=state.agent_id,
        pack_id=state.pack_id,
        stage=state.stage,
        affinity=state.affinity,
        mood=state.mood,
        energy=state.energy,
        last_interaction=state.last_interaction,
        last_heartbeat=state.last_heartbeat,
        pending_heartbeat=state.pending_heartbeat,
        state=state.state or {},
        version=state.version,
        updated_at=state.updated_at,
    )


@router.put("/agents/{agent_id}/state", response_model=AgentStateResponse)
async def update_agent_state(
    agent_id: str,
    update: AgentStateUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update agent state."""
    # Get current state or create default
    result = await session.execute(
        select(AgentState).where(AgentState.agent_id == agent_id)
    )
    state = result.scalar_one_or_none()
    
    if not state:
        # Create new state
        state = AgentState(
            agent_id=agent_id,
            pack_id="default",
            stage=update.stage or 1,
            affinity=update.affinity or 0.0,
            mood=update.mood or 50.0,
            energy=update.energy or 50.0,
            pending_heartbeat=update.pending_heartbeat or False,
            state=update.state or {},
        )
        session.add(state)
    else:
        # Update existing state
        if update.stage is not None:
            state.stage = update.stage
        if update.affinity is not None:
            state.affinity = update.affinity
        if update.mood is not None:
            state.mood = update.mood
        if update.energy is not None:
            state.energy = update.energy
        if update.pending_heartbeat is not None:
            state.pending_heartbeat = update.pending_heartbeat
        if update.state is not None:
            state.state = update.state
        
        state.updated_at = datetime.now(timezone.utc)
        state.version += 1
    
    await session.commit()
    await session.refresh(state)
    
    return AgentStateResponse(
        agent_id=state.agent_id,
        pack_id=state.pack_id,
        stage=state.stage,
        affinity=state.affinity,
        mood=state.mood,
        energy=state.energy,
        last_interaction=state.last_interaction,
        last_heartbeat=state.last_heartbeat,
        pending_heartbeat=state.pending_heartbeat,
        state=state.state or {},
        version=state.version,
        updated_at=state.updated_at,
    )
