# memos-graph v0.1.0 Task Breakdown

> **目的**：把 SPEC §0.1 P0 任务 + TEST_SPEC 测试点 → 拆为可执行的子任务，标依赖/工时/责任人/验收。
> **使用**：未来真要实装时按本文档排期。

---

## 0. 总览

- **12 个 P0 任务**（来自 SPEC §0.1）
- **拆为 47 个子任务**
- **总预估工时**：~140 工时（1 人 1 月 / 4 人 1 周）
- **关键路径**：DB → Migrations → 5 阶段 recall → Embedding → API → Tests
- **可并行**：Heartbeat / Pack / Viewer / CLI 互不依赖

---

## 1. 任务依赖图

```
T1 (DB Schema)
 │
 ├── T2 (Async Session 修复)
 │    │
 │    └── T3 (Alembic 异步化)
 │         │
 │         └── T4 (Migrations 跑通 + 验证) ───┐
 │                                            │
T5 (5 阶段 Recall Engine) ◄────────────────────┤
 │                                             │
 ├── T6 (Embedding Service) ◄──────────────────┤
 │    │                                        │
 │    ├── T7 (Recall 集成 Embedding) ◄─────────┤
 │    │                                        │
 │    └── T8 (API Memories search 接入) ◄──────┤
 │                                             │
T9 (LLM 抽取 prompt 关闭入口) ◄────────────────┤ [W1, 0 依赖]
 │                                             │
T10 (CLI 14 个命令) ◄─────────────────────────┤
 │                                             │
T11 (Pack 协议) ◄─────────────────────────────┤
 │                                             │
T12 (Heartbeat 调度) ◄─────────────────────────┤
 │                                             │
T13 (Viewer 3 页面) ◄─────────────────────────┤
 │                                             │
T14 (Tests 全部) ◄─── T5-T13 全部 ─────────────┘
```

---

## 2. 子任务表（47 个）

### T1: DB Schema（0.5 天）

| ID | 任务 | 文件 | 验收 | 工时 |
|----|------|------|------|------|
| T1.1 | 11 张表 SQLAlchemy 模型声明 | `db/models.py` | 跟 alembic 0001 一致 | 2h |
| T1.2 | 2 个 junction 表 chunk_edges / chunk_entities | `db/models.py` | TEST_SPEC DB-M-06/07 通过 | 1h |
| T1.3 | 10 个不变量验证（SPEC §2.2）| `db/models.py` 注释 | TEST_SPEC DB-M-01..12 通过 | 2h |

### T2: Async Session 修复（0.5 天）

> S1 MOA 评审 P0-bug

| ID | 任务 | 文件 | 验收 | 工时 |
|----|------|------|------|------|
| T2.1 | `get_session` 改 `async def` + `@asynccontextmanager` | `db/session.py` | DB-S-01..05 通过 | 3h |
| T2.2 | pool 配置（size=10, recycle=3600）| `db/session.py` | 内存泄漏测试通过 | 1h |

### T3: Alembic 异步化（0.5 天）

> S1 MOA 评审 P0-bug

| ID | 任务 | 文件 | 验收 | 工时 |
|----|------|------|------|------|
| T3.1 | `db/migrations.py` 用 `alembic.command.upgrade` 异步封装 | `db/migrations.py` | DB-MIG-01..04 通过 | 4h |
| T3.2 | 迁移超时保护 `asyncio.timeout(30)` | `db/migrations.py` | TEST_SPEC 通过 | 1h |

### T4: Migrations 跑通 + 验证（0.5 天）

| ID | 任务 | 文件 | 验收 | 工时 |
|----|------|------|------|------|
| T4.1 | `memos-graph migrate` 命令跑通 | `cli.py` | 干净 PG 上一次建全表 | 2h |
| T4.2 | 迁移回滚脚本 | `db/migrations.py` | `downgrade -1` 跑通 | 2h |

### T5: 5 阶段 Recall Engine（7 天）⚠️ 最大

> **关键路径**。包含 4 个子模块。**MOA v0.1.0 评审：原 T5.4 工时低估（12h → 20h），拆 T5.4a/4b**

