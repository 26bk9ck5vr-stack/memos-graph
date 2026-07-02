# memos-graph TDD Test Spec v0.1.0

> **目的**：给 v0.1.0 每个 module 写"**测试契约**"（不实装测试代码，只描述输入/输出/边界/不变量）。
> **使用**：后续真要实装时，按本 spec 写 `pytest` 测试。
> **与 SPEC.md 关系**：本文件是 SPEC §0.1 P0 任务的**可测试化**展开。

---

## 0. 测试基础设施

### 0.1 必装的 fixture

> **⚠️ 关键：mock vs live 分离**（MOA v0.1.0 评审指出 fixture 矛盾）
> - 默认测试用 mock（快、CI 友好）
> - 显式标 `[LIVE]` 的测试用 testcontainers 真服务（CI 用 nightly job 跑）

```python
# tests/conftest.py 必须提供
@pytest.fixture
async def pg_engine():
    """testcontainers Python 起 PG 15 + pgvector，返回 async engine + sessionmaker"""
    # 见 SPEC §6.1 性能预算：硬件 4CPU/8GB，数据集 10k chunks

@pytest.fixture
async def ollama_mock():
    """httpx mock 返回固定 1024 维向量，避免真调 Ollama（默认）"""
    # 缺这个 fixture 跑测试就要真起 Ollama + 下模型，慢

@pytest.fixture(scope="session")
async def ollama_live():
    """[LIVE] testcontainers 起 Ollama 容器（仅 LIVE 测试用）"""
    # 用于 EMB-O-* 真调测试

@pytest.fixture(params=[100, 10000])
async def seed_chunks(request, pg_engine):
    """参数化 fixture：100 条（单元测试用）/ 10000 条（性能测试用）"""
    n = request.param
    # 100 条 < 1s 写入；10k 条 < 30s 写入
    # PERFORMANCE-* 自动用 10k 版本

@pytest.fixture
def client(pg_engine):
    """httpx.AsyncClient(transport=ASGITransport(app=app))"""
    # 端到端 API 测试
```

### 0.2 全局约定

- **所有测试用 asyncio**（`@pytest.mark.asyncio`）
- **所有测试用真 PG**（**禁用 SQLite**）—— pgvector / HNSW / ltree 都依赖 PG
- **每个测试结束 rollback 事务**，不留脏数据
- **时间相关**（last_interaction / heartbeat）用 `freezegun.freeze_time` 控制

---

## 1. db 模块测试

### 1.1 `db/session.py` 修复验证

> **背景**：S1 MOA 评审指出 `get_session` 非协程却用 `async with` 是 bug
> **⚠️ MOA v0.1.0 评审：并发测试必须真 asyncio.gather，不只数连接数**

| Test ID | 描述 | 期望 |
|---------|------|------|
| DB-S-01 | `get_session()` 返回对象支持 `async with` | 不抛 `TypeError` |
| DB-S-02 | `async with get_session() as s:` 进入后 `s` 是 `AsyncSession` | `isinstance(s, AsyncSession) == True` |
| DB-S-03 | 异常路径自动 rollback | `RuntimeError` 后事务回滚 |
| DB-S-04 | 正常路径自动 commit | 无异常时 commit |
| DB-S-05 | **`asyncio.gather(*[get_session() for _ in range(100)])` 真并发** | 无连接泄漏 + 无死锁 |

### 1.2 `db/models.py` 字段验证

