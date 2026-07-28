# memos-graph 代码稳定性分析报告

**分析日期**: 2026-07-22  
**分析范围**: 代码层稳定性风险  
**目标**: 构建"稳定性环路"，确保 7x24 小时运行

---

## 执行摘要

| 风险类别 | 高风险项 | 中风险项 | 低风险项 |
|----------|----------|----------|----------|
| 进程崩溃 | 2 | 3 | 2 |
| 外部依赖拖死 | 3 | 2 | 1 |
| 资源泄漏 | 1 | 2 | - |

**整体稳定性评级**: ⚠️ **中风险** - 需要立即加固

---

## 1. 进程崩溃风险 (Crash Risks)

### 1.1 未捕获异常 - 高风险 🔴

#### 风险点 1.1: `api/realtime_sync.py` 第 188 行

**问题**: 后台任务 `asyncio.create_task()` 无异常捕获

```python
# 第 186-188 行 - 当前代码
asyncio.create_task(generate_embedding_async())  # ❌ 异常会静默丢失
```

**影响**: 
- Embedding API 失败时异常被吞噬，无法追踪
- 多次失败可能导致内存累积
- 无法触发告警

**发生概率**: 高 (每次写入都触发)  
**影响程度**: 中 (不崩溃主进程，但数据不一致)

**修复方案**:

```python
# 创建带异常捕获的包装器
async def safe_generate_embedding_async():
    try:
        await generate_embedding_async()
    except Exception as e:
        logger.exception(f"后台向量生成失败：{e}")

asyncio.create_task(safe_generate_embedding_async())  # ✅
```

---

#### 风险点 1.2: `server.py` 第 84-126 行

**问题**: startup/shutdown 事件处理器无异常保护

```python
# 第 84-94 行 - 当前代码
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # ❌ DB 失败直接崩溃
```

**影响**: 
- 数据库连接失败 → 服务无法启动
- LLM API 不可达 → 启动崩溃
- Neo4j 连接失败 → 未处理

**发生概率**: 低 (仅启动时)  
**影响程度**: 高 (服务完全不可用)

**修复方案**:

```python
@app.on_event("startup")
async def startup():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized")
    except Exception as e:
        logger.critical(f"Database startup failed: {e}")
        raise  # 启动失败是可接受的，但必须明确
```

---

### 1.2 内存泄漏风险 - 中风险 🟡

#### 风险点 1.3: `api/realtime_sync.py` 第 151-188 行

**问题**: 每个消息创建一个后台任务，无背压控制

```python
for msg in messages:  # 假设 100 条消息
    # ...
    asyncio.create_task(generate_embedding_async())  # 100 个并发任务
```

**影响**: 
- 大批量写入时内存爆炸
- HTTP 连接池耗尽
- Embedding API 速率限制触发

**发生概率**: 中 (取决于写入频率)  
**影响程度**: 高 (OOM 崩溃)

**修复方案**: 使用信号量限制并发

```python
# 在模块级别创建信号量
_embedding_semaphore = asyncio.Semaphore(10)  # 最多 10 个并发

async def safe_generate_embedding_async():
    async with _embedding_semaphore:  # ✅ 背压控制
        try:
            await generate_embedding_async()
        except Exception as e:
            logger.exception(f"后台向量生成失败：{e}")
```

---

### 1.3 数据库连接泄漏 - 高风险 🔴

#### 风险点 1.4: `db/session.py` 第 29-37 行

**问题**: `get_session()` 使用 `async with` 但异常时可能不关闭

```python
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if _async_session_factory is None:
        # ... 初始化 ...
    async with _async_session_factory() as session:  # ✅ 这部分是好的
        yield session
```

**但是** `api/realtime_sync.py` 第 226 行:

```python
await session.rollback()  # ❌ 如果 rollback 失败呢？
await session.close()     # ❌ 如果 close 失败呢？
```

**修复方案**: 使用 `try/finally` 确保清理

```python
@router.post("/sync/realtime")
async def realtime_sync(request: dict, session: AsyncSession = Depends(get_session)):
    try:
        # ... 业务逻辑 ...
        await session.commit()
    except Exception as e:
        logger.exception(f"Sync failed: {e}")
        try:
            await session.rollback()
        except Exception as rollback_error:
            logger.error(f"Rollback failed: {rollback_error}")
        raise HTTPException(status_code=500, detail=str(e))
    # finally 由 FastAPI 依赖注入处理关闭
```

---