| ID | 任务 | 文件 | 验收 | 工时 |
|----|------|------|------|------|
| T5.1 | `recall/fuzzy.py` PostgreSQL tsvector FTS（含词典/trigger/索引类型调优）| `recall/fuzzy.py` | REC-FTS-01..05 通过 | 10h |
| T5.2 | `recall/vector.py` pgvector cosine + HNSW（含 m/ef_construction 参数调优）| `recall/vector.py` | REC-VEC-01..05 通过 | 12h |
| T5.3 | `recall/graph.py` 1-hop BFS 邻居 + 衰减 | `recall/graph.py` | REC-GRAPH-01..05 通过 | 8h |
| T5.4a | `recall/pipeline.py` 5 阶段编排 + RRF | `recall/pipeline.py` | REC-PIP-01..10 通过（orchestration 部分）| 14h |
| T5.4b | `recall/pipeline.py` MMR 重排 + 时间衰减 + scope 过滤 | `recall/pipeline.py` | REC-PIP-03/04/05 通过 | 8h |
| T5.5 | `recall/__init__.py` 暴露 `RecallEngine` 类 | `recall/__init__.py` | 公开 API 完整 | 2h |

**T5.4a/4b 边界**（防 scope creep）：
- 5.4a IN: asyncio.gather 5 阶段 / RRF 融合 / 空结果处理
- 5.4a OUT: MMR / 时间衰减 / scope 过滤（留 5.4b）
- 5.4b IN: MMR 算法 / 7 天衰减 / private/shared scope 过滤
- 5.4b OUT: RRF / 阶段编排 / graph decay 参数

### T6: Embedding Service（2 天）

| ID | 任务 | 文件 | 验收 | 工时 |
|----|------|------|------|------|
| T6.1 | `embedding/base.py` abstract Embedder | `embedding/base.py` | EMB-B-01..03 通过 | 2h |
| T6.2 | `embedding/ollama.py` HTTP 客户端 | `embedding/ollama.py` | EMB-O-01..04 通过 | 6h |
| T6.3 | `embedding/cache.py` SQLite 缓存 | `embedding/cache.py` | EMB-C-01..05 通过 | 4h |
| T6.4 | `embedding/__init__.py` 暴露 `EmbeddingService` | `embedding/__init__.py` | | 2h |

### T7: Recall 集成 Embedding（1 天）

| ID | 任务 | 文件 | 验收 | 工时 |
|----|------|------|------|------|
| T7.1 | `POST /api/v1/memories` 异步后台 embed | `api/memories.py` | EMB-I-01..03 通过 | 4h |
| T7.2 | embed 失败不丢文本 | `api/memories.py` | warn log + 文本仍写 | 2h |
| T7.3 | 写 chunk 立即返回 | `api/memories.py` | P50 < 50ms | 2h |

### T8: API Memories search 接入真 Recall（0.5 天）

| ID | 任务 | 文件 | 验收 | 工时 |
|----|------|------|------|------|
| T8.1 | `/api/v1/memories/search` 替换 `ILIKE` → `RecallEngine` | `api/memories.py` | API-M-07/08 通过 | 3h |
| T8.2 | `use_graph` / `graph_decay` 参数接入 | `api/memories.py` | REC-PIP-09/10 通过 | 1h |

### T9: LLM 抽取 prompt 关闭入口（0.5 天）

> SPEC §0.2 范围冻结

| ID | 任务 | 文件 | 验收 | 工时 |
|----|------|------|------|------|
| T9.1 | `llm/client.py` 加 `enabled` 开关 | `llm/client.py` | env `MEMOS_GRAPH_LLM_EXTRACT_ENABLED=false` 时不调 | 2h |
| T9.2 | 6 个 prompt 默认 disabled | `llm/prompts/*.py` | 配置项 `extract_enabled` 默认 false | 2h |

### T10: CLI 14 个命令（1.5 天）

| ID | 任务 | 文件 | 验收 | 工时 |
|----|------|------|------|------|
| T10.1 | `memos-graph doctor` | `cli.py` | CLI-03/04 通过 | 4h |
| T10.2 | `memos-graph config show/set` | `cli.py` | CLI-05/06 通过 | 4h |
| T10.3 | `memos-graph recall-debug` | `cli.py` | CLI-07/08 通过 | 4h |
| T10.4 | 验证已有 12 个命令 | `cli.py` | 全部可执行 | 2h |