| Test ID | 表.字段 | 描述 | 期望 |
|---------|---------|------|------|
| DB-M-01 | chunks.content | NOT NULL + 空字符串拒绝 | `IntegrityError` |
| DB-M-02 | chunks.scope | enum: private/shared/global | 写入 'invalid' 拒绝 |
| DB-M-03 | chunks.agent_id | NOT NULL | 缺值 `IntegrityError` |
| DB-M-04 | chunk_vectors.dimension | 跟 config.embedding.dimension 一致 | mismatch 抛 `ConfigMismatch` |
| DB-M-05 | chunk_vectors | 唯一性 chunk_id | 重复插入 `IntegrityError` |
| DB-M-06 | chunk_edges | (src, dst, relation) 唯一 | 重复 `IntegrityError` |
| DB-M-07 | chunk_edges | 不允许 self-loop (src==dst) | DB check 约束拒绝 |
| DB-M-08 | entities | (name, type) 唯一 | 大小写敏感 |
| DB-M-09 | agent_state | version 字段乐观锁 | 并发更新不丢更新 |
| DB-M-10 | events | payload 必须含 `schema_version` | 缺字段 reject |
| DB-M-11 | promises.status | enum: open/fulfilled/broken/expired | 状态机单向不回退 |
| DB-M-12 | packs.id | kebab-case 唯一 | 重复 `IntegrityError` |

### 1.3 `db/migrations.py` 异步化验证

> **背景**：S1 MOA 指出 `subprocess.run(["alembic", "upgrade"])` 阻塞事件循环

| Test ID | 描述 | 期望 |
|---------|------|------|
| DB-MIG-01 | `run_migrate()` 在 async 函数里被 await | 不阻塞 100ms 以上 |
| DB-MIG-02 | 迁移失败抛 `MigrationError` 而非 subprocess.CalledProcessError | 异常类型转换 |
| DB-MIG-03 | 迁移期间 PG 锁等待 | `asyncio.timeout(30)` 保护 |
| DB-MIG-04 | 迁移幂等 | 跑两次结果一致 |

---

## 2. recall 模块测试（v0.1 最大缺口）

### 2.1 `recall/fuzzy.py` — FTS 阶段

| Test ID | 输入 | 期望 top-3 |
|---------|------|-----------|
| REC-FTS-01 | query="Electron CDP" | 3 条含 Electron 和 CDP 关键词的 chunk |
| REC-FTS-02 | query="电子 客户端" | 中文 CJK 退化为 pattern 匹配（ILIKE） |
| REC-FTS-03 | query="" | 拒绝（HTTP 400）|
| REC-FTS-04 | 100 chunks 里 query "needle" | 命中 1 条且 top-1 |
| REC-FTS-05 | 同义词 "cache" / "缓存" 各自 | 不要求语义同（v0.1 不做 query_expand）|

### 2.2 `recall/vector.py` — 向量阶段

| Test ID | 描述 | 期望 |
|---------|------|------|
| REC-VEC-01 | 相似 query 返回 top-K | 5 条按 cosine 距离降序 |
| REC-VEC-02 | 完全不相关 query | top-K 但 score 全低于阈值 |
| REC-VEC-03 | 向量维度不匹配 | 抛 `DimensionMismatch` |
| REC-VEC-04 | 空表 | 返回空列表（不抛） |
| REC-VEC-05 | HNSW 索引真被使用 | `EXPLAIN` 含 "Index Scan using idx_vectors_hnsw" |

### 2.3 `recall/graph.py` — 图谱扩散阶段

| Test ID | 描述 | 期望 |
|---------|------|------|
| REC-GRAPH-01 | top-30 chunk 各自 1-hop 邻居 | 返回 ≤ 30 × degree 个邻居 |
| REC-GRAPH-02 | 邻居到 query 的相似度计算 | 用向量 cosine |
| REC-GRAPH-03 | 衰减因子 0.3 | 邻居 score = 原 score × 0.3 |
| REC-GRAPH-04 | 无限图（环路） | BFS depth=2 截断 |
| REC-GRAPH-05 | 无邻居的孤立 chunk | 跳过，不影响 top-30 |

### 2.4 `recall/pipeline.py` — 5 阶段编排

| Test ID | 描述 | 期望 |
|---------|------|------|
| REC-PIP-01 | 5 阶段并发 | FTS/向量/Pattern/Graph seed 并行跑，< 300ms |
| REC-PIP-02 | RRF 融合 | score = Σ 1/(k+rank)，k=60 |
| REC-PIP-03 | MMR 重排去冗余 | 相似度 > 0.95 的两条只留 1 条 |
| REC-PIP-04 | 时间衰减 | 7 天前 chunk 分数乘 0.7 |
| REC-PIP-05 | scope 过滤 | scope=private 只看自己 agent |
| REC-PIP-06 | 最终 top-K=10 | 10 条按综合 score 降序 |
| REC-PIP-07 | 5 阶段任一失败 | 用 partial result，不全失败 |
| REC-PIP-08 | 空 query | HTTP 400 |
| REC-PIP-09 | use_graph=false | 跳过 stage 4（graph diffusion）|
| REC-PIP-10 | graph_decay=0.5（用户可调）| 邻居 score 衰减 0.5 而非默认 0.3 |

