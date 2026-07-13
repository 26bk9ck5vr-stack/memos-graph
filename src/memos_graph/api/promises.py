"""Promises endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from memos_graph.db.session import get_session
from memos_graph.db.models import Promise
from datetime import datetime

router = APIRouter()


class PromiseCreate(BaseModel):
    """Create a promise."""
    agent_id: str
    user_id: Optional[str] = None
    content: str
    deadline: Optional[datetime] = None


class PromiseUpdate(BaseModel):
    """Update a promise."""
    status: Optional[str] = None  # open | fulfilled | broken | expired
    fulfilled_at: Optional[datetime] = None


class PromiseResponse(BaseModel):
    """Promise response."""
    id: int
    agent_id: str
    user_id: Optional[str]
    content: str
    status: str
    deadline: Optional[datetime]
    fulfilled_at: Optional[datetime]
    created_at: datetime


@router.post("/promises", response_model=PromiseResponse)
async def create_promise(
    promise: PromiseCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new promise."""
    promise_model = Promise(
        agent_id=promise.agent_id,
        user_id=promise.user_id,
        content=promise.content,
        deadline=promise.deadline,
    )
    session.add(promise_model)
    await session.commit()
    await session.refresh(promise_model)

    return PromiseResponse(
        id=promise_model.id,
        agent_id=promise_model.agent_id,
        user_id=promise_model.user_id,
        content=promise_model.content,
        status=promise_model.status,
        deadline=promise_model.deadline,
        fulfilled_at=promise_model.fulfilled_at,
        created_at=promise_model.created_at,
    )


@router.get("/promises", response_model=list[PromiseResponse])
async def list_promises(
    agent_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """List promises with optional filtering."""
    query = select(Promise)

    if agent_id:
        query = query.where(Promise.agent_id == agent_id)
    if status:
        query = query.where(Promise.status == status)

    result = await session.execute(query)
    promises = result.scalars().all()

    return [
        PromiseResponse(
            id=p.id,
            agent_id=p.agent_id,
            user_id=p.user_id,
            content=p.content,
            status=p.status,
            deadline=p.deadline,
            fulfilled_at=p.fulfilled_at,
            created_at=p.created_at,
        )
        for p in promises
    ]


@router.put("/promises/{promise_id}", response_model=PromiseResponse)
async def update_promise(
    promise_id: int,
    update: PromiseUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a promise."""
    result = await session.execute(
        select(Promise).where(Promise.id == promise_id)
    )
    promise = result.scalar_one_or_none()

    if not promise:
        raise HTTPException(status_code=404, detail="Promise not found")

    if update.status is not None:
        promise.status = update.status
        if update.status == "fulfilled" and promise.fulfilled_at is None:
            promise.fulfilled_at = datetime.utcnow()
    if update.fulfilled_at is not None:
        promise.fulfilled_at = update.fulfilled_at

    await session.commit()
    await session.refresh(promise)

    return PromiseResponse(
        id=promise.id,
        agent_id=promise.agent_id,
        user_id=promise.user_id,
        content=promise.content,
        status=promise.status,
        deadline=promise.deadline,
        fulfilled_at=promise.fulfilled_at,
        created_at=promise.created_at,
    )
