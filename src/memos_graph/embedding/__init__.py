"""memos-graph embedding layer — v0.1.0-docs 占位。

TASK_BREAKDOWN T6.1-T6.5 实装。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


# === 占位异常 ===

class EmbeddingError(Exception):
    """Embedding service 基类异常。"""


class NotImplementedByDesignError(EmbeddingError):
    """v0.1.0-docs 阶段未实装。T6.x 实装后删除。"""


# === 抽象接口（契约 — v0.1 占位 + 签名）===

class Embedder(ABC):
    """Embedding provider 抽象基类。"""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """单文本 → 向量。v0.1 占位。"""
        raise NotImplementedByDesignError("Embedder.embed 待 T6.2 实装")

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量文本 → 向量列表。v0.1 占位。"""
        raise NotImplementedByDesignError("Embedder.embed_batch 待 T6.2 实装")

    @property
    @abstractmethod
    def dimension(self) -> int:
        """返回向量维度（768 / 1024 / 1536）。"""
        raise NotImplementedByDesignError("Embedder.dimension 待 T6.2 实装")


class EmbeddingService:
    """Embedding 服务主入口（v0.1 占位）。

    公开方法：
    - `embed(text) -> list[float]`
    - `embed_batch(texts) -> list[list[float]]`
    - `cached_embed(text) -> list[float]`（带 SQLite 缓存）
    - `dimension -> int`
    """

    def __init__(
        self,
        provider: str = "ollama",
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
        cache_db: str | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._base_url = base_url
        self._cache_db = cache_db
        self._embedder: Embedder | None = None  # 延迟实例化

    async def embed(self, text: str) -> list[float]:
        raise NotImplementedByDesignError(
            "EmbeddingService.embed 待 T6.2 (Ollama) 实装"
        )

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedByDesignError(
            "EmbeddingService.embed_batch 待 T6.2 实装"
        )

    async def cached_embed(self, text: str) -> list[float]:
        """带 SQLite 缓存（T6.3）。"""
        raise NotImplementedByDesignError(
            "EmbeddingService.cached_embed 待 T6.3 (cache) 实装"
        )

    @property
    def dimension(self) -> int:
        """返回当前模型维度。"""
        if self._model == "nomic-embed-text":
            return 768
        if self._model == "mxbai-embed-large":
            return 1024
        raise NotImplementedByDesignError(
            f"EmbeddingService.dimension 未知 model: {self._model}"
        )


__all__ = [
    "Embedder",
    "EmbeddingService",
    "EmbeddingError",
    "NotImplementedByDesignError",
]