---

## 3. embedding 模块测试

### 3.1 `embedding/base.py` 抽象类

| Test ID | 描述 | 期望 |
|---------|------|------|
| EMB-B-01 | 抽象方法未实现 | 继承类实例化抛 `TypeError` |
| EMB-B-02 | `embed(text)` 返回 list[float] | 长度 == dimension |
| EMB-B-03 | `embed_batch(texts)` 批处理 | 一次性调用上游 |

### 3.2 `embedding/ollama.py`

| Test ID | 描述 | 期望 |
|---------|------|------|
| EMB-O-01 `[LIVE]` | 真调 `POST http://localhost:11434/api/embeddings` | 返回 1024 维（**用 ollama_live fixture**） |
| EMB-O-02 `[LIVE]` | Ollama 未启动 | 抛 `EmbeddingServiceError` |
| EMB-O-03 | 文本 > 模型 max tokens（**mock**）| 截断 + 警告日志 |
| EMB-O-04 | nomic-embed-text vs mxbai-embed-large（**mock**）| dimension 分别为 768 / 1024 |

### 3.3 `embedding/cache.py` SQLite 缓存

| Test ID | 描述 | 期望 |
|---------|------|------|
| EMB-C-01 | 同文本二次 embed | 第二次走缓存，0 HTTP 调用 |
| EMB-C-02 | 文本 hash 算错 | cache miss，走 Ollama |
| EMB-C-03 | 模型切换 | 旧缓存作废（key 含 model） |
| EMB-C-04 | 缓存损坏 | 自动重建，Ollama 重 embed |
| EMB-C-05 | 10w 条缓存 | 查询 < 1ms |

### 3.4 集成测试

| Test ID | 描述 | 期望 |
|---------|------|------|
| EMB-I-01 | `POST /api/v1/memories` 自动调 embed | chunk_vectors 写入 |
| EMB-I-02 | embed 失败时 chunk 仍写 | 不丢文本，只 log warning |
| EMB-I-03 | embed 异步后台跑 | 写 chunk 立即返回，不等 embed |

---

## 4. heartbeat 模块测试

### 4.1 `heartbeat/rules.py` HEARTBEAT.md 解析

| Test ID | 描述 | 期望 |
|---------|------|------|
| HB-R-01 | 解析 5 阶段规则 | 返回 dict{stage: hours} |
| HB-R-02 | quiet_hours "23:00-08:00" | 当前 02:00 → quiet |
| HB-R-03 | 缺文件 | 抛 `HeartbeatConfigError` |
| HB-R-04 | 非法阈值 | 抛 `HeartbeatConfigError` |
| HB-R-05 | 时区配置 user.timezone | 用 user 时区判断 |

### 4.2 `heartbeat/scheduler.py` 调度

| Test ID | 描述 | 期望 |
|---------|------|------|
| HB-S-01 | 每 30 分钟 tick | asyncio task 真在跑 |
| HB-S-02 | tick 时按 threshold 触发 | `last_interaction < threshold[stage]` |
| HB-S-03 | 触发后投递 | `deliver(agent, msg)` 被调 |
| HB-S-04 | 投递成功 | `last_heartbeat = now()` |
| HB-S-05 | 投递失败 3 次 | 放弃 + 写 events 表 |
| HB-S-06 | 心跳期间 daemon 退出 | 重启后从上次 tick 续 |

### 4.3 `heartbeat/deliver.py` 飞书投递

