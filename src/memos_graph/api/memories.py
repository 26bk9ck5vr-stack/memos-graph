"""Memory (chunk) CRUD and search endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from memos_graph.db.session import get_session
from memos_graph.db.models import Chunk, ChunkVector
from datetime import datetime

logger = logging.getLogger(__name__)

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
    request: Request,
):
    """Create a new memory chunk with full ingest pipeline (entities, events, promises)."""
    from memos_graph.ingest import IngestPipeline
    from memos_graph.config import load_config
    from memos_graph.embedding import EmbeddingService
    from memos_graph.llm.client import LLMClient
    from memos_graph.db.models import Chunk
    from memos_graph.db.session import _async_session_factory
    from memos_graph.db.session import create_session_factory
    from sqlalchemy import select
    
    # Ensure session factory is initialized
    if _async_session_factory is None:
        cfg = load_config()
        create_session_factory(cfg.database.url)
    
    # Use global services from app.state if available, otherwise create new ones
    if hasattr(request.app.state, 'llm_client') and hasattr(request.app.state, 'embedding_service'):
        llm_client = request.app.state.llm_client
        embedding_service = request.app.state.embedding_service
    else:
        cfg = load_config()
        llm_client = LLMClient(
            base_url=cfg.llm.base_url,
            api_key=cfg.llm.api_key,
            model=cfg.llm.model,
            timeout=cfg.llm.timeout_seconds,
        )
        embedding_service = EmbeddingService(
            provider=cfg.embedding.provider,
            model=cfg.embedding.model,
            base_url=cfg.embedding.base_url,
            api_key=cfg.embedding.api_key,
            timeout=float(cfg.embedding.timeout_seconds),
        )
    
    # Create pipeline with shared services
    pipeline = IngestPipeline(
        llm_client=llm_client,
        embedding_service=embedding_service,
    )
    
    # Run full ingest pipeline with its own session
    result = await pipeline.ingest(
        text=memory.content,
        agent_id=memory.agent_id,
        session=None,  # Let pipeline create its own session
        user_id=memory.metadata.get("user_id") if memory.metadata else None,
        scope=memory.scope or "private",
        extract_entities=True,
        extract_events=True,
        extract_promises=True,
        merge_profile=False,
    )
    
    # Fetch the created chunk
    async with _async_session_factory() as session:
        chunk_result = await session.execute(
            select(Chunk).where(Chunk.id == result["chunk_id"])
        )
        chunk = chunk_result.scalar_one()
    
    return MemoryResponse(
        id=chunk.id,
        agent_id=chunk.agent_id,
        scope=chunk.scope,
        role=memory.role,
        content=chunk.content,
        metadata=chunk.metadata_,
        created_at=chunk.created_at,
        updated_at=chunk.updated_at,
    )


@router.get("/memories", response_model=list[MemoryResponse])
async def list_memories(
    agent_id: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
):
    """List memory chunks for an agent."""
    result = await session.execute(
        select(Chunk)
        .where(Chunk.agent_id == agent_id)
        .order_by(Chunk.created_at.desc())
        .limit(limit)
    )
    chunks = result.scalars().all()
    return [
        MemoryResponse(
            id=c.id,
            agent_id=c.agent_id,
            scope=c.scope,
            role=c.role,
            content=c.content,
            metadata=c.metadata_,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in chunks
    ]


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
    """Search memories using 5-stage recall (FTS + Vector + RRF + MMR + Graph)."""
    from memos_graph.recall import RecallEngine, RecallRequest
    from memos_graph.config import load_config
    
    cfg = load_config()
    engine = RecallEngine(
        embedding_provider=cfg.embedding.provider,
        embedding_model=cfg.embedding.model,
        embedding_base_url=cfg.embedding.base_url,
        embedding_api_key=cfg.embedding.api_key,
        embedding_timeout=float(cfg.embedding.timeout_seconds),
    )
    req = RecallRequest(
        query=request.query,
        agent_id=request.agent_id,
        scope=request.scope or "all",
        max_results=request.top_k,
    )
    recall_result = await engine.search(req)

    # Load full chunks
    chunk_ids = [h.chunk_id for h in recall_result.hits]
    if not chunk_ids:
        return SearchResponse(results=[], query=request.query)

    result = await session.execute(
        select(Chunk).where(Chunk.id.in_(chunk_ids))
    )
    chunks = result.scalars().all()
    chunk_map = {c.id: c for c in chunks}

    results = []
    for hit in recall_result.hits:
        if hit.chunk_id is None:
            logger.warning(f"Skipping hit with chunk_id=None, stage_source={hit.stage_source}, score={hit.score}")
            continue
        c = chunk_map.get(hit.chunk_id)
        if c:
            results.append(MemoryResponse(
                id=c.id,
                agent_id=c.agent_id,
                scope=c.scope,
                role=c.role,
                content=c.content,
                metadata=c.metadata_,
                created_at=c.created_at,
                updated_at=c.updated_at,
            ))
        else:
            logger.warning(f"Chunk not found for hit chunk_id={hit.chunk_id}, stage_source={hit.stage_source}")

    return SearchResponse(results=results, query=request.query)
