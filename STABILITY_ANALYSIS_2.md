## 2. 外部依赖拖死风险 (External Dependency Risks)

### 2.1 Embedding API 超时 - 高风险 🔴

#### 风险点 2.1: `embedding/__init__.py` 第 82-134 行

**问题**: SiliconflowEmbedder 有超时但无重试机制

```python
# 第 102-134 行 - 当前代码
try:
    resp = await self._client.post(...)
    resp.raise_for_status()
except httpx.HTTPStatusError as e:
    logger.error(...)
    return [zero_vector for _ in texts]  # ✅ 优雅降级是好的
except httpx.RequestError as e:
    logger.error(...)
    return [zero_vector for _ in texts]
```

**评估**: 
- ✅ 优雅降级 (返回零向量) 防止崩溃
- ❌ 无重试机制，瞬时网络故障导致质量下降
- ❌ 无熔断器，持续失败时仍频繁调用

**发生概率**: 中 (网络波动)  
**影响程度**: 中 (检索质量下降，但服务可用)

**修复方案**: 添加重试 + 熔断

```python
import asyncio
from datetime import datetime, timedelta

class CircuitBreaker:
    """简单熔断器实现"""
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED | OPEN | HALF_OPEN
    
    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"熔断器打开：{self.failure_count} 次失败")
    
    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = "HALF_OPEN"
                return True
            return False
        return True  # HALF_OPEN 允许一次尝试

# 在 SiliconflowEmbedder 中使用
class SiliconflowEmbedder(Embedder):
    def __init__(self, ...):
        # ... 现有初始化 ...
        self._circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        self._retry_delays = [1, 2, 4, 8, 16]  # 指数退避
    
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        zero_vector = [0.0] * self._dimension
        
        # 检查熔断器
        if not self._circuit_breaker.can_execute():
            logger.warning("Embedding API 熔断中，返回零向量")
            return [zero_vector for _ in texts]
        
        # 重试逻辑
        last_error = None
        for attempt, delay in enumerate(self._retry_delays + [0]):
            if attempt > 0:
                logger.info(f"Embedding 重试 {attempt}/{len(self._retry_delays)}")
                await asyncio.sleep(delay)
            
            try:
                resp = await self._client.post(...)
                resp.raise_for_status()
                data = resp.json()
                embeddings = [item["embedding"] for item in data["data"]]
                self._circuit_breaker.record_success()
                return embeddings
            except httpx.RequestError as e:
                last_error = e
                self._circuit_breaker.record_failure()
                if self._circuit_breaker.state == "OPEN":
                    break
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:  # 服务端错误才重试
                    last_error = e
                    self._circuit_breaker.record_failure()
                    if self._circuit_breaker.state == "OPEN":
                        break
                else:
                    logger.error(f"Embedding API HTTP {e.response.status_code}")
                    return [zero_vector for _ in texts]
        
        logger.error(f"Embedding API 所有重试失败：{last_error}")
        return [zero_vector for _ in texts]
```

---

### 2.2 LLM API 超时/失败 - 高风险 🔴

#### 风险点 2.2: `llm/client.py` 第 26-42 行

**问题**: `chat()` 方法无重试、无熔断

```python
async def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
    try:
        resp = await self._client.post("/chat/completions", ...)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except httpx.HTTPError as e:
        logger.error(f"LLM request failed: {e}")
        raise  # ❌ 直接抛出，调用方可能崩溃
```

**影响**:
- LLM API 失败 → recall 引擎崩溃
- 无超时保护 → 可能无限等待
- 无熔断 → 持续失败时仍频繁调用

**发生概率**: 中  
**影响程度**: 高 (检索功能完全失效)

**修复方案**:

```python
# 在 LLMClient 类中添加
class LLMClient:
    def __init__(self, ...):
        # ... 现有初始化 ...
        self._circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=120)
        self._retry_delays = [1, 2, 4]  # LLM 重试次数少一些
    
    async def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        if not self._circuit_breaker.can_execute():
            raise LLMError("LLM API 熔断中")
        
        last_error = None
        for attempt, delay in enumerate(self._retry_delays + [0]):
            if attempt > 0:
                await asyncio.sleep(delay)
            
            try:
                resp = await self._client.post("/chat/completions", json={...}, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                self._circuit_breaker.record_success()
                return data["choices"][0]["message"]["content"]
            except httpx.TimeoutException as e:
                last_error = e
                self._circuit_breaker.record_failure()
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                    last_error = e
                    self._circuit_breaker.record_failure()
                else:
                    logger.error(f"LLM API HTTP {e.response.status_code}")
                    raise LLMError(f"LLM request failed: {e}")
        
        raise LLMError(f"LLM API 所有重试失败：{last_error}")

class LLMError(Exception):
    """LLM 调用失败异常"""
    pass
```

---

### 2.3 数据库连接池耗尽 - 中风险 🟡

#### 风险点 2.3: `db/session.py` 第 14-26 行

**问题**: 连接池大小固定为 10，无动态扩展

```python
def create_session_factory(database_url: str, pool_size: int = 10, ...):
    engine = create_async_engine(
        database_url,
        pool_size=pool_size,  # ❌ 固定大小
        pool_recycle=pool_recycle,
        pool_pre_ping=True,  # ✅ 这个配置是好的
    )
```

**影响**:
- 高并发时连接池耗尽
- 请求排队等待，响应时间变长
- 可能触发超时

**发生概率**: 低 (取决于负载)  
**影响程度**: 中 (性能下降)

**修复方案**:

```python
def create_session_factory(
    database_url: str,
    pool_size: int = 10,
    max_overflow: int = 20,  # ✅ 新增：允许临时扩展
    pool_recycle: int = 3600,
    pool_timeout: int = 30,   # ✅ 新增：获取连接超时
):
    engine = create_async_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,  # 允许额外 20 个连接
        pool_recycle=pool_recycle,
        pool_pre_ping=True,
        pool_timeout=pool_timeout,  # 30 秒超时
        echo=False,
    )
```

---
