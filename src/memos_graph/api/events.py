"""Events endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from memos_graph.db.session import get_session
from memos_graph.db.models import Event
from datetime import datetime

router = APIRouter()


class EventCreate(BaseModel):
    """Create an event."""
    agent_id: str
    event_type: str
    actor: str
    payload: dict[str, Any]
    summary: Optional[str] = None


class EventResponse(BaseModel):
    """Event response."""
    id: int
    agent_id: str
    event_type: str
    actor: str
    payload: dict[str, Any]
    summary: Optional[str]
    created_at: datetime


@router.post("/events", response_model=EventResponse)
async def create_event(
    event: EventCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new event."""
    event_model = Event(
        agent_id=event.agent_id,
        event_type=event.event_type,
        actor=event.actor,
        payload=event.payload,
        summary=event.summary,
    )
    session.add(event_model)
    await session.commit()
    await session.refresh(event_model)

    return EventResponse(
        id=event_model.id,
        agent_id=event_model.agent_id,
        event_type=event_model.event_type,
        actor=event_model.actor,
        payload=event_model.payload,
        summary=event_model.summary,
        created_at=event_model.created_at,
    )


@router.get("/events", response_model=list[EventResponse])
async def list_events(
    agent_id: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session),
):
    """List events with optional filtering."""
    query = select(Event)

    if agent_id:
        query = query.where(Event.agent_id == agent_id)
    if event_type:
        query = query.where(Event.event_type == event_type)

    query = query.order_by(desc(Event.created_at)).limit(limit)
    result = await session.execute(query)
    events = result.scalars().all()

    return [
        EventResponse(
            id=e.id,
            agent_id=e.agent_id,
            event_type=e.event_type,
            actor=e.actor,
            payload=e.payload,
            summary=e.summary,
            created_at=e.created_at,
        )
        for e in events
    ]
