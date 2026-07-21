"""完整召回 API - 集成 FTS + Pattern + Time + RRF + MMR + Time Decay + LLM Rerank"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from memos_graph.db.session import _async_session_factory, create_session_factory
from memos_graph.config import load_config
from sqlalchemy import text
from datetime import datetime, timedelta
import time
import math
import logging

# 懒加载 CrossEncoder
_reranker = None

def get_reranker():
    """懒加载 CrossEncoder reranker"""
    global _reranker
    if _reranker is None:
        logger = logging.getLogger(__name__)
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder('BAAI/bge-reranker-base')  # base 模型更快
            logger.info("CrossEncoder loaded successfully")
        except ImportError:
            logger.warning("sentence_transformers not installed, LLM rerank disabled")
            return None
        except Exception as e:
            logger.warning(f"CrossEncoder load error: {e}")
            return None
    return _reranker

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
    top_k: int = Field(default=10, ge=1, le=50)
    performance_mode: str = Field(default="fast", description="fast|standard|full")
    time_range_hours: Optional[int] = None
    # 高级配置
    fts_top_k: int = 150
    pattern_top_k: int = 100
    time_top_k: int = 80
    use_llm_rerank: bool = False  # 是否使用 LLM 重排
    use_mmr: bool = True
    mmr_diversity: float = 0.5  # 0-1, 越高越多样
    use_time_decay: bool = True
    decay_hours: int = 168  # 7 天半衰期


class RetrieveResult(BaseModel):
    id: int
    content: str
    score: float
    final_score: float
    stage_source: str
    created_at: Optional[datetime] = None


class RetrieveResponse(BaseModel):
    query: str
    agent_id: str
    total_results: int
    results: List[RetrieveResult]
    search_time_ms: int
    stages_run: List[str]


def calculate_time_decay(created_at: datetime, decay_hours: int) -> float:
    """计算时间衰减分数 (指数衰减，半衰期=decay_hours)"""
    if not created_at:
        return 1.0
    now = datetime.utcnow()
    age_hours = (now - created_at.replace(tzinfo=None)).total_seconds() / 3600
    # 指数衰减：score = 2^(-age/half_life)
    return math.pow(2, -age_hours / decay_hours)


def mmr_select(diverse_hits: List[dict], all_hits: dict, k: int, diversity: float) -> List[int]:
    """MMR (Maximal Marginal Relevance) 多样性重排
    
    Args:
        diverse_hits: 已选中的多样化结果 [{chunk_id, content, ...}]
        all_hits: 所有候选结果 {chunk_id: {content, score, ...}}
        k: 需要选择的数量
        diversity: 多样性参数 (0-1, 越高越多样)
    
    Returns:
        选中的 chunk_id 列表
    """
    if not all_hits or k <= 0:
        return []
    
    selected = []
    remaining = dict(all_hits)
    
    while len(selected) < k and remaining:
        best_chunk_id = None
        best_mmr_score = -float('inf')
        
        for chunk_id, hit in remaining.items():
            # 相关性分数 (已经包含 RRF 和时间衰减)
            relevance = hit.get('final_score', 0)
            
            # 冗余度惩罚 (与已选结果的最大相似度)
            max_similarity = 0
            if diverse_hits and diversity > 0:
                for selected_hit in diverse_hits:
                    # 简单的内容重叠度作为相似度
                    sim = len(set(hit['content'][:200].split()) & set(selected_hit['content'][:200].split())) / max(len(hit['content'][:200].split()), 1)
                    max_similarity = max(max_similarity, sim)
            
            # MMR 分数 = diversity * relevance - (1-diversity) * similarity
            mmr_score = diversity * relevance - (1 - diversity) * max_similarity
            
            if mmr_score > best_mmr_score:
                best_mmr_score = mmr_score
                best_chunk_id = chunk_id
        
        if best_chunk_id is None:
            break
        
        selected.append(best_chunk_id)
        diverse_hits.append(remaining[best_chunk_id])
        del remaining[best_chunk_id]
    
    return selected


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(request: RetrieveRequest):
    """完整召回 - FTS + Pattern + Time + RRF + MMR + Time Decay"""
    start = time.time()
    stages_run = []
    
    # 根据性能模式调整参数
    if request.performance_mode == "fast":
        request.fts_top_k = min(request.fts_top_k, 20)
        request.pattern_top_k = 0  # 禁用 Pattern 以提速
        request.time_top_k = min(request.time_top_k, 20)
        if request.time_range_hours is None:
            request.time_range_hours = 72
    elif request.performance_mode == "standard":
        request.fts_top_k = min(request.fts_top_k, 50)
        request.pattern_top_k = min(request.pattern_top_k, 30)
        request.time_top_k = min(request.time_top_k, 50)
        if request.time_range_hours is None:
            request.time_range_hours = 168
    # full 模式使用默认值
    
    if factory is None:
        raise HTTPException(500, "Database not initialized")
    
    async with factory() as session:
        # === Stage 1: FTS ===
        time_filter = f"AND c.created_at >= NOW() - INTERVAL '{request.time_range_hours} hours'" if request.time_range_hours else ""
        
        # === Stage 1: FTS (全文搜索) ===
        # P1 优化：jieba 中文分词 + 智能拆分
        def preprocess_query(query: str) -> str:
            """查询预处理：使用 jieba 智能分词"""
            import re
            
            # 策略 1: 按常见分隔符拆分
            parts = re.split(r'[\s,，.。?？!！;；:：]+', query)
            parts = [p.strip() for p in parts if p.strip()]
            
            # 策略 2: 如果查询太长 (>6 字符) 且没有自然分隔，使用 jieba 分词
            if len(parts) == 1 and len(query) > 6:
                try:
                    import jieba
                    # 使用精确模式分词
                    jieba_parts = list(jieba.cut(query))
                    # 过滤掉单字符 (除非是英文/数字)
                    jieba_parts = [
                        p for p in jieba_parts 
                        if len(p) > 1 or not p.isalpha()
                    ]
                    if len(jieba_parts) > 1:
                        parts = jieba_parts
                except ImportError:
                    # jieba 不可用时，回退到正则拆分
                    mixed_parts = re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z0-9]+', query)
                    if len(mixed_parts) > 1:
                        parts = mixed_parts
            
            # 用 & 连接 (AND 逻辑)
            return ' & '.join(f"'{p}'" for p in parts) if parts else query
        
        processed_query = preprocess_query(request.query)
        
        fts_sql = text(f"""
            SELECT c.id, c.content, c.created_at, 
                   ts_rank(c.tsvector, plainto_tsquery('simple', :query)) as score
            FROM chunks c
            WHERE c.agent_id = :agent_id
              AND c.tsvector @@ plainto_tsquery('simple', :query)
              {time_filter}
            ORDER BY score DESC
            LIMIT :top_k
        """)
        
        result = await session.execute(fts_sql, {
            "query": processed_query,
            "agent_id": request.agent_id,
            "top_k": request.fts_top_k,
        })
        fts_rows = result.fetchall()
        if fts_rows:
            stages_run.append("fts")
        
        # === Stage 2: Pattern (可选) ===
        pattern_rows = []
        if request.pattern_top_k > 0:
            pattern_sql = text(f"""
                SELECT c.id, c.content, c.created_at, 1.0 as score
                FROM chunks c
                WHERE c.agent_id = :agent_id
                  AND c.content ILIKE :pattern
                  {time_filter}
                ORDER BY c.created_at DESC
                LIMIT :top_k
            """)
            result = await session.execute(pattern_sql, {
                "agent_id": request.agent_id,
                "pattern": f"%{request.query}%",
                "top_k": request.pattern_top_k,
            })
            pattern_rows = result.fetchall()
            if pattern_rows:
                stages_run.append("pattern")
        
        # === Stage 3: Time-based ===
        time_sql = text(f"""
            SELECT c.id, c.content, c.created_at, 1.0 as score
            FROM chunks c
            WHERE c.agent_id = :agent_id
              {time_filter}
            ORDER BY c.created_at DESC
            LIMIT :top_k
        """)
        result = await session.execute(time_sql, {
            "agent_id": request.agent_id,
            "top_k": request.time_top_k,
        })
        time_rows = result.fetchall()
        if time_rows:
            stages_run.append("time")
        
        # === Stage 4: RRF 融合 ===
        def rrf_score(rank, k=60, weight=1.0):
            return weight / (k + rank + 1)
        
        chunk_scores = {}
        
        # FTS 权重 3.0
        for rank, row in enumerate(fts_rows):
            chunk_scores[row.id] = chunk_scores.get(row.id, 0) + rrf_score(rank, k=60, weight=3.0) * row.score
        
        # Pattern 权重 1.5
        for rank, row in enumerate(pattern_rows):
            chunk_scores[row.id] = chunk_scores.get(row.id, 0) + rrf_score(rank, k=60, weight=1.5)
        
        # Time 权重 0.5
        for rank, row in enumerate(time_rows):
            chunk_scores[row.id] = chunk_scores.get(row.id, 0) + rrf_score(rank, k=60, weight=0.5)
        
        stages_run.append("rrf")
        
        # 排序并取 Top-K
        sorted_chunks = sorted(chunk_scores.items(), key=lambda x: x[1], reverse=True)
        
        # 构建结果映射
        all_rows = {row.id: row for row in fts_rows + pattern_rows + time_rows}
        results_dict = {}
        
        for chunk_id, score in sorted_chunks[:request.top_k * 3]:  # 先取 3 倍给 MMR
            if chunk_id in all_rows:
                row = all_rows[chunk_id]
                # 应用时间衰减
                time_decay = 1.0
                if request.use_time_decay and row.created_at:
                    time_decay = calculate_time_decay(row.created_at, request.decay_hours)
                
                final_score = score * time_decay
                
                results_dict[chunk_id] = {
                    'id': row.id,
                    'content': row.content,
                    'score': score,
                    'final_score': final_score,
                    'created_at': row.created_at,
                    'stage_source': 'rrf_merged',
                }
        
        # === Stage 5: LLM Cross-Encoder 重排 ===
        if request.use_llm_rerank and len(results_dict) > 1:
            reranker = get_reranker()
            if reranker is not None:
                try:
                    # 准备重排数据
                    rerank_items = list(results_dict.items())
                    contents = [item[1]['content'][:512] for item in rerank_items]  # 每条截取 512 字符
                    
                    # Cross-Encoder 重排
                    reranked_indices = reranker.rerank(request.query, contents, top_k=len(rerank_items))
                    
                    if reranked_indices and len(reranked_indices) == len(rerank_items):
                        # 根据索引重排
                        reranked_dict = {rerank_items[i][0]: rerank_items[i][1] for i in reranked_indices}
                        # 更新分数为排名 (归一化到 0-1)
                        for idx, (cid, item) in enumerate(reranked_dict.items()):
                            item['final_score'] = 1.0 - (idx / len(reranked_dict))
                        results_dict = reranked_dict
                        stages_run.append("llm_rerank")
                except Exception as e:
                    logger = logging.getLogger(__name__)
                    logger.warning(f"LLM rerank error: {e}, falling back to RRF")
        
        # === Stage 6: MMR 多样性重排 ===
        if request.use_mmr and len(results_dict) > 1:
            mmr_selected = mmr_select(
                diverse_hits=[],
                all_hits=results_dict,
                k=request.top_k,
                diversity=request.mmr_diversity
            )
            final_results = [results_dict[cid] for cid in mmr_selected if cid in results_dict]
            stages_run.append("mmr")
        else:
            final_results = list(results_dict.values())[:request.top_k]
        
        if request.use_time_decay:
            stages_run.append("time_decay")
        
        # 构建响应
        results = [
            RetrieveResult(
                id=r['id'],
                content=r['content'][:500],
                score=r['score'],
                final_score=r['final_score'],
                stage_source=r['stage_source'],
                created_at=r['created_at'],
            )
            for r in final_results[:request.top_k]
        ]
        
        elapsed = int((time.time() - start) * 1000)
        
        return RetrieveResponse(
            query=request.query,
            agent_id=request.agent_id,
            total_results=len(results),
            results=results,
            search_time_ms=elapsed,
            stages_run=stages_run,
        )
