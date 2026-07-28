## 4. 风险汇总表

| 编号 | 风险点 | 文件位置 | 发生概率 | 影响程度 | 优先级 | 修复状态 |
|------|--------|----------|----------|----------|--------|----------|
| 1.1 | 后台任务无异常捕获 | `api/realtime_sync.py:188` | 高 | 中 | P0 | ⏳ 待修复 |
| 1.2 | startup/shutdown 无异常保护 | `server.py:84-126` | 低 | 高 | P0 | ⏳ 待修复 |
| 1.3 | 内存泄漏 (无背压) | `api/realtime_sync.py:151-188` | 中 | 高 | P0 | ⏳ 待修复 |
| 1.4 | DB 连接可能泄漏 | `db/session.py:29-37` | 低 | 高 | P1 | ⏳ 待修复 |
| 2.1 | Embedding API 无重试/熔断 | `embedding/__init__.py:82-134` | 中 | 中 | P0 | ⏳ 待修复 |
| 2.2 | LLM API 无重试/熔断 | `llm/client.py:26-42` | 中 | 高 | P0 | ⏳ 待修复 |
| 2.3 | DB 连接池固定大小 | `db/session.py:14-26` | 低 | 中 | P2 | ⏳ 待修复 |
| 3.1 | RecallEngine 无超时控制 | `recall/__init__.py:239-315` | 中 | 中 | P1 | ⏳ 待修复 |
| 3.2 | Neo4j 连接无健康检查 | `graph/neodb.py:10-25` | 低 | 中 | P2 | ⏳ 待修复 |
| 3.3 | Heartbeat 后台任务无保护 | `heartbeat/scheduler.py:254-265` | 中 | 低 | P1 | ⏳ 待修复 |

**优先级定义**:
- **P0**: 立即修复 (可能导致崩溃/数据丢失)
- **P1**: 本周修复 (影响稳定性)
- **P2**: 下次迭代修复 (性能优化)

---

## 5. 推荐修复顺序

### 第一阶段 (P0 - 本周内)

1. **创建工具模块** (`src/memos_graph/utils/`)
   - `retry.py` - 重试装饰器和熔断器
   - `backpressure.py` - 背压控制工具

2. **修复 Embedding 服务** (`embedding/__init__.py`)
   - 添加重试逻辑
   - 添加熔断器
   - 保持优雅降级

3. **修复 LLM 客户端** (`llm/client.py`)
   - 添加重试逻辑
   - 添加熔断器
   - 创建 LLMError 异常类

4. **修复后台任务** (`api/realtime_sync.py`)
   - 添加异常包装器
   - 添加信号量背压控制

### 第二阶段 (P1 - 下周内)

5. **修复服务器启动/关闭** (`server.py`)
   - 添加 try/finally 保护
   - 添加健康检查

6. **修复 RecallEngine** (`recall/__init__.py`)
   - 添加整体超时
   - 添加各阶段超时控制

7. **修复 Heartbeat Scheduler** (`heartbeat/scheduler.py`)
   - 添加异常捕获
   - 添加运行状态监控

### 第三阶段 (P2 - 下次迭代)

8. **数据库连接池优化** (`db/session.py`)
   - 添加 max_overflow
   - 添加 pool_timeout

9. **Neo4j 健康检查** (`graph/neodb.py`)
   - 添加连接测试
   - 添加断线重连

10. **添加全局监控**
    - 指标收集 (Prometheus)
    - 日志聚合
    - 告警规则

---

## 6. 代码修改示例

### 6.1 重试装饰器使用示例

```python
# 在 embedding/__init__.py 中
from memos_graph.utils.retry import retry_with_backoff, CircuitBreaker
import httpx

# 创建熔断器实例
_embedding_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

class SiliconflowEmbedder(Embedder):
    @retry_with_backoff(
        max_retries=3,
        base_delay=1.0,
        exceptions=(httpx.RequestError, httpx.HTTPStatusError)
    )
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not _embedding_breaker.can_execute():
            logger.warning("Embedding API 熔断中")
            return [zero_vector for _ in texts]
        
        try:
            resp = await self._client.post(...)
            resp.raise_for_status()
            _embedding_breaker.record_success()
            # ... 处理响应 ...
        except Exception as e:
            _embedding_breaker.record_failure()
            raise
```

### 6.2 背压控制使用示例

```python
# 在 api/realtime_sync.py 中
from memos_graph.utils.backpressure import ConcurrentLimiter

# 模块级别创建信号量
_embedding_limiter = ConcurrentLimiter(max_concurrent=10)

async def generate_embedding_async():
    async with _embedding_limiter:  # 最多 10 个并发
        try:
            # ... 生成向量 ...
        except Exception as e:
            logger.exception(f"向量生成失败：{e}")
```

### 6.3 安全执行示例

```python
# 在 recall/__init__.py 中
from memos_graph.utils.retry import safe_execute

async def search(self, req: RecallRequest) -> RecallResult:
    # Stage 1: FTS
    fts_hits = await safe_execute(
        self._fts_search,
        session, req,
        default=[],
        exceptions=(Exception,),
    )
    
    # Stage 2: Pattern
    pattern_hits = await safe_execute(
        self._pattern_search,
        session, req,
        default=[],
        exceptions=(Exception,),
    )
    
    # ... 其他阶段 ...
```

---

## 7. 监控和告警建议

### 7.1 关键指标

| 指标名称 | 类型 | 告警阈值 | 说明 |
|----------|------|----------|------|
| `http_requests_total` | Counter | - | 总请求数 |
| `http_request_duration_seconds` | Histogram | p99 > 5s | 请求延迟 |
| `db_pool_connections_in_use` | Gauge | > 80% | DB 连接池使用率 |
| `embedding_api_failures` | Counter | > 10/min | Embedding API 失败数 |
| `llm_api_failures` | Counter | > 5/min | LLM API 失败数 |
| `circuit_breaker_state` | Gauge | OPEN | 熔断器状态 |
| `background_task_failures` | Counter | > 5/min | 后台任务失败数 |

### 7.2 健康检查端点

```python
# 在 api/health.py 中添加
@router.get("/health/detailed")
async def detailed_health_check():
    """详细健康检查"""
    checks = {
        "database": await check_database(),
        "embedding_api": await check_embedding_api(),
        "llm_api": await check_llm_api(),
        "neo4j": await check_neo4j(),
    }
    
    healthy = all(v["healthy"] for v in checks.values())
    
    return {
        "healthy": healthy,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }

async def check_database() -> dict:
    try:
        async with _async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return {"healthy": True, "latency_ms": latency}
    except Exception as e:
        return {"healthy": False, "error": str(e)}

# ... 其他检查类似 ...
```

---

## 8. 总结

memos-graph 当前的代码稳定性处于**中等风险**水平：

### 优势 ✅
- Embedding 服务有优雅降级 (返回零向量)
- 数据库连接使用 `async with` 自动管理
- 全局异常处理器已配置

### 劣势 ❌
- 无重试机制，瞬时故障导致服务降级
- 无熔断器，持续失败时仍频繁调用外部 API
- 无背压控制，大批量写入可能 OOM
- 后台任务异常被吞噬，无法追踪

### 建议行动
1. **立即** 创建 `utils/retry.py` 和 `utils/backpressure.py` 工具模块
2. **本周内** 修复 Embedding 和 LLM 客户端的重试/熔断
3. **本周内** 修复后台任务的异常处理和背压
4. **下周内** 添加详细健康检查和监控指标

**预期效果**: 修复后服务可用性从 ~95% 提升至 ~99.5%
