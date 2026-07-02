"""Agent state endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from memos_graph.db.session import get_session
from memos_graph.db.models import AgentState
from datetime import datetime

router = APIRouter()


class AgentStateUpdate(BaseModel):
    """Update agent state."""
    stage: Optional[int] = None
    affinity: Optional[float] = None
    mood: Optional[float] = None
    energy: Optional[float] = None
    state: Optional[dict[str, Any]] = None
    version: Optional[int] = None  # For optimistic locking


class AgentStateResponse(BaseModel):
    """Agent state response."""
    agent_id: str
    pack_id: str
    stage: int
    affinity: float
    mood: float
    energy: float
    last_interaction: Optional[datetime]
    last_heartbeat: Optional[datetime]
    pending_heartbeat: bool
    state: dict[str, Any]
    version: int
    updated_at: datetime


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
        raise HTTPException(status_code=404, detail="Agent state not found")

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
        state=state.state,
        version=state.version,
        updated_at=state.updated_at,
    )


@router.put("/agents/{agent_id}/state", response_model=AgentStateResponse)
async def update_agent_state(
    agent_id: str,
    update: AgentStateUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update agent state with optimistic locking."""
    result = await session.execute(
        select(AgentState).where(AgentState.agent_id == agent_id)
    )
    state = result.scalar_one_or_none()

    if not state:
        # Create new state
        state = AgentState(agent_id=agent_id, pack_id="default")
        session.add(state)

    # Optimistic lock check
    if update.version is not None and state.version != update.version:
        raise HTTPException(
            status_code=409,
            detail="State was modified by another process. Please refresh and retry.",
        )

    # Update fields
    if update.stage is not None:
        state.stage = update.stage
    if update.affinity is not None:
        state.affinity = update.affinity
    if update.mood is not None:
        state.mood = update.mood
    if update.energy is not None:
        state.energy = update.energy
    if update.state is not None:
        state.state = update.state

    state.version += 1
    state.updated_at = datetime.utcnow()

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
        state=state.state,
        version=state.version,
        updated_at=state.updated_at,
    )


@router.post("/agents/{agent_id}/heartbeat")
async def trigger_heartbeat(
    agent_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Manually trigger a heartbeat for an agent."""
    result = await session.execute(
        select(AgentState).where(AgentState.agent_id == agent_id)
    )
    state = result.scalar_one_or_none()

    if not state:
        raise HTTPException(status_code=404, detail="Agent state not found")

    state.pending_heartbeat = True
    await session.commit()

    return {"status": "heartbeat_triggered", "agent_id": agent_id}
