"""简化版召回 API - 直接使用 SQL，不依赖 recall 引擎"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from memos_graph.db.session import _async_session_factory, create_session_factory
from memos_graph.config import load_config
from sqlalchemy import text
import time

# 确保 session factory 已初始化
if _async_session_factory is None:
    cfg = load_config()
    create_session_factory(cfg.database.url)
    from memos_graph.db.session import _async_session_factory as factory
else:
    factory = _async_session_factory

router = APIRouter()


class RetrieveRequest(BaseModel):
    query: str = Field(..., description="Search query")
    agent_id: str = Field(..., description="Agent ID")
    top_k: int = Field(default=5, ge=1, le=50)
    performance_mode: str = Field(default="fast", description="fast|standard|full")
    time_range_hours: Optional[int] = None


class RetrieveResult(BaseModel):
    id: int
    content: str
    score: float
    stage_source: str


class RetrieveResponse(BaseModel):
    query: str
    agent_id: str
    total_results: int
    results: list[RetrieveResult]
    search_time_ms: int
    stages_run: list[str]


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(request: RetrieveRequest):
    """简化版召回 - 直接使用 FTS SQL"""
    start = time.time()
    
    # 使用已初始化的 factory
    if factory is None:
        raise HTTPException(500, "Database not initialized")
    
    async with factory() as session:
        # 根据性能模式调整参数
        if request.performance_mode == "fast":
            fts_top_k = 20
            time_top_k = 20
            time_range = request.time_range_hours or 72  # 3 天
        elif request.performance_mode == "standard":
            fts_top_k = 50
            time_top_k = 50
            time_range = request.time_range_hours or 168  # 7 天
        else:  # full
            fts_top_k = 150
            time_top_k = 80
            time_range = request.time_range_hours or 720
        
        # FTS 查询
        time_filter = f"AND c.created_at >= NOW() - INTERVAL '{time_range} hours'" if time_range else ""
        
        sql = text(f"""
            SELECT c.id, c.content, 
                   ts_rank(c.tsvector, plainto_tsquery('simple', :query)) as score
            FROM chunks c
            WHERE c.agent_id = :agent_id
              AND c.tsvector IS NOT NULL
              AND c.tsvector @@ plainto_tsquery('simple', :query)
              {time_filter}
            ORDER BY score DESC
            LIMIT :top_k
        """)
        
        result = await session.execute(sql, {
            "query": request.query,
            "agent_id": request.agent_id,
            "top_k": fts_top_k,
        })
        
        rows = result.fetchall()
        
        results = [
            RetrieveResult(
                id=row.id,
                content=row.content[:500],
                score=float(row.score) if row.score else 0.0,
                stage_source="fts",
            )
            for row in rows
        ]
        
        elapsed = int((time.time() - start) * 1000)
        
        return RetrieveResponse(
            query=request.query,
            agent_id=request.agent_id,
            total_results=len(results),
            results=results,
            search_time_ms=elapsed,
            stages_run=["fts"],
        )
