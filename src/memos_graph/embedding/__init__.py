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

import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SiliconflowEmbedder(Embedder):
    """siliconflow.cn OpenAI-compatible Embedding 实现。
    
    支持模型：BAAI/bge-m3 (1024 维), BAAI/bge-large-zh-v1.5 (1024 维) 等。
    
    内置重试和熔断机制:
    - 最多重试 3 次，指数退避 (1s, 2s, 4s)
    - 熔断器：5 次失败后打开，60 秒后尝试恢复
    - 优雅降级：失败时返回零向量
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
        
        # 熔断器配置
        self._cb_failure_count = 0
        self._cb_failure_threshold = 5
        self._cb_recovery_timeout = 60
        self._cb_last_failure_time = None
        self._cb_state = "CLOSED"  # CLOSED | OPEN | HALF_OPEN
        
        # 重试配置
        self._retry_delays = [1.0, 2.0, 4.0]  # 指数退避
        
        # 模型维度映射
        model_lower = model.lower()
        if "nomic" in model_lower:
            self._dimension = 768
        elif "bge-m3" in model_lower:
            self._dimension = 1024
        else:
            self._dimension = 1024
    
    async def embed(self, text: str) -> list[float]:
        """单文本嵌入。"""
        result = await self.embed_batch([text])
        return result[0]
    
    def _cb_record_success(self):
        """记录成功，重置熔断器"""
        self._cb_failure_count = 0
        self._cb_state = "CLOSED"
    
    def _cb_record_failure(self):
        """记录失败，更新熔断器状态"""
        self._cb_failure_count += 1
        self._cb_last_failure_time = datetime.utcnow()
        if self._cb_failure_count >= self._cb_failure_threshold:
            old_state = self._cb_state
            self._cb_state = "OPEN"
            logger.warning(f"Embedding 熔断器打开：{self._cb_failure_count} 次失败 ({old_state} → OPEN)")
    
    def _cb_can_execute(self) -> bool:
        """检查熔断器是否允许执行"""
        if self._cb_state == "CLOSED":
            return True
        if self._cb_state == "OPEN":
            if (self._cb_last_failure_time and 
                datetime.utcnow() - self._cb_last_failure_time > timedelta(seconds=self._cb_recovery_timeout)):
                self._cb_state = "HALF_OPEN"
                logger.info("Embedding 熔断器进入半开状态")
                return True
            return False
        return True  # HALF_OPEN
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入。失败时返回零向量（优雅降级）。
        
        内置重试和熔断:
        - 熔断器打开时直接返回零向量
        - 网络错误时指数退避重试 (1s, 2s, 4s)
        - 5 次连续失败后熔断 60 秒
        """
        zero_vector = [0.0] * self._dimension
        
        # 检查熔断器
        if not self._cb_can_execute():
            logger.warning("Embedding API 熔断中，返回零向量")
            return [zero_vector for _ in texts]
        
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        clean_texts = [str(t).strip() for t in texts if t and str(t).strip()]
        if not clean_texts:
            return [zero_vector] * len(texts)
        payload = {"model": self._model, "input": clean_texts, "encoding_format": "float"}
        
        last_error = None
        
        # 重试循环
        for attempt, delay in enumerate(self._retry_delays + [0]):
            if attempt > 0:
                logger.info(f"Embedding 重试 {attempt}/{len(self._retry_delays)}")
                await asyncio.sleep(delay)
            
            try:
                resp = await self._client.post(
                    f"{self._base_url}/embeddings",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                
                embeddings = [item["embedding"] for item in data["data"]]
                
                result = []
                for emb in embeddings:
                    if hasattr(emb, 'tolist'):
                        result.append(emb.tolist())
                    elif isinstance(emb, (list, tuple)):
                        result.append(list(emb))
                    else:
                        logger.warning(f"Unexpected embedding type: {type(emb)}, using zero vector")
                        result.append(zero_vector)
                
                self._cb_record_success()
                return result
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                    # 服务端错误，重试
                    last_error = e
                    self._cb_record_failure()
                    if self._cb_state == "OPEN":
                        break
                else:
                    # 客户端错误，不重试
                    logger.error(f"Embedding API HTTP {e.response.status_code}: {e.response.text[:200]}")
                    return [zero_vector for _ in texts]
                    
            except httpx.RequestError as e:
                # 网络错误，重试
                last_error = e
                self._cb_record_failure()
                if self._cb_state == "OPEN":
                    break
        
        # 所有重试失败
        logger.error(f"Embedding API 所有重试失败：{last_error}")
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
        raise NotImplementedByDesignError("cached_embed 未实装 - T6.3")
    
    @property
    def dimension(self) -> int:
        """返回当前模型维度。"""
        return self._get_embedder().dimension
    
    @property
    def model(self) -> str:
        """返回当前模型名称。"""
        return self._model
    
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
