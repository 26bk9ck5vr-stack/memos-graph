"""Promises endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
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
        status="open",
    )
    session.add(promise_model)
    await session.commit()
    await session.refresh(promise_model)
    return promise_model


@router.put("/promises/{promise_id}", response_model=PromiseResponse)
async def update_promise(
    promise_id: int,
    update: PromiseUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a promise (mark as fulfilled/broken)."""
    result = await session.execute(select(Promise).where(Promise.id == promise_id))
    promise_model = result.scalar_one_or_none()
    
    if not promise_model:
        raise HTTPException(status_code=404, detail="Promise not found")
    
    if update.status is not None:
        promise_model.status = update.status
        if update.status == "fulfilled" and update.fulfilled_at is None:
            promise_model.fulfilled_at = datetime.utcnow()
        elif update.fulfilled_at is not None:
            promise_model.fulfilled_at = update.fulfilled_at
    
    await session.commit()
    await session.refresh(promise_model)
    return promise_model


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
