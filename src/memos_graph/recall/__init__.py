"""memos-graph recall engine (5-stage: FTS → Vector → RRF → MMR → Graph diffusion).

v0.1.0-docs 占位实现 — 真实 5 阶段逻辑见 TASK_BREAKDOWN T5.1-T5.5
实装前所有方法抛 NotImplementedError。Contract tests 验证签名 + 异常类型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# === 占位异常类（v0.1 公开 API 的一部分）===

class RecallError(Exception):
    """Recall 引擎任何错误的基类。"""


class NotImplementedByDesignError(RecallError):
    """v0.1.0-docs 阶段未实装的方法。

    实装后（TASK_BREAKDOWN T5.x）应删除此异常，方法真实工作。
    """


# === 数据契约（来自 SPEC §2.1 + TEST_SPEC §2.4）===

@dataclass
class RecallRequest:
    """5 阶段 recall 的输入。"""
    query: str
    agent_id: str
    scope: str = "all"           # private | shared | global | all
    use_graph: bool = True
    graph_decay: float = 0.3
    max_results: int = 10


@dataclass
class RecallHit:
    """一条召回结果。"""
    chunk_id: int
    content: str
    score: float
    stage_source: str            # "fts" | "vector" | "graph" | "rrf_merged"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RecallResult:
    """5 阶段 recall 的输出。"""
    query: str
    hits: list[RecallHit]
    took_ms: int
    stages_run: list[str]        # 实际跑过的阶段


# === 占位主类（v0.1 不实装，v0.2 实装 T5.x）===

class RecallEngine:
    """5 阶段 recall 引擎 — v0.1 占位。

    公开方法（**契约** — v0.2 真实实装后这些方法签名不变）：

    - `search(req: RecallRequest) -> RecallResult`
    - `expand_graph(chunk_id: int, decay: float = 0.3) -> list[RecallHit]`

    v0.1 阶段：所有方法 raise NotImplementedByDesignError。
    """

    def __init__(self, db_url: str | None = None, embedding_service: Any = None) -> None:
        self._db_url = db_url
        self._embedding_service = embedding_service

    async def search(self, req: RecallRequest) -> RecallResult:
        """5 阶段检索入口。v0.1 占位，v0.2 实装。

        见 TEST_SPEC §2.4 REC-PIP-01..10。
        """
        raise NotImplementedByDesignError(
            "RecallEngine.search 待 T5.4a + T5.4b 实装"
        )

    async def expand_graph(self, chunk_id: int, decay: float = 0.3) -> list[RecallHit]:
        """图谱扩散。v0.1 占位，v0.2 实装。

        见 TEST_SPEC §2.3 REC-GRAPH-01..05。
        """
        raise NotImplementedByDesignError(
            "RecallEngine.expand_graph 待 T5.3 实装"
        )

    async def fts_search(self, query: str, top_k: int = 50) -> list[RecallHit]:
        """FTS 阶段。v0.1 占位。

        见 TEST_SPEC §2.1 REC-FTS-01..05。
        """
        raise NotImplementedByDesignError(
            "RecallEngine.fts_search 待 T5.1 实装"
        )

    async def vector_search(self, query: str, top_k: int = 50) -> list[RecallHit]:
        """向量阶段。v0.1 占位。

        见 TEST_SPEC §2.2 REC-VEC-01..05。
        """
        raise NotImplementedByDesignError(
            "RecallEngine.vector_search 待 T5.2 实装"
        )


# === 公开 API 列表（contract tests 用）===

__all__ = [
    "RecallEngine",
    "RecallRequest",
    "RecallHit",
    "RecallResult",
    "RecallError",
    "NotImplementedByDesignError",
]
