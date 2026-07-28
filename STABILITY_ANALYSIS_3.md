## 3. 代码层防御措施 (Defensive Measures)

### 3.1 重试装饰器

创建通用重试装饰器工具模块：

**文件**: `src/memos_graph/utils/retry.py`

```python
"""通用重试和熔断工具"""

import asyncio
import logging
from functools import wraps
from typing import Callable, Any, Optional, List, Type
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CircuitBreakerError(Exception):
    """熔断器打开时的异常"""
    pass


class CircuitBreaker:
    """
    简单熔断器实现
    
    状态机:
    - CLOSED: 正常执行，失败计数
    - OPEN: 拒绝执行，等待恢复超时
    - HALF_OPEN: 允许一次尝试，成功则关闭，失败则打开
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 1,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"
        self._half_open_calls = 0
    
    def record_success(self):
        """记录成功"""
        self.failure_count = 0
        self.success_count += 1
        self.state = "CLOSED"
        self._half_open_calls = 0
    
    def record_failure(self):
        """记录失败"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            old_state = self.state
            self.state = "OPEN"
            logger.warning(f"熔断器打开：{self.failure_count} 次失败 (状态：{old_state} → OPEN)")
        
        self._half_open_calls = 0
    
    def can_execute(self) -> bool:
        """检查是否可以执行"""
        if self.state == "CLOSED":
            return True
        
        if self.state == "OPEN":
            if (self.last_failure_time and 
                datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.recovery_timeout)):
                self.state = "HALF_OPEN"
                self._half_open_calls = 0
                logger.info("熔断器进入半开状态")
                return True
            return False
        
        # HALF_OPEN 状态
        if self._half_open_calls < self.half_open_max_calls:
            self._half_open_calls += 1
            return True
        return False
    
    def reset(self):
        """重置熔断器"""
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"
        self._half_open_calls = 0


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential: bool = True,
    exceptions: tuple = (Exception,),
    logger_func: Optional[Callable] = None,
):
    """
    带指数退避的重试装饰器
    
    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟 (秒)
        max_delay: 最大延迟 (秒)
        exponential: 是否指数退避
        exceptions: 需要重试的异常类型
        logger_func: 日志函数，默认 logger.warning
    
    Example:
        @retry_with_backoff(max_retries=3, exceptions=(httpx.RequestError,))
        async def fetch_data():
            ...
    """
    if logger_func is None:
        logger_func = logger.warning
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt >= max_retries:
                        break
                    
                    # 计算延迟
                    if exponential:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                    else:
                        delay = base_delay
                    
                    logger_func(
                        f"{func.__name__} 失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}. "
                        f"等待 {delay:.1f}s 后重试"
                    )
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator


def with_circuit_breaker(
    circuit_breaker: CircuitBreaker,
    fallback: Optional[Callable] = None,
):
    """
    熔断器装饰器
    
    Args:
        circuit_breaker: 熔断器实例
        fallback: 熔断时的回退函数
    
    Example:
        breaker = CircuitBreaker()
        
        @with_circuit_breaker(breaker, fallback=lambda: default_value)
        async def call_external_api():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if not circuit_breaker.can_execute():
                logger.warning(f"{func.__name__} 被熔断器拒绝")
                if fallback:
                    return fallback()
                raise CircuitBreakerError(f"Circuit breaker is OPEN for {func.__name__}")
            
            try:
                result = await func(*args, **kwargs)
                circuit_breaker.record_success()
                return result
            except Exception as e:
                circuit_breaker.record_failure()
                raise
        
        return wrapper
    return decorator


async def safe_execute(
    func: Callable,
    *args,
    default: Any = None,
    exceptions: tuple = (Exception,),
    logger_func: Optional[Callable] = None,
    **kwargs
) -> Any:
    """
    安全执行函数，捕获异常并返回默认值
    
    Args:
        func: 要执行的函数
        default: 失败时的默认返回值
        exceptions: 要捕获的异常类型
        logger_func: 日志函数
    
    Example:
        result = await safe_execute(
            embedding_service.embed,
            text,
            default=[0.0] * 1024,
            exceptions=(httpx.RequestError,)
        )
    """
    if logger_func is None:
        logger_func = logger.error
    
    try:
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    except exceptions as e:
        logger_func(f"{func.__name__} 执行失败：{e}")
        return default
    except Exception as e:
        logger_func(f"{func.__name__} 未知错误：{e}")
        return default
```

---

### 3.2 背压控制

**文件**: `src/memos_graph/utils/backpressure.py`

```python
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
        limiter = RateLimiter(rate=10, capacity=20)  # 每秒 10 个，桶容量 20
        
        async def make_request():
            await limiter.acquire()  # 等待获取令牌
            # ... 执行请求 ...
    """
    
    def __init__(self, rate: float, capacity: Optional[int] = None):
        """
        Args:
            rate: 每秒令牌数
            capacity: 桶容量 (默认等于 rate)
        """
        self.rate = rate
        self.capacity = capacity or int(rate)
        self.tokens = float(self.capacity)
        self.last_update = datetime.utcnow()
        self._waiters = deque()
    
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
            
            # 计算等待时间
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
        
        # 生产者
        await queue.put(item)  # 满时等待
        
        # 消费者
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
                
                queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.exception(f"Worker 错误：{e}")
    
    # 启动 worker
    workers = [asyncio.create_task(worker()) for _ in range(max_concurrent)]
    
    # 放入所有项
    for item in items:
        await queue.put(item)
    
    # 等待所有项处理完成
    await queue.queue.join()
    
    # 停止 worker
    processing = False
    await asyncio.gather(*workers, return_exceptions=True)
    
    if errors:
        logger.warning(f"处理完成，{len(errors)} 项失败")
    
    return results
```

---
