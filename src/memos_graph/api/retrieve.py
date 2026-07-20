"""Memory and context retrieval endpoints with vector similarity search."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from memos_graph.db.session import get_session
from memos_graph.db.models import Chunk, ChunkVector, Event, EventVector
from datetime import datetime
import json

router = APIRouter()


class RetrieveRequest(BaseModel):
    """Retrieval request."""
    query: str = Field(..., description="Search query text")
    agent_id: str = Field(..., description="Agent ID to search within")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of results to return")
    search_types: list[str] = Field(
        default=["memories", "events"],
        description="Types to search: memories, events, promises"
    )
    time_range_hours: Optional[int] = Field(
        default=None,
        ge=1,
        le=720,
        description="Optional time range filter (hours)"
    )


class RetrieveResult(BaseModel):
    """Single retrieval result."""
    id: int
    type: str  # "memory", "event", "promise"
    content: str
    summary: Optional[str] = None
    score: float  # Similarity score (0-1, higher is better)
    created_at: datetime
    metadata: Optional[dict] = None


class RetrieveResponse(BaseModel):
    """Retrieval response."""
    query: str
    agent_id: str
    total_results: int
    results: list[RetrieveResult]
    search_time_ms: float


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_context(
    request: RetrieveRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Retrieve relevant memories and events using vector similarity search.
    
    This endpoint:
    1. Generates embedding for the query
    2. Searches for similar chunks and events
    3. Returns top-K results with similarity scores
    """
    start_time = datetime.utcnow()
    
    # Import embedding service
    from memos_graph.embedding import EmbeddingService
    from memos_graph.config import load_config
    
    cfg = load_config()
    embedding_service = EmbeddingService(
        model=cfg.embedding.model,
        base_url=cfg.embedding.base_url,
        api_key=cfg.embedding.api_key,
        timeout=float(cfg.embedding.timeout_seconds),
    )
    
    # 1. Generate query embedding
    try:
        query_vector = await embedding_service.embed(request.query)
        if not query_vector or len(query_vector) == 0:
            raise HTTPException(status_code=400, detail="Failed to generate query embedding")
        query_vec = query_vector if isinstance(query_vector, list) else []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")
    
    # Convert to JSON array string for SQL
    query_vec_json = json.dumps(query_vec)
    query_vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
    
    all_results = []
    
    # 2. Search memories (chunks)
    if "memories" in request.search_types:
        memory_results = await _search_memories(
            session, request.agent_id, query_vec_str, 
            request.top_k, request.time_range_hours
        )
        all_results.extend(memory_results)
    
    # 3. Search events
    if "events" in request.search_types:
        event_results = await _search_events(
            session, request.agent_id, query_vec_str,
            request.top_k, request.time_range_hours
        )
        all_results.extend(event_results)
    
    # 4. Sort by score and take top-K
    all_results.sort(key=lambda x: x.score, reverse=True)
    top_results = all_results[:request.top_k]
    
    # 5. Calculate search time
    search_time = (datetime.utcnow() - start_time).total_seconds() * 1000
    
    return RetrieveResponse(
        query=request.query,
        agent_id=request.agent_id,
        total_results=len(top_results),
        results=top_results,
        search_time_ms=search_time,
    )


async def _search_memories(
    session: AsyncSession,
    agent_id: str,
    query_vec_str: str,
    top_k: int,
    time_range_hours: Optional[int] = None,
) -> list[RetrieveResult]:
    """Search memories using cosine similarity."""
    
    # Build time filter
    time_filter = ""
    if time_range_hours:
        time_filter = f"AND c.created_at >= NOW() - INTERVAL '{time_range_hours} hours'"
    
    # Cosine similarity search using pgvector
    query = text(f"""
        SELECT 
            c.id,
            c.content,
            c.created_at,
            c.metadata as metadata,
            (1 - cosine_distance(cv.embedding, '{query_vec_str}'::vector)) as similarity
        FROM chunks c
        JOIN chunk_vectors cv ON c.id = cv.chunk_id
        WHERE c.agent_id = :agent_id
        {time_filter}
        ORDER BY similarity DESC
        LIMIT :limit
    """)
    
    result = await session.execute(
        query,
        {
            "agent_id": agent_id,
            "limit": top_k,
        }
    )
    
    rows = result.fetchall()
    
    results_list = []
    for row in rows:
        # Handle NaN and None similarity scores
        similarity = row.similarity
        if similarity is None or (isinstance(similarity, float) and (similarity != similarity)):  # NaN check
            similarity = 0.0
        
        results_list.append(
            RetrieveResult(
                id=row.id,
                type="memory",
                content=row.content[:500],  # Truncate long content
                summary=None,
                score=float(similarity),
                created_at=row.created_at,
                metadata=row.metadata if isinstance(row.metadata, dict) else None,
            )
        )
    
    return results_list


async def _search_events(
    session: AsyncSession,
    agent_id: str,
    query_vec_str: str,
    top_k: int,
    time_range_hours: Optional[int] = None,
) -> list[RetrieveResult]:
    """Search events using cosine similarity."""
    
    # Build time filter
    time_filter = ""
    if time_range_hours:
        time_filter = f"AND e.created_at >= NOW() - INTERVAL '{time_range_hours} hours'"
    
    # Cosine similarity search
    query = text(f"""
        SELECT 
            e.id,
            e.summary,
            e.payload,
            e.created_at,
            (1 - cosine_distance(ev.embedding, '{query_vec_str}'::vector)) as similarity
        FROM events e
        JOIN event_vectors ev ON e.id = ev.event_id
        WHERE e.agent_id = :agent_id
        {time_filter}
        ORDER BY similarity DESC
        LIMIT :limit
    """)
    
    result = await session.execute(
        query,
        {
            "agent_id": agent_id,
            "limit": top_k,
        }
    )
    
    rows = result.fetchall()
    
    results_list = []
    for row in rows:
        # Handle NaN and None similarity scores
        similarity = row.similarity
        if similarity is None or (isinstance(similarity, float) and (similarity != similarity)):  # NaN check
            similarity = 0.0
        
        results_list.append(
            RetrieveResult(
                id=row.id,
                type="event",
                content=row.summary or "",
                summary=row.summary,
                score=float(similarity),
                created_at=row.created_at,
                metadata=row.payload if isinstance(row.payload, dict) else None,
            )
        )
    
    return results_list


@router.get("/retrieve/test")
async def test_retrieval(
    agent_id: str = Query("hermes", description="Agent ID"),
):
    """
    Test retrieval endpoint with a sample query.
    Useful for verifying the retrieval system works.
    """
    test_query = "What did we discuss about plugins?"
    
    request = RetrieveRequest(
        query=test_query,
        agent_id=agent_id,
        top_k=5,
        search_types=["memories", "events"],
    )
    
    # Get current session
    from memos_graph.db.session import _async_session_factory
    async with _async_session_factory() as session:
        response = await retrieve_context(request, session)
    
    return {
        "test_query": test_query,
        "response": response,
        "status": "success" if response.total_results > 0 else "no_results",
    }
