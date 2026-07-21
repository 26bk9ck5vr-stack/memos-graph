"""memos-graph recall engine (5-stage: FTS → Vector → RRF → MMR → Graph diffusion).

Implementation: T5.1-T5.5
"""

from __future__ import annotations

import time
import httpx
from memos_graph.llm.client import LLMClient
from memos_graph.embedding import EmbeddingService
from memos_graph.reranker.cross_encoder import CrossEncoderReranker
import json
import re
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select, text, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from memos_graph.db.session import _async_session_factory
from memos_graph.db.models import Chunk, ChunkVector, EntityEdge, Entity

# Session factory for recall engine — uses the same global factory as db.session
def _get_factory():
    from memos_graph.db.session import _async_session_factory
    return _async_session_factory

logger = logging.getLogger(__name__)


# === Exceptions ===

class RecallError(Exception):
    """Recall 引擎任何错误的基类。"""


# === Data Contracts ===

@dataclass
class RecallRequest:
    """5 阶段 recall 的输入。"""
    query: str
    agent_id: str
    scope: str = "all"           # private | shared | global | all
    use_vector: bool = True
    use_llm_expand: bool = False
    use_graph: bool = True
    graph_decay: float = 0.3
    max_results: int = 10
    # 优化召回配置
    fts_top_k: int = 150         # FTS 召回数量
    pattern_top_k: int = 100     # Pattern 召回数量
    time_top_k: int = 80         # 时间召回数量
    rrf_top_k: int = 100         # RRF 融合后取 Top-K 给 LLM
    vector_top_k: int = 0        # 默认禁用向量搜索（可选）
    # 性能模式
    performance_mode: str = "standard"  # fast|standard|full
    time_range_hours: Optional[int] = None  # 时间范围 (小时)


@dataclass
class RecallHit:
    """一条召回结果。"""
    chunk_id: int
    content: str
    score: float
    stage_source: str            # "fts" | "vector" | "graph" | "rrf_merged"
    metadata: dict[str, Any] = field(default_factory=dict)
    time_score: float = 0.0      # 时间衰减分数
    final_score: float = 0.0     # 最终融合分数
    
    def __post_init__(self):
        """Validate chunk_id is not None."""
        if self.chunk_id is None:
            raise ValueError(f"chunk_id cannot be None, stage_source={self.stage_source}")


@dataclass
class RecallResult:
    """5 阶段 recall 的输出。"""
    query: str
    hits: list[RecallHit]
    took_ms: int
    stages_run: list[str]


# === Embedding Service ===
# Import from dedicated embedding module


# === RRF Fusion ===