| Test ID | 描述 | 期望 |
|---------|------|------|
| HB-D-01 | mock 飞书 API | 200 → 标记成功 |
| HB-D-02 | mock 飞书 API | 4xx → 标记失败（不重试）|
| HB-D-03 | mock 飞书 API | 5xx → 重试，最多 3 次 |
| HB-D-04 | 网络超时 | 重试 + 写 events |

### 4.4 心跳消息内容

| Test ID | 描述 | 期望 |
|---------|------|------|
| HB-M-01 | 模板选取 | 从 HEARTBEAT.md 预设 3-5 段随机选 |
| HB-M-02 | 长度 ≤ 100 字 | 计数断言 |
| HB-M-03 | "主人大人"开头 | 字符串断言 |
| HB-M-04 | 阶段 1 vs 阶段 5 | 模板内容差异（不能一样）|

---

## 5. pack 模块测试

### 5.1 `pack/loader.py` pack.yaml 解析

| Test ID | 描述 | 期望 |
|---------|------|------|
| PK-L-01 | 标准 pack.yaml | 解析为 dict |
| PK-L-02 | 缺 id 字段 | 抛 `PackConfigError` |
| PK-L-03 | id 含大写 | 抛 `PackConfigError` |
| PK-L-04 | runtime 不在 {openclaw, hermes, claude-code} | 抛 `PackConfigError` |
| PK-L-05 | preserve_on_upgrade 含不在目录的文件 | 警告但通过 |
| PK-L-06 | memos_graph.required=false | 警告但通过 |
| PK-L-07 | heartbeat.schedule 非法 cron | 抛 `PackConfigError` |

### 5.2 `pack/installer.py`

| Test ID | 描述 | 期望 |
|---------|------|------|
| PK-I-01 | `pack install ./nako` | 复制到 `~/.local/share/memos-graph/packs/nako/` |
| PK-I-02 | `pack install --from-git <url>` | git clone + 走 install 逻辑 |
| PK-I-03 | `pack install --migrate-from=memos-local` | 一次性迁移 chunks |
| PK-I-04 | 已装 pack 重复装 | 拒绝（uninstall 再装）|
| PK-I-05 | install 失败回滚 | 已复制文件全删 |
| PK-I-06 | preserve 保护 | custom.md 不被覆盖（即使升级）|

### 5.3 `pack/runner.py`

| Test ID | 描述 | 期望 |
|---------|------|------|
| PK-R-01 | `pack run nako` 加载 agent_state 入 prompt | DB 快照注入 |
| PK-R-02 | `pack run nako` 启动 openclaw | subprocess 启动 |
| PK-R-03 | `pack run nako` 启动 heartbeat scheduler | daemon 内一并启 |
| PK-R-04 | runtime 进程退出非 0 | 重启 1 次，仍失败写 events |
| PK-R-05 | runtime 进程 30s 未启动 | 超时 + 写 events |

### 5.4 `pack/registry.py` packs 表操作

| Test ID | 描述 | 期望 |
|---------|------|------|
| PK-REG-01 | `GET /api/v1/packs` | 返回所有 enabled=true 的 pack |
| PK-REG-02 | install 后 DB 写入 | `packs.enabled=true` |
| PK-REG-03 | disable=true 的 pack | `GET /api/v1/packs` 不返回（但 list-all 仍返回）|

---

## 6. api 端点测试

### 6.1 `/api/v1/memories` 端到端

| Test ID | 描述 | 期望 |
|---------|------|------|
| API-M-01 | POST 无 content | 400 |
| API-M-02 | POST 正常 | 200 + 返回 id |
| API-M-03 | GET 不存在 id | 404 |
| API-M-04 | PUT 改 content | 200 + updated_at 更新 |
| API-M-05 | DELETE 后 GET | 404 |
| API-M-06 | POST scope=invalid | 400 |
| API-M-07 | POST 100 条 chunk 后 search | top-5 命中相关 |
| API-M-08 | search use_graph=false | 5 阶段变 4 阶段（无 graph diffusion）|

### 6.2 `/api/v1/agents/{id}/state` 乐观锁

