"""Viewer API — Dynamic dashboard and statistics.

Provides real-time statistics and dashboard data for the memos-graph viewer.

v1.0.0-beta: Basic implementation with stats and activity metrics.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from memos_graph.db.session import get_session
from memos_graph.db.models import Chunk, Event, Promise, AgentState, Entity, EntityEdge

router = APIRouter()


class DashboardStats(BaseModel):
    """Dashboard statistics response."""
    total_chunks: int
    total_events: int
    total_promises: int
    total_entities: int
    total_relations: int
    active_agents: int
    chunks_last_24h: int
    events_last_24h: int
    promises_pending: int
    last_updated: datetime


class ActivityMetric(BaseModel):
    """Activity metric for charts."""
    timestamp: datetime
    value: int
    metric_type: str


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    user_id: str = "default",
    session: AsyncSession = Depends(get_session),
):
    """Get dashboard statistics.

    Returns real-time counts and metrics for the viewer dashboard.
    """
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)

    # Total counts
    chunks_count = await session.execute(
        select(func.count(Chunk.id)).where(Chunk.user_id == user_id)
    )
    total_chunks = chunks_count.scalar() or 0

    events_count = await session.execute(
        select(func.count(Event.id)).where(Event.user_id == user_id)
    )
    total_events = events_count.scalar() or 0

    promises_count = await session.execute(
        select(func.count(Promise.id)).where(Promise.user_id == user_id)
    )
    total_promises = promises_count.scalar() or 0

    entities_count = await session.execute(
        select(func.count(Entity.id)).where(Entity.user_id == user_id)
    )
    total_entities = entities_count.scalar() or 0

    relations_count = await session.execute(
        select(func.count(EntityEdge.id)).where(EntityEdge.user_id == user_id)
    )
    total_relations = relations_count.scalar() or 0

    # Active agents
    agents_count = await session.execute(
        select(func.count(AgentState.agent_id)).where(
            and_(
                AgentState.user_id == user_id,
                AgentState.last_interaction > yesterday,
            )
        )
    )
    active_agents = agents_count.scalar() or 0

    # Last 24h activity
    chunks_24h = await session.execute(
        select(func.count(Chunk.id)).where(
            and_(
                Chunk.user_id == user_id,
                Chunk.created_at > yesterday,
            )
        )
    )
    chunks_last_24h = chunks_24h.scalar() or 0

    events_24h = await session.execute(
        select(func.count(Event.id)).where(
            and_(
                Event.user_id == user_id,
                Event.created_at > yesterday,
            )
        )
    )
    events_last_24h = events_24h.scalar() or 0

    # Pending promises
    promises_pending = await session.execute(
        select(func.count(Promise.id)).where(
            and_(
                Promise.user_id == user_id,
                Promise.status == "pending",
            )
        )
    )
    promises_pending_count = promises_pending.scalar() or 0

    return DashboardStats(
        total_chunks=total_chunks,
        total_events=total_events,
        total_promises=total_promises,
        total_entities=total_entities,
        total_relations=total_relations,
        active_agents=active_agents,
        chunks_last_24h=chunks_last_24h,
        events_last_24h=events_last_24h,
        promises_pending=promises_pending_count,
        last_updated=now,
    )


@router.get("/dashboard/activity", response_model=List[ActivityMetric])
async def get_activity_metrics(
    metric_type: str = Query("chunks", description="Type of metric: chunks, events, promises"),
    days: int = Query(7, description="Number of days to look back"),
    user_id: str = "default",
    session: AsyncSession = Depends(get_session),
):
    """Get activity metrics for charts.

    Returns daily counts for the specified metric type.
    """
    now = datetime.utcnow()
    start_date = now - timedelta(days=days)

    if metric_type == "chunks":
        model = Chunk
        date_field = Chunk.created_at
    elif metric_type == "events":
        model = Event
        date_field = Event.created_at
    elif metric_type == "promises":
        model = Promise
        date_field = Promise.created_at
    else:
        return []

    # Group by date
    result = await session.execute(
        select(
            func.date_trunc('day', date_field).label('date'),
            func.count(model.id).label('count')
        )
        .where(
            and_(
                model.user_id == user_id,
                date_field > start_date,
            )
        )
        .group_by(func.date_trunc('day', date_field))
        .order_by(func.date_trunc('day', date_field))
    )

    rows = result.all()

    return [
        ActivityMetric(
            timestamp=row.date,
            value=row.count,
            metric_type=metric_type,
        )
        for row in rows
    ]


@router.get("/dashboard/top-entities", response_model=List[Dict[str, Any]])
async def get_top_entities(
    limit: int = Query(10, description="Number of top entities to return"),
    user_id: str = "default",
    session: AsyncSession = Depends(get_session),
):
    """Get top entities by connection count.

    Returns entities with the most relations.
    """
    result = await session.execute(
        select(
            Entity.name,
            Entity.entity_type,
            func.count(EntityEdge.id).label('relation_count')
        )
        .join(
            EntityEdge,
            and_(
                (EntityEdge.source_id == Entity.id) | (EntityEdge.target_id == Entity.id),
                EntityEdge.user_id == user_id,
            ),
            isouter=True
        )
        .where(Entity.user_id == user_id)
        .group_by(Entity.id, Entity.name, Entity.entity_type)
        .order_by(func.count(EntityEdge.id).desc())
        .limit(limit)
    )

    rows = result.all()

    return [
        {
            "name": row.name,
            "type": row.entity_type,
            "connections": row.relation_count,
        }
        for row in rows
    ]


@router.get("/dashboard/recent-events", response_model=List[Dict[str, Any]])
async def get_recent_events(
    limit: int = Query(10, description="Number of events to return"),
    user_id: str = "default",
    session: AsyncSession = Depends(get_session),
):
    """Get recent events for the activity feed.

    Returns the most recent events with basic info.
    """
    result = await session.execute(
        select(Event)
        .where(Event.user_id == user_id)
        .order_by(Event.created_at.desc())
        .limit(limit)
    )

    events = result.scalars().all()

    return [
        {
            "id": event.id,
            "type": event.event_type,
            "summary": event.summary,
            "created_at": event.created_at,
        }
        for event in events
    ]


@router.get("/dashboard/promises-status", response_model=Dict[str, int])
async def get_promises_status(
    user_id: str = "default",
    session: AsyncSession = Depends(get_session),
):
    """Get promises grouped by status.

    Returns count of promises in each status.
    """
    result = await session.execute(
        select(Promise.status, func.count(Promise.id))
        .where(Promise.user_id == user_id)
        .group_by(Promise.status)
    )

    rows = result.all()

    return {row.status: row.count for row in rows}


__all__ = ["router"]