def rrf_fuse(hits_list: list[list[tuple[int, float]]], k: int = 60, weights: list[float] | None = None) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion 合并多个结果列表。

    Args:
        hits_list: 每个列表是 [(chunk_id, score), ...]
        k: RRF 参数，默认 60
        weights: 每个列表的权重，默认 [1.0, 1.0, 1.0]。P0 优化：FTS 权重提升到 4.0
    """
    scores: dict[int, float] = {}
    
    # P0 优化：支持自定义权重 (默认 FTS:4.0, Pattern:1.5, Time:0.5)
    if weights is None:
        weights = [4.0, 1.5, 0.5]  # 提升 FTS 权重，增强关键词匹配
    
    for idx, hits in enumerate(hits_list):
        weight = weights[idx] if idx < len(weights) else 1.0
        for rank, (chunk_id, score) in enumerate(hits):
            rrf = 1.0 / (k + rank + 1)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + rrf * score * weight

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# === Recall Engine ===

class RecallEngine:
    """优化 recall 引擎。

    Stage 1: FTS(150) — PostgreSQL tsvector GIN 全文搜索
    Stage 2: Pattern(100) — ILIKE pattern 模糊匹配
    Stage 3: Time(80) — 时间最近优先召回
    Stage 4: RRF — 融合三路召回 → Top 330
    Stage 5: LLM — LLM 重排 330 条
    Stage 6: MMR — 多样性重排
    Stage 7: Time Decay — 时间衰减最终分数
    """

    def __init__(
        self,
        db_url: str | None = None,
        embedding_provider: str = "siliconflow",
        embedding_model: str = "BAAI/bge-m3",
        embedding_base_url: str = "https://api.siliconflow.cn/v1",
        embedding_api_key: str = "",
        embedding_timeout: float = 30.0,
        llm_base_url: str = "",
        llm_api_key: str = "",
        llm_model: str = "",
        llm_timeout: int = 60,
    ) -> None:
        from memos_graph.config import load_config
        from memos_graph.llm.client import LLMClient
        cfg = load_config()
        self._db_url = db_url
        # Store embedding config for lazy init
        self._embedding_provider = embedding_provider or cfg.embedding.provider
        self._embedding_model = embedding_model or cfg.embedding.model
        self._embedding_base_url = embedding_base_url or cfg.embedding.base_url
        self._embedding_api_key = embedding_api_key or cfg.embedding.api_key
        self._embedding_timeout = embedding_timeout or float(cfg.embedding.timeout_seconds)
        # Store LLM config for lazy init
        self._llm_base_url = llm_base_url or cfg.llm.base_url
        self._llm_api_key = llm_api_key or cfg.llm.api_key
        self._llm_model = llm_model or cfg.llm.model
        self._llm_timeout = llm_timeout or cfg.llm.timeout_seconds
        # Lazy-initialized services
        self._embedding: Any | None = None
        self._llm: LLMClient | None = None
        # Cross-Encoder reranker (lazy init)
        self._reranker: CrossEncoderReranker | None = None

    def _get_embedding(self):
        """Lazy init embedding service."""
        if self._embedding is None:
            from memos_graph.embedding import EmbeddingService
            self._embedding = EmbeddingService(
                provider=self._embedding_provider,
                model=self._embedding_model,
                base_url=self._embedding_base_url,
                api_key=self._embedding_api_key,
                timeout=self._embedding_timeout,
            )
        return self._embedding

    def _get_llm(self):
        """Lazy init LLM client."""
        if self._llm is None:
            from memos_graph.llm.client import LLMClient
            self._llm = LLMClient(
                base_url=self._llm_base_url,
                api_key=self._llm_api_key,
                model=self._llm_model,
                timeout=self._llm_timeout,
            )
        return self._llm
    
    def _get_reranker(self):
        """Lazy init Cross-Encoder reranker."""
        if self._reranker is None:
            self._reranker = CrossEncoderReranker('BAAI/bge-reranker-base')  # base 模型更快
        return self._reranker

    async def close(self):
        """Close lazy-initialized services."""
        if self._embedding is not None and hasattr(self._embedding, "close"):
            await self._embedding.close()
        if self._llm is not None and hasattr(self._llm, "close"):
            await self._llm.close()

    async def search(
        self,
        req: RecallRequest,
        session: AsyncSession | None = None,
    ) -> RecallResult:
        """优化检索入口。"""
        start = time.time()
        stages_run = []

        own_session = False
        if session is None:
            session = _get_factory()()
            own_session = True

        try:
            # Stage 1: FTS (150 条)
            fts_hits = await self._fts_search(session, req)
            stages_run.append("fts")

            # Stage 2: Pattern (100 条)
            pattern_hits = await self._pattern_search(session, req)
            stages_run.append("pattern")

            # Stage 3: Time-based (80 条)
            time_hits = await self._time_search(session, req)
            stages_run.append("time")

            # Stage 4: RRF 融合三路召回
            fts_ranked = [(h.chunk_id, h.score) for h in fts_hits]
            pattern_ranked = [(h.chunk_id, h.score) for h in pattern_hits]
            time_ranked = [(h.chunk_id, h.score) for h in time_hits]
            rrf_ranked = rrf_fuse([fts_ranked, pattern_ranked, time_ranked])
            stages_run.append("rrf")

            # 取 Top 330 给 LLM 重排
            top_k_for_llm = min(req.rrf_top_k, len(rrf_ranked))
            chunk_ids = [cid for cid, _ in rrf_ranked[:top_k_for_llm]]
            chunks = await self._load_chunks(session, chunk_ids)
            chunk_map = {c.id: c for c in chunks}

            rrf_hits = [
                RecallHit(
                    chunk_id=cid,
                    content=chunk_map[cid].content,
                    score=score,
                    stage_source="rrf_merged",
                    metadata={"agent_id": chunk_map[cid].agent_id, "scope": chunk_map[cid].scope},
                )
                for cid, score in rrf_ranked
                if cid is not None and cid in chunk_map
            ]

            # Stage 5: LLM 重排 (330 条)
            if req.use_llm_expand and rrf_hits:
                try:
                    rrf_hits = await self._rerank(rrf_hits, req.query)
                    stages_run.append("llm_rerank")
                except Exception as ex:
                    logger.warning(f"LLM rerank failed: {ex}")

            # Stage 6: MMR 多样性重排
            mmr_hits = self._mmr_diversify(rrf_hits, req.max_results * 2, lambda h: h.content)
            stages_run.append("mmr")

            # Stage 7: 时间衰减
            final_hits = self._apply_time_decay(mmr_hits)

            took_ms = int((time.time() - start) * 1000)
            return RecallResult(
                query=req.query,
                hits=final_hits[:req.max_results],
                took_ms=took_ms,
                stages_run=stages_run,
            )
        finally:
            if own_session:
                await session.close()

    async def _rerank(self, hits: list[RecallHit], query: str) -> list[RecallHit]:
        """Cross-Encoder 重排 (替代 LLM)。"""
        if not hits:
            return hits
        
        try:
            reranker = self._get_reranker()
            # 提取内容 (每条截取前 512 字符)
            contents = [h.content[:512] for h in hits]
            
            # Cross-Encoder 重排
            reranked_indices = reranker.rerank(query, contents, top_k=len(hits))
            
            # 根据索引重排
            if reranked_indices and len(reranked_indices) == len(hits):
                reranked_hits = [hits[i] for i in reranked_indices]
                # 更新分数为排名 (归一化到 0-1)
                for idx, hit in enumerate(reranked_hits):
                    hit.final_score = 1.0 - (idx / len(reranked_hits))
                return reranked_hits
        except Exception as e:
            logger.warning(f"Cross-Encoder rerank error: {e}")
        
        # Fallback: 保持原顺序
        return hits

    async def _pattern_search(self, session: AsyncSession, req: RecallRequest) -> list[RecallHit]:
        """Stage 2: Pattern 模糊匹配 (ILIKE)。"""
        if req.scope == "all":
            scope_filter = ""
        else:
            scope_filter = "AND c.scope = :scope"
        
        sql = text(f"""
            SELECT c.id, c.content, c.agent_id, c.scope, c.created_at,
                   1.0 as pattern_score
            FROM chunks c
            WHERE c.agent_id = :agent_id
              AND c.content ILIKE :pattern
              {scope_filter}
            ORDER BY c.created_at DESC
            LIMIT :top_k
        """)
        
        pattern = f"%{req.query}%"
        params = {
            "agent_id": req.agent_id,
            "pattern": pattern,
            "top_k": req.pattern_top_k,
        }
        if req.scope != "all":
            params["scope"] = req.scope
        
        try:
            result = await session.execute(sql, params)
            rows = result.fetchall()
            return [
                RecallHit(
                    chunk_id=row.id,
                    content=row.content,
                    score=float(row.pattern_score),
                    stage_source="pattern",
                    metadata={"agent_id": row.agent_id, "scope": row.scope},
                    time_score=0.0,
                )
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"Pattern search failed: {e}")
            return []

    async def _time_search(self, session: AsyncSession, req: RecallRequest) -> list[RecallHit]:
        """Stage 3: 时间最近优先召回 (80 条)。"""
        if req.scope == "all":
            scope_filter = ""
        else:
            scope_filter = "AND c.scope = :scope"
        
        sql = text(f"""
            SELECT c.id, c.content, c.agent_id, c.scope, c.created_at,
                   1.0 as time_score
            FROM chunks c
            WHERE c.agent_id = :agent_id
              {scope_filter}
            ORDER BY c.created_at DESC
            LIMIT :top_k
        """)
        
        params = {
            "agent_id": req.agent_id,
            "top_k": req.time_top_k,
        }
        if req.scope != "all":
            params["scope"] = req.scope
        
        try:
            result = await session.execute(sql, params)
            rows = result.fetchall()
            return [
                RecallHit(
                    chunk_id=row.id,
                    content=row.content,
                    score=float(row.time_score),
                    stage_source="time",
                    metadata={"agent_id": row.agent_id, "scope": row.scope, "created_at": row.created_at},
                    time_score=1.0,
                )
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"Time search failed: {e}")
            return []

    def _apply_time_decay(self, hits: list[RecallHit]) -> list[RecallHit]:
        """Stage 7: 应用时间衰减到最终分数。"""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        for hit in hits:
            # 从 metadata 中获取 created_at
            created_at = hit.metadata.get("created_at")
            if created_at:
                if isinstance(created_at, datetime):
                    created_time = created_at
                else:
                    try:
                        created_time = datetime.fromisoformat(str(created_at))
                        if created_time.tzinfo is None:
                            created_time = created_time.replace(tzinfo=timezone.utc)
                    except Exception:
                        created_time = now
            else:
                created_time = now
            
            # 计算时间差（小时）
            hours_diff = (now - created_time).total_seconds() / 3600
            
            # 时间衰减：exp(-0.01 * hours) ≈ 每 70 小时衰减一半
            decay_factor = 2.718281828 ** (-0.01 * min(hours_diff, 720))  # 最多衰减 30 天
            
            # 最终分数 = RRF 分数 * 时间衰减
            hit.final_score = hit.score * decay_factor
            hit.time_score = decay_factor
        
        # 按最终分数重排
        hits.sort(key=lambda h: h.final_score, reverse=True)
        return hits

    async def fts_search(self, query: str, agent_id: str, top_k: int = 50) -> list[RecallHit]:
        """FTS 阶段入口（独立调用）。"""
        async with _get_factory()() as session:
            req = RecallRequest(query=query, agent_id=agent_id, fts_top_k=top_k)
            return await self._fts_search(session, req)

    async def vector_search(self, query: str, agent_id: str, top_k: int = 50) -> list[RecallHit]:
        """向量阶段入口（独立调用）。"""
        async with _get_factory()() as session:
            req = RecallRequest(query=query, agent_id=agent_id, vector_top_k=top_k)
            return await self._vector_search(session, req)

    async def expand_graph(self, chunk_id: int, decay: float = 0.3) -> list[RecallHit]:
        """图谱扩散入口（独立调用）。"""
        async with _get_factory()() as session:
            fake_hit = RecallHit(chunk_id=chunk_id, content="", score=1.0, stage_source="graph")
            return await self._graph_diffusion(session, [fake_hit], decay)

    # === Private Methods ===

    async def _fts_search(self, session: AsyncSession, req: RecallRequest) -> list[RecallHit]:
        """Stage 1: Full-Text Search using PostgreSQL tsvector."""
        # Build search query
        search_query = req.query.replace("'", "''")
        
        if req.scope == "all":
            scope_filter = ""
        else:
            scope_filter = f"AND c.scope = :scope"

        sql = text(f"""
            SELECT c.id, c.content, c.agent_id, c.scope,
                   ts_rank(c.tsvector, plainto_tsquery('english', :query)) as rank
            FROM chunks c
            WHERE c.agent_id = :agent_id
              AND c.tsvector @@ plainto_tsquery('english', :query)
              {scope_filter}
            ORDER BY rank DESC
            LIMIT :top_k
        """)
        
        params: dict[str, Any] = {
            "query": search_query,
            "agent_id": req.agent_id,
            "top_k": req.fts_top_k,
        }
        if req.scope != "all":
            params["scope"] = req.scope

        try:
            result = await session.execute(sql, params)
            rows = result.fetchall()
        except Exception as e:
            logger.warning(f"FTS search failed: {e}, falling back to ILIKE")
            # ILIKE fallback with proper parameterization
            from sqlalchemy import bindparam
            like_pattern = bindparam("pattern", value=f"%{req.query}%")
            q = select(Chunk).where(
                Chunk.agent_id == req.agent_id,
                Chunk.content.ilike(like_pattern),
            )
            if req.scope != "all":
                q = q.where(Chunk.scope == req.scope)
            q = q.limit(req.fts_top_k)
            result = await session.execute(q)
            chunks = result.scalars().all()
            return [
                RecallHit(
                    chunk_id=c.id,
                    content=c.content,
                    score=1.0,
                    stage_source="fts",
                    metadata={"agent_id": c.agent_id, "scope": c.scope},
                )
                for c in chunks
            ]

        return [
            RecallHit(
                chunk_id=row.id,
                content=row.content,
                score=float(row.rank) if row.rank else 0.0,
                stage_source="fts",
                metadata={"agent_id": row.agent_id, "scope": row.scope},
            )
            for row in rows
        ]

    async def _vector_search(self, session: AsyncSession, req: RecallRequest) -> list[RecallHit]:
        """Stage 2: Vector similarity search using pgvector."""
        # Get query embedding
        embedding = self._get_embedding()
        try:
            # embed() accepts a single string and returns list[float]
            query_vec = await embedding.embed(req.query)
        except Exception as e:
            logger.warning(f"Embedding failed: {e}, skipping vector search")
            return []
        if not query_vec or not isinstance(query_vec, list):
            logger.warning("Embedding returned invalid result, skipping vector search")
            return []

        # Build vector query
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"

        if req.scope == "all":
            scope_filter = ""
        else:
            scope_filter = "AND c.scope = :scope"

        sql = text(f"""
            SELECT c.id, c.content, c.agent_id, c.scope,
                   1 - (cv.embedding <=> '{vec_str}'::vector) as similarity
            FROM chunks c
            JOIN chunk_vectors cv ON cv.chunk_id = c.id
            WHERE c.agent_id = :agent_id
              {scope_filter}
            ORDER BY cv.embedding <=> '{vec_str}'::vector
            LIMIT :top_k
        """)

        params: dict[str, Any] = {
            "vec": vec_str,
            "agent_id": req.agent_id,
            "top_k": req.vector_top_k,
        }
        if req.scope != "all":
            params["scope"] = req.scope

        try:
            result = await session.execute(sql, params)
            rows = result.fetchall()
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

        return [
            RecallHit(
                chunk_id=row.id,
                content=row.content,
                score=float(row.similarity) if row.similarity else 0.0,
                stage_source="vector",
                metadata={"agent_id": row.agent_id, "scope": row.scope},
            )
            for row in rows
        ]

    async def _graph_diffusion(
        self,
        session: AsyncSession,
        seed_hits: list[RecallHit],
        decay: float = 0.3,
    ) -> list[RecallHit]:
        """Stage 5: Graph diffusion via entity edges."""
        if not seed_hits:
            return []

        seed_chunk_ids = [h.chunk_id for h in seed_hits if h.chunk_id is not None]

        # Find entities connected to seed chunks
        entity_sql = text("""
            SELECT DISTINCT e.id, e.name, e.type
            FROM entities e
            JOIN chunk_entities ce ON ce.entity_id = e.id
            WHERE ce.chunk_id = ANY(:chunk_ids)
        """)

        try:
            result = await session.execute(entity_sql, {"chunk_ids": seed_chunk_ids})
            entity_rows = result.fetchall()
        except Exception as e:
            logger.warning(f"Graph diffusion failed: {e}")
            return []

        if not entity_rows:
            return []

        entity_ids = [row.id for row in entity_rows]

        # Find other chunks connected to these entities
        related_sql = text("""
            SELECT DISTINCT c.id, c.content, c.agent_id, c.scope,
                   COUNT(DISTINCT ce.entity_id) as entity_overlap
            FROM chunks c
            JOIN chunk_entities ce ON ce.chunk_id = c.id
            WHERE ce.entity_id = ANY(:entity_ids)
              AND c.id != ALL(:exclude_ids)
            GROUP BY c.id, c.content, c.agent_id, c.scope
            ORDER BY entity_overlap DESC
            LIMIT 10
        """)

        try:
            result = await session.execute(related_sql, {
                "entity_ids": entity_ids,
                "exclude_ids": seed_chunk_ids,
            })
            rows = result.fetchall()
        except Exception:
            return []

        return [
            RecallHit(
                chunk_id=row.id,
                content=row.content,
                score=float(row.entity_overlap) * decay,
                stage_source="graph",
                metadata={"agent_id": row.agent_id, "scope": row.scope},
            )
            for row in rows
        ]

    async def _load_chunks(self, session: AsyncSession, chunk_ids: list[int]) -> list[Chunk]:
        """Load chunks by IDs, preserving order."""
        if not chunk_ids:
            return []
        q = select(Chunk).where(Chunk.id.in_(chunk_ids))
        result = await session.execute(q)
        return list(result.scalars().all())

    @staticmethod
    def _mmr_diversify(
        hits: list[RecallHit],
        max_results: int,
        get_text,
        lambda_val: float = 0.5,
    ) -> list[RecallHit]:
        """Stage 4: Maximal Marginal Relevance — diversify results."""
        if len(hits) <= max_results:
            return hits

        selected = []
        remaining = list(hits)

        while len(selected) < max_results and remaining:
            if not selected:
                # Pick highest score — use best_item for consistency
                best_item = remaining.pop(0)
                selected.append(best_item)
            else:
                # Score = lambda * relevance - (1-lambda) * max_similarity_to_selected
                best_score = -float("inf")
                best_item = None
                
                for item in remaining:
                    relevance = item.score
                    # Simple text similarity (word overlap)
                    selected_texts = " ".join(get_text(s) for s in selected)
                    item_text = get_text(item)
                    
                    overlap = len(set(item_text.lower().split()) & set(selected_texts.lower().split()))
                    max_sim = overlap / max(len(set(item_text.lower().split()) | set(selected_texts.lower().split())), 1)
                    
                    mmr_score = lambda_val * relevance - (1 - lambda_val) * max_sim
                    if mmr_score > best_score:
                        best_score = mmr_score
                        best_item = item
                
                if best_item is None:
                    break  # No more items to select
                
                remaining.remove(best_item)
                selected.append(best_item)

        return selected


__all__ = [
    "RecallEngine",
    "RecallRequest",
    "RecallHit",
    "RecallResult",
    "RecallError",
    "EmbeddingService",
]