| Test ID | 描述 | 期望 |
|---------|------|------|
| API-A-01 | PUT version=N 成功 | 200, version=N+1 |
| API-A-02 | PUT version=N 但 DB 是 N+1 | 409 Conflict |
| API-A-03 | **`asyncio.gather(*[put_state() for _ in range(10)])` 真并发** | 9 个失败，1 个成功 |
| API-A-04 | GET 不存在 agent | 404 |

### 6.3 `/api/v1/events`

| Test ID | 描述 | 期望 |
|---------|------|------|
| API-E-01 | POST event | 200 + 写 events |
| API-E-02 | GET 过滤 agent_id | 只返该 agent 的 events |
| API-E-03 | GET 过滤 type | 只返该 type |
| API-E-04 | GET 过滤 created_at 范围 | 只返范围内 |
| API-E-05 | POST payload 缺 schema_version | 400 |
| API-E-06 | POST event_type 不在 enum | 400 |

### 6.4 `/api/v1/promises`

| Test ID | 描述 | 期望 |
|---------|------|------|
| API-PR-01 | POST open promise | 200 + status=open |
| API-PR-02 | PUT 标记 fulfilled | 200 + status=fulfilled + fulfilled_at |
| API-PR-03 | 状态机回退 fulfilled→open | 400（不回退）|
| API-PR-04 | GET agent 的所有 promise | 按 due_at 升序 |

### 6.5 `/api/v1/users/{id}/profile`

| Test ID | 描述 | 期望 |
|---------|------|------|
| API-U-01 | GET 不存在 user | 200 + 空 profile（不 404）|
| API-U-02 | PUT 创建 | 200 |
| API-U-03 | 并发 PUT merge | v0.1 不做 merge → 最后一个赢 |
| API-U-04 | updated_by 字段自动写 | 等于当前 agent_id |

---

## 7. viewer 模块测试

### 7.1 路由

| Test ID | 描述 | 期望 |
|---------|------|------|
| VW-R-01 | GET / | 200 + 渲染 index.html |
| VW-R-02 | GET /state/{agent_id} | 200 + 渲染状态面板 |
| VW-R-03 | GET /timeline/{agent_id} | 200 + 渲染时间线 |
| VW-R-04 | GET /promises/{agent_id} | 200 + 渲染承诺看板 |
| VW-R-05 | 静态资源 | 200 + 正确 MIME |

### 7.2 模板

| Test ID | 描述 | 期望 |
|---------|------|------|
| VW-T-01 | 状态面板含 affinity/mood/stage | HTML 含三字段 |
| VW-T-02 | 时间线倒序 | 最新 event 在顶部 |
| VW-T-03 | 承诺看板标红 | due_at < now+24h 红色 |
| VW-T-04 | 空数据 | "暂无数据" 友好提示 |

---

## 8. CLI 测试

### 8.1 `cli` Click 框架

| Test ID | 描述 | 期望 |
|---------|------|------|
| CLI-01 | `memos-graph --version` | 0.1.0 |
| CLI-02 | `memos-graph --help` | 列出 14 个子命令 |
| CLI-03 | `memos-graph doctor` | 报告 PG + Ollama 状态 |
| CLI-04 | `memos-graph doctor` PG 关闭 | exit code 非 0 |
| CLI-05 | `memos-graph config show` | YAML 输出 |
| CLI-06 | `memos-graph config set model foo` | 更新 config + 提示重启 |
| CLI-07 | `memos-graph recall-debug "test"` | 5 阶段每个返回前 3 chunk |
| CLI-08 | `memos-graph recall-debug --stage=vector` | 只跑向量阶段 |
| CLI-09 | `memos-graph pack install <bad>` | 友好错误信息 |
| CLI-10 | `memos-graph pack list` | 表格输出 |

---

## 9. 性能测试（基准）

### 9.1 吞吐量

> **⚠️ MOA v0.1.0 评审：必须加 P95 + 失败阈值 + pytest-benchmark**

