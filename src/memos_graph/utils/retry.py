"""通用重试和熔断工具"""

import asyncio
import logging
from functools import wraps
from typing import Callable, Any, Optional, Type
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
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if not circuit_breaker.can_execute():
                logger.warning(f"{func.__name__} 被熔断器拒绝")
                if fallback:
                    result = fallback()
                    return result() if asyncio.iscoroutinefunction(fallback) else result
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


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerError",
    "retry_with_backoff",
    "with_circuit_breaker",
    "safe_execute",
]