### T11: Pack 协议（3 天）

| ID | 任务 | 文件 | 验收 | 工时 |
|----|------|------|------|------|
| T11.1 | `pack/loader.py` 解析 pack.yaml | `pack/loader.py` | PK-L-01..07 通过 | 4h |
| T11.2 | `pack/installer.py` install / 升级 / 保护 | `pack/installer.py` | PK-I-01..06 通过 | 8h |
| T11.3 | `pack/runner.py` run / spawn runtime | `pack/runner.py` | PK-R-01..05 通过 | 6h |
| T11.4 | `pack/registry.py` packs 表操作 | `pack/registry.py` | PK-REG-01..03 通过 | 4h |
| T11.5 | `pack/__init__.py` 暴露 `PackManager` | `pack/__init__.py` | | 2h |

### T12: Heartbeat 调度（2 天）

| ID | 任务 | 文件 | 验收 | 工时 |
|----|------|------|------|------|
| T12.1 | `heartbeat/rules.py` HEARTBEAT.md 解析 | `heartbeat/rules.py` | HB-R-01..05 通过 | 4h |
| T12.2 | `heartbeat/scheduler.py` asyncio task | `heartbeat/scheduler.py` | HB-S-01..06 通过 | 6h |
| T12.3 | `heartbeat/deliver.py` 飞书投递 + 重试 | `heartbeat/deliver.py` | HB-D-01..04 通过 | 4h |
| T12.4 | `heartbeat/message.py` 模板选取 | `heartbeat/message.py` | HB-M-01..04 通过 | 2h |

### T13: Viewer 3 页面（2 天）

| ID | 任务 | 文件 | 验收 | 工时 |
|----|------|------|------|------|
| T13.1 | `viewer/templates/index.html` | `viewer/templates/` | VW-R-01 通过 | 2h |
| T13.2 | `viewer/templates/state.html` | `viewer/templates/` | VW-T-01 通过 | 3h |
| T13.3 | `viewer/templates/timeline.html` | `viewer/templates/` | VW-T-02 通过 | 3h |
| T13.4 | `viewer/templates/promises.html` | `viewer/templates/` | VW-T-03/04 通过 | 3h |
| T13.5 | `viewer/server.py` 路由 + 静态资源 | `viewer/server.py` | VW-R-01..05 通过 | 3h |

### T14: E2E Tests + CI（2 天）

> **MOA v0.1.0 评审：单元/集成测试"Embedded"嵌进各任务，T14 只负责 E2E + CI**
> - 单元/集成测试 = T1-T13 各自的 DoD（写代码时同步写测试）
> - T14 = E2E（API/CLI/Viewer）+ 性能 + 安全 + CI

| ID | 任务 | 文件 | 验收 | 工时 |
|----|------|------|------|------|
| T14.1 | E2E: `tests/test_api_e2e.py` (API-M/A/E/PR/U E2E) | `tests/test_api_e2e.py` | 30 测试通过 | 6h |
| T14.2 | E2E: `tests/test_cli_e2e.py` (CLI-*) | `tests/test_cli_e2e.py` | 10 测试通过 | 3h |
| T14.3 | E2E: `tests/test_viewer_e2e.py` (VW-*) | `tests/test_viewer_e2e.py` | 9 测试通过 | 3h |
| T14.4 | 性能: `tests/test_perf.py` (PERF-*) | `tests/test_perf.py` | 9 测试通过 | 4h |
| T14.5 | 安全: `tests/test_security.py` (SEC-*) | `tests/test_security.py` | 7 测试通过 | 2h |
| T14.6 | CI 集成 `.github/workflows/test.yml` | `.github/workflows/` | push 触发 + perf 回归报警 | 3h |

---

## 3. 工时汇总

