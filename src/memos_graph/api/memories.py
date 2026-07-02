"""Memory (chunk) CRUD and search endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from memos_graph.db.session import get_session
from memos_graph.db.models import Chunk, ChunkVector
from datetime import datetime

router = APIRouter()


class MemoryCreate(BaseModel):
    """Create a new memory chunk."""
    agent_id: str
    scope: str = "private"
    role: Optional[str] = None
    content: str
    metadata: dict = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    """Update a memory chunk."""
    content: Optional[str] = None
    metadata: Optional[dict] = None
    scope: Optional[str] = None


class MemoryResponse(BaseModel):
    """Memory chunk response."""
    id: int
    agent_id: str
    scope: str
    role: Optional[str]
    content: str
    metadata: dict
    created_at: datetime
    updated_at: datetime


class SearchRequest(BaseModel):
    """Search request."""
    query: str
    agent_id: str
    scope: Optional[str] = None
    top_k: int = 10


class SearchResponse(BaseModel):
    """Search response."""
    results: list[MemoryResponse]
    query: str


@router.post("/memories", response_model=MemoryResponse)
async def create_memory(
    memory: MemoryCreate,
    session: AsyncSession = Depends(get_session),
):
    """Create a new memory chunk."""
    chunk = Chunk(
        agent_id=memory.agent_id,
        scope=memory.scope,
        role=memory.role,
        content=memory.content,
        metadata_=memory.metadata,
    )
    session.add(chunk)
    await session.commit()
    await session.refresh(chunk)

    return MemoryResponse(
        id=chunk.id,
        agent_id=chunk.agent_id,
        scope=chunk.scope,
        role=chunk.role,
        content=chunk.content,
        metadata=chunk.metadata_,
        created_at=chunk.created_at,
        updated_at=chunk.updated_at,
    )


@router.get("/memories/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get a memory chunk by ID."""
    result = await session.execute(
        select(Chunk).where(Chunk.id == memory_id)
    )
    chunk = result.scalar_one_or_none()

    if not chunk:
        raise HTTPException(status_code=404, detail="Memory not found")

    return MemoryResponse(
        id=chunk.id,
        agent_id=chunk.agent_id,
        scope=chunk.scope,
        role=chunk.role,
        content=chunk.content,
        metadata=chunk.metadata_,
        created_at=chunk.created_at,
        updated_at=chunk.updated_at,
    )


@router.put("/memories/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: int,
    update: MemoryUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update a memory chunk."""
    result = await session.execute(
        select(Chunk).where(Chunk.id == memory_id)
    )
    chunk = result.scalar_one_or_none()

    if not chunk:
        raise HTTPException(status_code=404, detail="Memory not found")

    if update.content is not None:
        chunk.content = update.content
    if update.metadata is not None:
        chunk.metadata_ = update.metadata
    if update.scope is not None:
        chunk.scope = update.scope

    chunk.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(chunk)

    return MemoryResponse(
        id=chunk.id,
        agent_id=chunk.agent_id,
        scope=chunk.scope,
        role=chunk.role,
        content=chunk.content,
        metadata=chunk.metadata_,
        created_at=chunk.created_at,
        updated_at=chunk.updated_at,
    )


@router.delete("/memories/{memory_id}")
async def delete_memory(
    memory_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete a memory chunk."""
    result = await session.execute(
        select(Chunk).where(Chunk.id == memory_id)
    )
    chunk = result.scalar_one_or_none()

    if not chunk:
        raise HTTPException(status_code=404, detail="Memory not found")

    await session.delete(chunk)
    await session.commit()

    return {"status": "deleted", "id": memory_id}


@router.post("/memories/search", response_model=SearchResponse)
async def search_memories(
    request: SearchRequest,
    session: AsyncSession = Depends(get_session),
):
    """Search memories using FTS + vector + RRF + MMR."""
    # TODO: Implement full 5-stage recall
    # For now, simple FTS search

    query = select(Chunk).where(
        Chunk.agent_id == request.agent_id,
        Chunk.content.ilike(f"%{request.query}%")
    )

    if request.scope:
        query = query.where(Chunk.scope == request.scope)

    query = query.limit(request.top_k)
    result = await session.execute(query)
    chunks = result.scalars().all()

    results = [
        MemoryResponse(
            id=chunk.id,
            agent_id=chunk.agent_id,
            scope=chunk.scope,
            role=chunk.role,
            content=chunk.content,
            metadata=chunk.metadata_,
            created_at=chunk.created_at,
            updated_at=chunk.updated_at,
        )
        for chunk in chunks
    ]

    return SearchResponse(results=results, query=request.query)
