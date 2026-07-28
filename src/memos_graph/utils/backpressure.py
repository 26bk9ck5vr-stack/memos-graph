"""背压控制工具"""

import asyncio
import logging
from typing import Optional, Callable, Any
from collections import deque
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    令牌桶限流器
    
    Example:
        limiter = RateLimiter(rate=10, capacity=20)
        
        async def make_request():
            await limiter.acquire()
            # ... 执行请求 ...
    """
    
    def __init__(self, rate: float, capacity: Optional[int] = None):
        self.rate = rate
        self.capacity = capacity or int(rate)
        self.tokens = float(self.capacity)
        self.last_update = datetime.utcnow()
    
    def _refill(self):
        """补充令牌"""
        now = datetime.utcnow()
        elapsed = (now - self.last_update).total_seconds()
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now
    
    async def acquire(self, tokens: int = 1):
        """获取令牌，必要时等待"""
        while True:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return
            
            wait_time = (tokens - self.tokens) / self.rate
            await asyncio.sleep(wait_time)
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """尝试获取令牌，不等待"""
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class ConcurrentLimiter:
    """
    并发数限制器 (信号量包装)
    
    Example:
        limiter = ConcurrentLimiter(max_concurrent=10)
        
        async def process_item(item):
            async with limiter:
                # ... 处理 item，最多 10 个并发 ...
    """
    
    def __init__(self, max_concurrent: int):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        self.current_count = 0
    
    async def __aenter__(self):
        await self.semaphore.acquire()
        self.current_count += 1
        if self.current_count >= self.max_concurrent * 0.8:
            logger.warning(f"并发数达到上限的 80%: {self.current_count}/{self.max_concurrent}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.current_count -= 1
        self.semaphore.release()


class BoundedQueue:
    """
    有界队列，带背压
    
    Example:
        queue = BoundedQueue(maxsize=100)
        
        await queue.put(item)  # 满时等待
        item = await queue.get()
    """
    
    def __init__(self, maxsize: int = 100, name: str = "default"):
        self.queue = asyncio.Queue(maxsize=maxsize)
        self.maxsize = maxsize
        self.name = name
        self.total_put = 0
        self.total_get = 0
    
    async def put(self, item: Any, timeout: Optional[float] = None):
        """放入物品，满时等待"""
        if self.queue.full():
            logger.warning(f"队列 {self.name} 已满 ({self.maxsize})")
        
        await self.queue.put(item)
        self.total_put += 1
    
    async def get(self, timeout: Optional[float] = None) -> Any:
        """获取物品"""
        item = await self.queue.get()
        self.total_get += 1
        return item
    
    def qsize(self) -> int:
        return self.queue.qsize()
    
    def is_full(self) -> bool:
        return self.queue.full()
    
    def stats(self) -> dict:
        return {
            "name": self.name,
            "size": self.qsize(),
            "maxsize": self.maxsize,
            "total_put": self.total_put,
            "total_get": self.total_get,
        }


async def process_with_backpressure(
    items: list,
    processor: Callable,
    max_concurrent: int = 10,
    queue_size: int = 100,
    rate_limit: Optional[float] = None,
) -> list:
    """
    带背压的批量处理
    
    Args:
        items: 待处理项列表
        processor: 处理函数 (async)
        max_concurrent: 最大并发数
        queue_size: 队列大小
        rate_limit: 每秒处理数限制
    
    Returns:
        处理结果列表
    """
    queue = BoundedQueue(maxsize=queue_size)
    concurrent_limiter = ConcurrentLimiter(max_concurrent)
    rate_limiter = RateLimiter(rate_limit) if rate_limit else None
    
    results = []
    errors = []
    processing = True
    
    async def worker():
        while processing or not queue.queue.empty():
            try:
                item = await queue.get(timeout=1.0)
                
                if rate_limiter:
                    await rate_limiter.acquire()
                
                async with concurrent_limiter:
                    try:
                        result = await processor(item)
                        results.append(result)
                    except Exception as e:
                        logger.exception(f"处理项失败：{e}")
                        errors.append((item, e))
                
                queue.queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.exception(f"Worker 错误：{e}")
    
    workers = [asyncio.create_task(worker()) for _ in range(max_concurrent)]
    
    for item in items:
        await queue.put(item)
    
    await queue.queue.join()
    
    processing = False
    await asyncio.gather(*workers, return_exceptions=True)
    
    if errors:
        logger.warning(f"处理完成，{len(errors)} 项失败")
    
    return results


__all__ = [
    "RateLimiter",
    "ConcurrentLimiter",
    "BoundedQueue",
    "process_with_backpressure",
]