| 任务 | 子任务数 | 工时 | 备注 |
|------|---------|------|------|
| T1-T4 (DB + Migration) | 9 | 22h | 关键路径 |
| T5 (5 阶段 Recall) | 5 | 34h | **最大块** |
| T6 (Embedding) | 4 | 14h | 关键路径 |
| T7-T8 (集成) | 5 | 12h | |
| T9 (Scope freeze) | 2 | 4h | |
| T10 (CLI) | 4 | 14h | |
| T11 (Pack) | 5 | 24h | |
| T12 (Heartbeat) | 4 | 16h | |
| T13 (Viewer) | 5 | 14h | |
| T14 (Tests) | 12 | 45h | **次大块** |
| **合计** | **47** | **~140h** | **~ 17.5 工作日 / 1 人 1 月** |

---

## 4. 排期建议

### 4.1 单人串行

```
W1: T1-T4 (DB 全部)
W2: T6 (Embedding)  + T9 (scope freeze)
W3: T5.1-T5.3 (Recall 子模块)
W4: T5.4-T5.5 (Recall pipeline) + T7-T8 (集成)
W5: T11 (Pack) + T12 (Heartbeat) + 并行
W6: T10 (CLI) + T13 (Viewer)
W7: T14 (Tests) 全部
W8: 修复 + 文档 + 发布
```

### 4.2 4 人并行

```
W1: 全员 T1-T4 (DB)
W2: A=T5.1, B=T6, C=T11, D=T12
W3: A=T5.2-T5.3, B=T7-T8, C=T11.2-T11.3, D=T12.2-T12.3
W4: A=T5.4-T5.5, B=T6.3-T6.4, C=T11.4-T11.5, D=T12.4
W5: 全员 T14 (Tests) + T9 (scope freeze) + T10 (CLI) + T13 (Viewer)
W6: 集成 + 修复 + 文档
```

### 4.3 风险点

- **T5 (Recall) 容易超期**：5 阶段算法 + 边界多，预留 +30% buffer
- **T14 (Tests) 容易缩水**：150+ 测试点可能 1 周写不完，分批
- **T11 (Pack) 跟 OpenClaw 协议耦合**：OpenClaw 升级可能 break，要锁版本

---

## 5. 验收 (Definition of Done)

> **MOA v0.1.0 评审：DoD 必须量化，去掉 "SPEC §11" 引用**

### 5.1 全局 DoD（每个子任务都适用）

- [ ] 代码实装 + 单元测试同步（embedded）
- [ ] 集成测试覆盖所有 P0-bug 修复
- [ ] `pytest -m "not perf and not live"` 全绿
- [ ] **覆盖率 ≥ 85%**（per-module 见 SPEC §11）
- [ ] `ruff check .` 无 error
- [ ] `pyright src/` 无 error（strict mode）
- [ ] `memos-graph doctor` 报 OK（**仅 T4 之后的任务要求**）
- [ ] PR review 通过

### 5.2 子任务 DoD 示例（去掉"必须跑 doctor"）

- **T1.1 (chunks 模型)**: TEST_SPEC DB-M-01..03 通过 + ruff + pyright
- **T5.4a (Pipeline 编排)**: TEST_SPEC REC-PIP-01/02/06/07/08/09/10 通过 + ruff + pyright
- **T11.2 (Pack installer)**: TEST_SPEC PK-I-01..06 通过 + ruff + pyright

### 5.3 整个 v0.1.0 DoD
- [ ] 47 个子任务全 ✅
- [ ] pytest 全绿，覆盖率 ≥ 85%
- [ ] `memos-graph doctor` 报 all green
- [ ] `memos-graph pack install ./packs/nako` 跑通
- [ ] `memos-graph pack run nako` 启动 + 心跳调度
- [ ] 飞书跟 Nako 聊 3 句 + 离线 48h 收心跳
- [ ] README 完整
- [ ] v0.1.0 tag 推到 git

---

## 6. 任务卡模板（每个子任务用）

```markdown
### TASK-{ID}
- **标题**：
- **文件**：
- **依赖**：TASK-{prev}
- **工时**：Xh
- **验收**：
  - [ ] TEST_SPEC-{X} 通过
  - [ ] 无 lint error
  - [ ] type check pass
- **风险**：
- **负责人**：
```

---

**状态**：✅ Task Breakdown v0.1 钉死，等待 MOA 评审
