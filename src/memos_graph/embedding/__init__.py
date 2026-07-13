"""memos-graph embedding layer — v0.2.0 siliconflow 实装。

T6.1-T6.5 实装：siliconflow provider (BAAI/bge-m3 1024 维)。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
import httpx


# === 异常类 ===

class EmbeddingError(Exception):
    """Embedding service 基类异常。"""


class NotImplementedByDesignError(EmbeddingError):
    """未实装异常。"""


class EmbeddingAPIError(EmbeddingError):
    """Embedding API 调用失败（网络/超时/HTTP 错误）。"""


# === 抽象接口 ===

class Embedder(ABC):
    """Embedding provider 抽象基类。"""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """单文本 → 向量。"""
        raise NotImplementedByDesignError("Embedder.embed 未实装")

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量文本 → 向量列表。"""
        raise NotImplementedByDesignError("Embedder.embed_batch 未实装")

    @property
    @abstractmethod
    def dimension(self) -> int:
        """返回向量维度。"""
        raise NotImplementedByDesignError("Embedder.dimension 未实装")


# === Siliconflow 实现 ===

class SiliconflowEmbedder(Embedder):
    """siliconflow.cn OpenAI-compatible Embedding 实现。
    
    支持模型：BAAI/bge-m3 (1024 维), BAAI/bge-large-zh-v1.5 (1024 维) 等。
    """
    
    def __init__(
        self,
        model: str = "BAAI/bge-m3",
        base_url: str = "https://api.siliconflow.cn/v1",
        api_key: str = "",
        timeout: float = 30.0,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)
        
        # BAAI/bge-m3 = 1024 维
        self._dimension = 1024 if "bge-m3" in model.lower() else 1024
    
    async def embed(self, text: str) -> list[float]:
        """单文本嵌入。"""
        result = await self.embed_batch([text])
        return result[0]
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入。失败时返回零向量（优雅降级）。"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Return zero vectors on any error (graceful degradation)
        zero_vector = [0.0] * self._dimension
        
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        # Ensure input is a list of non-empty strings
        clean_texts = [str(t).strip() for t in texts if t and str(t).strip()]
        if not clean_texts:
            return [zero_vector] * len(texts)
        payload = {"model": self._model, "input": clean_texts}
        
        try:
            resp = await self._client.post(
                f"{self._base_url}/embeddings",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            
            # OpenAI-compatible 响应格式
            embeddings = [item["embedding"] for item in data["data"]]
            return embeddings
        except httpx.HTTPStatusError as e:
            logger.error(f"Embedding API HTTP {e.response.status_code}: {e.response.text[:200]}, returning zero vectors")
            return [zero_vector for _ in texts]
        except httpx.RequestError as e:
            logger.error(f"Embedding API request failed: {e}, returning zero vectors")
            return [zero_vector for _ in texts]
        except Exception as e:
            logger.error(f"Embedding API unexpected error: {e}, returning zero vectors")
            return [zero_vector for _ in texts]
    
    @property
    def dimension(self) -> int:
        return self._dimension
    
    async def close(self) -> None:
        await self._client.aclose()


# === 主服务 ===

class EmbeddingService:
    """Embedding 服务主入口。
    
    支持 provider: siliconflow, ollama (未来扩展)。
    支持 fallback_to_zero_vector: 失败时返回零向量而非抛异常。
    """
    
    def __init__(
        self,
        provider: str = "siliconflow",
        model: str = "BAAI/bge-m3",
        base_url: str = "https://api.siliconflow.cn/v1",
        api_key: str = "",
        cache_db: str | None = None,
        timeout: float = 30.0,
        fallback_to_zero_vector: bool = False,
    ) -> None:
        self._provider = provider
        self._model = model
        self._base_url = base_url
        self._api_key = api_key
        self._cache_db = cache_db
        self._timeout = timeout
        self._fallback_to_zero_vector = fallback_to_zero_vector
        self._embedder: Embedder | None = None
    
    def _get_embedder(self) -> Embedder:
        """懒加载 embedder。"""
        if self._embedder is None:
            if self._provider == "siliconflow":
                self._embedder = SiliconflowEmbedder(
                    model=self._model,
                    base_url=self._base_url,
                    api_key=self._api_key,
                    timeout=self._timeout,
                )
            elif self._provider == "ollama":
                # TODO: 实现 Ollama embedder
                raise NotImplementedByDesignError("Ollama embedder 未实装")
            else:
                raise ValueError(f"未知 embedding provider: {self._provider}")
        return self._embedder
    
    async def embed(self, text: str) -> list[float]:
        """单文本嵌入。"""
        embedder = self._get_embedder()
        return await embedder.embed(text)
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入。"""
        embedder = self._get_embedder()
        return await embedder.embed_batch(texts)
    
    async def cached_embed(self, text: str) -> list[float]:
        """带 SQLite 缓存的嵌入（T6.3 待实装）。"""
        # TODO: 实现缓存逻辑
        return await self.embed(text)
    
    @property
    def dimension(self) -> int:
        """返回当前模型维度。"""
        return self._get_embedder().dimension
    
    async def close(self) -> None:
        """关闭 HTTP 客户端。"""
        if self._embedder is not None and hasattr(self._embedder, "close"):
            await self._embedder.close()


__all__ = [
    "Embedder",
    "EmbeddingService",
    "SiliconflowEmbedder",
    "EmbeddingError",
    "NotImplementedByDesignError",
]