| Test ID | 数据集 | 操作 | 期望 | 失败阈值（CI fail） |
|---------|--------|------|------|---------------------|
| PERF-01 | 1k chunks | POST 单条 | P50 < 50ms | P99 > 200ms |
| PERF-02 | 10k chunks | search | P50 < 300ms, P95 < 700ms, P99 < 1s | P99 > 1.5s |
| PERF-03 | 10k chunks | 并发 10 search | P95 < 1s | P99 > 2s |
| PERF-04 | 100k events | GET 范围 | P50 < 100ms | P95 > 300ms |
| PERF-05 | 1k events/min | POST 持续 | 不丢事件 | 队列积压 > 100 |

**使用 pytest-benchmark**：
```python
def test_perf_search(benchmark, seed_chunks_10k, client):
    result = benchmark(client.post, "/api/v1/memories/search", json={"query": "test"})
    # 自动生成 P50/P95/P99 报告
    # CI 失败条件：相比基线回归 > 5%
```

### 9.2 资源

| Test ID | 资源 | 期望 |
|---------|------|------|
| PERF-R-01 | daemon 内存（空载）| < 100MB |
| PERF-R-02 | daemon 内存（10k chunks）| < 500MB |
| PERF-R-03 | pgvector HNSW 索引大小 | < 10k 向量 × 1024 维 × 4B = 40MB |
| PERF-R-04 | heartbeat 调度内存 | < 50MB |

### 9.3 硬件假设

> SPEC §6 提到，但未给具体值。**Test Spec 补上**：

- **CPU**：4 vCPU
- **RAM**：8GB
- **磁盘**：SSD
- **PG**：本地（localhost:5432）
- **Ollama**：本地（localhost:11434）
- **数据集**：10k chunks 中文为主 + 1k 英文
- **并发**：10 search / 1 write

---

## 10. 安全测试

| Test ID | 描述 | 期望 |
|---------|------|------|
| SEC-01 | 绑定 0.0.0.0 | 拒绝启动（v0.1 安全） |
| SEC-02 | SQL 注入 `content = "x'; DROP TABLE chunks; --"` | 参数化，无注入 |
| SEC-03 | 路径穿越 `agent_id = "../../etc/passwd"` | 拒绝（regex 验证）|
| SEC-04 | 嵌入大文本（10MB）| 拒绝（max content size）|
| SEC-05 | CORS | OPTIONS 请求 reject |
| SEC-06 | .env 文件权限 | 必须 600，宽松报警告 |
| SEC-07 | API key 出现在日志 | 写日志时 mask |

---

## 11. 测试覆盖率目标

| 模块 | 覆盖率目标 |
|------|----------|
| db/ | 95% |
| recall/ | 90% |
| embedding/ | 90% |
| heartbeat/ | 85% |
| pack/ | 90% |
| api/ | 90% |
| viewer/ | 70%（UI 测难）|
| cli/ | 80% |

**总体 ≥ 85%**。

---

## 12. 测试执行

### 12.1 命令

```bash
# 全跑
pytest -v --cov=memos_graph --cov-report=term-missing

# 单模块
pytest tests/test_recall.py -v

# 性能基准
pytest -m perf -v

# 跳过慢测
pytest -m "not slow" -v

# 测试 DB 隔离
TEST_DB_URL=postgresql://test:test@localhost:5433/test pytest
```

### 12.2 CI 集成（建议）

```yaml
# .github/workflows/test.yml
- uses: actions/setup-python@v5
  with: { python-version: "3.11" }
- run: pip install -e .[dev]
- run: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=test pgvector/pgvector:pg15
- run: pytest --cov
```

---

## 13. 跟 SPEC 闭环

本 Test Spec 暴露 SPEC 的 3 个缺口，下个 SPEC 修订要补：

1. **§6 性能环境**（已在本 Spec §9.3 补：4CPU/8GB/SSD/10k chunks）
2. **§2.2 不变量** 缺外键约束和向量维度一致性（建议在 SPEC v0.2.2 补 §2.3 "外键/索引全表"）
3. **§5 bug 清单** 混了 bug 和 feature（建议在 SPEC v0.2.2 拆 §5.1 P0-bug + §5.2 P0-feature）

---

**状态**：✅ TDD Test Spec 钉死 v0.1，等待 MOA 评审 → 进入 Task Breakdown 阶段
