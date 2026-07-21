"""Memory and context retrieval endpoints using the 7-stage recall engine."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from memos_graph.recall import RecallEngine, RecallRequest, RecallHit
from memos_graph.db.session import _async_session_factory
import time

router = APIRouter()


class RetrieveRequest(BaseModel):
    """Retrieval request with 7-stage recall strategy."""
    query: str = Field(..., description="Search query text")
    agent_id: str = Field(..., description="Agent ID to search within")
    top_k: int = Field(default=10, ge=1, le=50, description="Number of results to return")
    time_range_hours: Optional[int] = Field(
        default=None,
        ge=1,
        le=720,
        description="Optional time range filter (hours)"
    )
    # 召回策略配置
    fts_top_k: int = Field(default=150, description="FTS 召回数量")
    pattern_top_k: int = Field(default=100, description="Pattern 召回数量")
    time_top_k: int = Field(default=80, description="时间召回数量")
    rrf_top_k: int = Field(default=330, description="RRF 融合后给 LLM 的数量")
    use_llm_rerank: bool = Field(default=False, description="是否使用 LLM 重排")
    use_mmr: bool = Field(default=True, description="是否使用 MMR 多样性重排")
    mmr_diversity: float = Field(default=0.5, ge=0, le=1, description="MMR 多样性参数")
    # 性能模式
    performance_mode: str = Field(default="standard", description="性能模式：fast|standard|full")


class RetrieveResult(BaseModel):
    """Single retrieval result."""
    id: int
    type: str  # "memory", "event", "promise"
    content: str
    summary: Optional[str] = None
    score: float  # Final score after all stages
    created_at: Optional[str] = None
    metadata: Optional[dict] = None
    stage_source: Optional[str] = None  # Which stage this result came from


class RetrieveResponse(BaseModel):
    """Retrieval response."""
    query: str
    agent_id: str
    total_results: int
    results: list[RetrieveResult]
    search_time_ms: int
    stages_run: list[str]  # Which recall stages were executed


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve_context(request: RetrieveRequest):
    """
    Retrieve relevant memories using the 7-stage recall engine.
    
    Stages:
    1. FTS (150) - PostgreSQL tsvector full-text search
    2. Pattern (100) - ILIKE pattern fuzzy matching
    3. Time (80) - Time-based recent priority
    4. RRF Fusion - Reciprocal Rank Fusion of 3 stages → Top 330
    5. LLM Rerank - LLM reranking (optional)
    6. MMR - Maximal Marginal Relevance for diversity
    7. Time Decay - Final time decay adjustment
    
    This provides:
    - Keyword precision (FTS)
    - Semantic understanding (Pattern + Time)
    - Diversity (MMR)
    - Temporal relevance (Time Decay)
    - Avoids token explosion by using efficient FTS first
    """
    try:
        # Initialize recall engine
        engine = RecallEngine()
        
        # Convert request to RecallRequest
        recall_req = RecallRequest(
            query=request.query,
            agent_id=request.agent_id,
            max_results=request.top_k,
            fts_top_k=request.fts_top_k,
            pattern_top_k=request.pattern_top_k,
            time_top_k=request.time_top_k,
            rrf_top_k=request.rrf_top_k,
            use_llm_expand=request.use_llm_rerank,
            performance_mode=request.performance_mode,
            time_range_hours=request.time_range_hours,
        )
        
        # Execute recall (5-stage: FTS → Pattern → Time → RRF → MMR → Time Decay)
        recall_result = await engine.search(recall_req)
        
        # Convert RecallHit to RetrieveResult
        results = []
        for hit in recall_result.hits:
            results.append(RetrieveResult(
                id=hit.chunk_id,
                type="memory",
                content=hit.content,
                summary=None,
                score=hit.final_score,
                created_at=hit.metadata.get("created_at") if hit.metadata else None,
                metadata=hit.metadata,
                stage_source=hit.stage_source,
            ))
        
        return RetrieveResponse(
            query=request.query,
            agent_id=request.agent_id,
            total_results=len(results),
            results=results,
            search_time_ms=recall_result.took_ms,
            stages_run=recall_result.stages_run,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recall failed: {str(e)}")
