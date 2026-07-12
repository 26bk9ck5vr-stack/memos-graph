"""memos-graph recall engine (5-stage: FTS → Vector → RRF → MMR → Graph diffusion).

Implementation: T5.1-T5.5
"""

from __future__ import annotations

import time
import httpx
from memos_graph.llm.client import LLMClient
from memos_graph.embedding import EmbeddingService
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
    fts_top_k: int = 50
    vector_top_k: int = 50


@dataclass
class RecallHit:
    """一条召回结果。"""
    chunk_id: int
    content: str
    score: float
    stage_source: str            # "fts" | "vector" | "graph" | "rrf_merged"
    metadata: dict[str, Any] = field(default_factory=dict)
    
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

def rrf_fuse(hits_list: list[list[tuple[int, float]]], k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion 合并多个结果列表。

    Args:
        hits_list: 每个列表是 [(chunk_id, score), ...]
        k: RRF 参数，默认 60
    """
    scores: dict[int, float] = {}

    for hits in hits_list:
        for rank, (chunk_id, score) in enumerate(hits):
            rrf = 1.0 / (k + rank + 1)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + rrf * score

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# === Recall Engine ===

class RecallEngine:
    """5 阶段 recall 引擎。

    Stage 1: FTS — PostgreSQL tsvector GIN 全文搜索
    Stage 2: Vector — pgvector 语义相似度搜索
    Stage 3: RRF — Reciprocal Rank Fusion 合并 FTS + Vector
    Stage 4: MMR — Maximal Marginal Relevance 多样性重排
    Stage 5: Graph — 图谱扩散，扩展相关实体
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
        """5 阶段检索入口。"""
        start = time.time()
        stages_run = []

        own_session = False
        if session is None:
            session = _get_factory()()
            own_session = True

        try:
            # Stage 0: Query expansion (LLM)
            expanded_queries = [req.query]
            if req.use_llm_expand and req.query.strip():
                try:
                    llm = self._get_llm()
                    expanded = await llm.expand_query(req.query)
                    if expanded:
                        expanded_queries = expanded
                        stages_run.append("expand")
                except Exception as ex:
                    logger.warning(f"Query expand failed: {ex}")

            # Best-effort FTS across expanded queries, union results
            all_fts_hits: dict[int, RecallHit] = {}
            for eq in expanded_queries:
                req_expanded = RecallRequest(
                    query=eq,
                    agent_id=req.agent_id,
                    scope=req.scope,
                    fts_top_k=req.fts_top_k,
                    vector_top_k=0,
                    max_results=req.max_results,
                    use_graph=False,
                    use_llm_expand=False,
                )
                fts_hits = await self._fts_search(session, req_expanded)
                for h in fts_hits:
                    if h.chunk_id not in all_fts_hits or h.score > all_fts_hits[h.chunk_id].score:
                        all_fts_hits[h.chunk_id] = h
            fts_hits = list(all_fts_hits.values())
            stages_run.append("fts")

            # Stage 2: Vector (only if enabled)
            vec_hits: list[RecallHit] = []
            if req.use_vector:
                try:
                    vec_hits = await self._vector_search(session, req)
                    stages_run.append("vector")
                except Exception as ex:
                    logger.warning(f"Vector search failed: {ex}")

            # Stage 3: RRF
            fts_ranked = [(h.chunk_id, h.score) for h in fts_hits]
            vec_ranked = [(h.chunk_id, h.score) for h in vec_hits]
            rrf_ranked = rrf_fuse([fts_ranked, vec_ranked])
            stages_run.append("rrf")

            # Load full chunks for RRF results
            chunk_ids = [cid for cid, _ in rrf_ranked[:req.max_results * 2]]
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

            # Stage 4: MMR
            mmr_hits = self._mmr_diversify(rrf_hits, req.max_results, lambda h: h.content)
            stages_run.append("mmr")

            # Stage 5: Graph diffusion (optional)
            if req.use_graph and mmr_hits:
                graph_hits = await self._graph_diffusion(session, mmr_hits[:3], req.graph_decay)
                if graph_hits:
                    # Merge graph hits
                    existing_ids = {h.chunk_id for h in mmr_hits}
                    for gh in graph_hits:
                        if gh.chunk_id not in existing_ids:
                            mmr_hits.append(gh)
                            existing_ids.add(gh.chunk_id)
                    stages_run.append("graph")

            took_ms = int((time.time() - start) * 1000)
            return RecallResult(
                query=req.query,
                hits=mmr_hits[:req.max_results],
                took_ms=took_ms,
                stages_run=stages_run,
            )
        finally:
            if own_session:
                await session.close()

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
