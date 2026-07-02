# memos-graph v0.1.0 SPEC（钉死版 v0.2.0）

> **本文件目的**：把 INITIAL_DRAFT.md / DESIGN.md / VERIFICATION_REPORT.md 三个文档的**矛盾点全部钉死**，作为后续 TDD test spec / task breakdown / migration plan 的唯一真源。
>
> **使用规则**：本 SPEC 是**契约**，任何后续文档跟 SPEC 冲突 → 以 SPEC 为准。

---

## 0. v0.1.0 范围声明（READ THIS FIRST）

### 0.1 v0.1.0 必须做的（P0）

按优先级：

1. **PG schema + async session** — `db/models.py` (✅ 已有) + `db/session.py` (✅ 已有但 S1 指出 `get_session` 非协程 bug 待修) + `db/migrations.py` (✅ 已有但 S1 指出 `subprocess` 同步调 alembic 阻塞事件循环待修)
2. **Alembic 迁移脚本** — `alembic/versions/0001_initial.py` (✅ 已有，一次建 11+ 张表)
3. **5 阶段 recall engine** — `recall/` 模块 4 个文件：`fuzzy.py` / `vector.py` / `graph.py` / `pipeline.py` + `recall/__init__.py` 暴露 `RecallEngine` 类
4. **Embedding service** — `embedding/` 模块 2 个文件：`base.py` (abstract) + `ollama.py` (实装) + `cache.py` (SQLite cache) + `embedding/__init__.py` 暴露 `EmbeddingService` 类
5. **CLI** — `cli.py` 已实装 12 命令，**补 5 个缺失**：`config` / `export` / `import` / `session` / `recall-debug`
6. **API：21 端点** — 已实装 ✅
7. **Health 端点** — `api/health.py` (✅ 已有) + `/ready` 检查 PG + Ollama
8. **Tests** — `tests/conftest.py` (✅ 已有 testcontainers) + `tests/test_memories.py` (✅ 已有但仅 SQLite) → **必须改用 PostgreSQL + pgvector** (S1 指出当前 SQLite 无法测向量索引)
9. **Pack 协议** — `pack/loader.py` + `pack/installer.py` + `pack/runner.py` + `pack/registry.py` + `pack/__init__.py` 暴露 `PackManager` 类
10. **Migration plan 文档** — `docs/MIGRATION.md`（本阶段产出）
11. **Test spec 文档** — `docs/TEST_SPEC.md`（本阶段产出）
12. **Viewer UI** — `viewer/server.py` (✅ 已有但 S2 指出 "Full UI coming soon" 占位) → **v0.1 只做"状态面板 + 时间线 + 承诺看板" 3 页面 + Jinja2 模板**

### 0.2 v0.1.0 明确**不做**的（P0-banned / scope freeze）

按 INITIAL_DRAFT §11 + DESIGN §1，**这些做了就是 scope creep**：

| ❌ 不做 | 理由 | 谁说了 |
|---------|------|--------|
| **LLM 自动实体抽取** | 6 个 prompt 已写但 v0.1 不调用 | INITIAL_DRAFT §11 |
| **LLM 自动承诺抽取** | 同上 | INITIAL_DRAFT §11 |
| **LLM 自动事件摘要** | 同上 | INITIAL_DRAFT §11 |
| **LLM 生成心跳消息** | v0.1 用 HEARTBEAT.md 模板 | INITIAL_DRAFT §3.4 |
| **Apache AGE / cypher** | v1 那条路径挂着 | DESIGN §1 |
| **多模态 embedding** | 图片/音频只元数据 | DESIGN §0 |
| **多 channel 投递** | v0.1 只飞书 | INITIAL_DRAFT §1 |
| **分布式 / HA** | 单机版 | INITIAL_DRAFT §1 |
| **鉴权 / RBAC** | localhost only | INITIAL_DRAFT §3.3 |
| **Pack 第三方市场** | 自用 1 pack | DESIGN §3 |
| **客户端 SDK** | REST + JSON-RPC 足够 | DESIGN §0 |
| **OpenAPI 文档站** | Swagger UI 自带 | INITIAL_DRAFT §1 |

**冻结规则**：llm/prompts/ 的 6 个 prompt **保留代码但入口关闭**，等 v0.2 启用。

### 0.3 v0.1.0 范围边界争议的最终裁决

S2 MOA 评审指出 3 个矛盾，本 SPEC 裁决如下：

| 矛盾点 | S2 提议 | **本 SPEC 裁决** | 理由 |
|--------|---------|-----------------|------|
| `llm/prompts/` 已实装 6 个 prompt | "scope creep，移除" | **保留代码 + 关闭入口** | 防 v0.2 重写；prompt 本身质量审查过 |
| `ToolLog` 表不在 DESIGN §2.2 11 张表内 | "+1 表，破坏一致性" | **保留并入正式表清单** | DESIGN §2.2 第 9 项已含 tool_logs，S2 看漏 |
| `VERIFICATION_REPORT.md` 自称"通过" | "虚假声明" | **改写为 v0.1.0-docs 状态报告** | 改名 + 加 MOA 评审 trace 附录 |

---

## 1. 真源 (Single Source of Truth)

后续所有文档 / test / plan / review **必须**用以下真源：

| 信息类别 | 真源 | 备注 |
|---------|------|------|
| 表结构 (DML) | `alembic/versions/0001_initial.py` | 唯一 |
| SQLAlchemy 模型 | `src/memos_graph/db/models.py` | 跟 alembic 对齐 |
| 端点 URL | `src/memos_graph/api/*.py` 的 `@router.X("...")` | 单一来源 |
| CLI 命令 | `src/memos_graph/cli.py` 的 `@main.command()` | 单一来源 |
| Config schema | `src/memos_graph/config.py` 的 Pydantic Settings class | 单一来源 |
| 默认值 | `pyproject.toml` 的 `[project]` 字段 | 版本、依赖 |
| 行为契约 | **本 SPEC v0.1.0** | 一切矛盾的最终裁决 |

---

## 2. 概念模型（v0.1 唯一）

### 2.1 核心实体（11 张表：9 实体 + 2 向量）

> **alembic/versions/0001_initial.py 实装确认**：
> - 实体表（9）：chunks / entities / entity_edges / agent_state / events / promises / user_profile / packs / tool_logs
> - 向量表（2）：chunk_vectors / event_vectors
> - **关系表（junction，不算 11）**：chunk_edges / chunk_entities

```
Agent ←───owns───→ Pack
  │
  ├───has_state──→ agent_state (1:1)
  │
  ├───writes──→ chunks (1:N)
  │              └───embeds──→ chunk_vectors (1:1)
  │              └───edges──→ chunk_edges (N:N)
  │              └───entities──→ chunk_entities (N:N)
  │                                └──→ entities (1:1)
  │                                    └──edges──→ entity_edges (N:N)
  │
  ├───emits──→ events (1:N)
  │              └───embeds──→ event_vectors (1:1)
  │
  ├───makes──→ promises (1:N)
  │
  └───logs──→ tool_logs (1:N)

User (cross-agent, 1 user)
  └───has_profile──→ user_profile (1:1, scope=global)
```

### 2.2 关键不变量 (Invariants)

- `chunks.agent_id` 必填
- `chunks.scope` ∈ {private, shared, global}
- `chunk_vectors.dimension` 必须 = embedding config 的 dimension
- `agent_state.version` 用乐观锁（UPDATE ... WHERE version = N）
- `promises.status` ∈ {open, fulfilled, broken, expired}，状态机单向不可回退
- `events.payload` 必须含 `schema_version` 字段（v1 起）
- `packs.id` 唯一，全小写 kebab-case
- `entity_edges` 不允许 self-loop

---

## 3. API 契约（v0.1 端点清单）

> **跟 INITIAL_DRAFT §5 略有差异**：本 SPEC 把 33 → **25 个端点**（v0.1 砍掉 8 个 v2-only 端点）

### 3.1 必须实装的 25 端点

| # | Method | Path | 来源 | 状态 |
|---|--------|------|------|------|
| 1 | GET | `/api/v1/health` | INITIAL_DRAFT §5 | ✅ 已有 |
| 2 | GET | `/api/v1/health/ready` | INITIAL_DRAFT §5 | ✅ 已有 |
| 3 | POST | `/api/v1/memories` | INITIAL_DRAFT §5 | ✅ 已有 |
| 4 | GET | `/api/v1/memories/{id}` | INITIAL_DRAFT §5 | ✅ 已有 |
| 5 | PUT | `/api/v1/memories/{id}` | INITIAL_DRAFT §5 | ✅ 已有 |
| 6 | DELETE | `/api/v1/memories/{id}` | INITIAL_DRAFT §5 | ✅ 已有 |
| 7 | POST | `/api/v1/memories/search` | INITIAL_DRAFT §5 | ✅ 已有（**5 阶段 recall 待实装**）|
| 8 | POST | `/api/v1/graph/expand` | INITIAL_DRAFT §5 | ✅ 已有（**graph 扩散待实装**）|
| 9 | GET | `/api/v1/graph/entity/{name}` | INITIAL_DRAFT §5 | ✅ 已有 |
| 10 | GET | `/api/v1/agents/{id}/state` | INITIAL_DRAFT §5 | ✅ 已有 |
| 11 | PUT | `/api/v1/agents/{id}/state` | INITIAL_DRAFT §5 | ✅ 已有（**乐观锁待修**）|
| 12 | POST | `/api/v1/agents/{id}/heartbeat` | INITIAL_DRAFT §5 | ✅ 已有（**手动触发可用**）|
| 13 | GET | `/api/v1/packs` | INITIAL_DRAFT §5 | ✅ 已有 |
| 14 | POST | `/api/v1/packs/install` | INITIAL_DRAFT §5 | ✅ 已有（**实装待补**）|
| 15 | POST | `/api/v1/events` | INITIAL_DRAFT §5 | ✅ 已有 |
| 16 | GET | `/api/v1/events` | INITIAL_DRAFT §5 | ✅ 已有 |
| 17 | POST | `/api/v1/promises` | INITIAL_DRAFT §5 | ✅ 已有 |
| 18 | GET | `/api/v1/promises` | INITIAL_DRAFT §5 | ✅ 已有 |
| 19 | PUT | `/api/v1/promises/{id}` | INITIAL_DRAFT §5 | ✅ 已有 |
| 20 | GET | `/api/v1/users/{id}/profile` | INITIAL_DRAFT §5 | ✅ 已有 |
| 21 | PUT | `/api/v1/users/{id}/profile` | INITIAL_DRAFT §5 | ✅ 已有 |
| 22 | POST | `/api/v1/tools/log` | INITIAL_DRAFT §5 | ✅ 已有 |
| 23 | GET | `/api/v1/tools/stats` | INITIAL_DRAFT §5 | ✅ 已有 |
| 24 | GET | `/api/v1/skills/{name}` | INITIAL_DRAFT §5 | ✅ 已有 |
| 25 | POST | `/api/v1/skills` | INITIAL_DRAFT §5 | ✅ 已有 |
| 25 | POST | `/api/v1/migrate/nako` | INITIAL_DRAFT §5 | ✅ 已有 |
|     | POST | `/api/v1/migrate/memos-local` | INITIAL_DRAFT §5 | ✅ 已有 |

### 3.2 砍掉的 6 个 v0.1 不实装端点

| # | 砍掉的 | 原因 |
|---|--------|------|
| - | `POST /api/v1/migrate/damxin` | v0.1 无需求 |
| - | `PUT /api/v1/users/{id}/merge` | v0.2 启用 |
| - | `POST /api/v1/events/search` | 复用 /api/v1/memories/search |
| - | `GET /api/v1/tasks/{id}` | v0.1 tasks 模块整体不做 |
| - | `POST /api/v1/tasks` | 同上 |
| - | `POST /api/v1/packs/{id}/update` | v0.1 用 install 覆盖式更新 |
| - | `POST /api/v1/packs/{id}/uninstall` | v0.1 不提供卸载 |
| - | `POST /api/v1/packs/{id}/run` | v0.1 pack run 走 CLI |

**实际**：33 → 25 个端点（DELETE 2 个，RENAME 6 个到 CLI）

---

## 4. CLI 契约（v0.1 命令清单）

### 4.1 17 个命令（INITIAL_DRAFT §6）+ 修正

INITIAL_DRAFT §6 列了 17 个，**v0.1 实装 12 个，缺 5 个**：

| 命令 | INITIAL_DRAFT 状态 | **SPEC 裁决** |
|------|--------------------|---------------|
| `memos-graph init` | 已有 | 保留 |
| `memos-graph migrate` | 已有 | 保留 |
| `memos-graph serve` | 已有 | 保留 |
| `memos-graph install-systemd` | 已有 | 保留 |
| `memos-graph pack install` | 已有 | 保留（**实现待补**）|
| `memos-graph pack list` | 已有 | 保留 |
| `memos-graph pack info` | 已有 | 保留 |
| `memos-graph pack update` | 已有 | 保留 |
| `memos-graph pack uninstall` | 已有 | 保留 |
| `memos-graph pack run` | 已有 | 保留（**实现待补**）|
| `memos-graph viewer` | 已有 | 保留（**UI 待补**）|
| `memos-graph backup` | 已有 | 保留 |
| `memos-graph doctor` | 缺 | **v0.1 必做** |
| `memos-graph config` | 缺 | **v0.1 必做**（show/edit 子命令）|
| `memos-graph export` | 缺 | v0.2 推迟 |
| `memos-graph import` | 缺 | v0.2 推迟 |
| `memos-graph session` | 缺 | v0.2 推迟 |
| `memos-graph recall-debug` | 缺 | **v0.1 必做**（5 阶段 recall 的调试命令）|

**v0.1 实装 = 14 个**（12 已有 + doctor + config + recall-debug）

---

## 5. 关键 bug 修复清单（S1 MOA 评审发现）

### 5.1 P0-bug

| Bug | 文件 | 行号待定 | 修复方案 |
|-----|------|---------|---------|
| `get_session` 非协程却用 `async with` | `db/session.py` | 待定位 | 改成 `async def get_session()` + `@asynccontextmanager` |
| Alembic 同步调阻塞事件循环 | `db/migrations.py` | 待定位 | 用 `alembic.command.upgrade` 异步封装 |
| `/memories/search` 退化为 `ILIKE` | `api/memories.py` | 待定位 | 接入真 RecallEngine |
| 5 阶段 recall 完全没实装 | `recall/__init__.py` | N/A | 整模块实装 |
| 心跳调度器完全没实装 | `heartbeat/__init__.py` | N/A | 整模块实装 |
| Pack 模块完全没实装 | `pack/__init__.py` | N/A | 整模块实装 |
| Embedding 完全没实装 | `embedding/__init__.py` | N/A | 整模块实装 |
| Viewer "Full UI coming soon" 占位 | `viewer/server.py` | 待定位 | 实装 3 页面 Jinja2 模板 |

### 5.2 P1-bug

| Bug | 文件 | 修复方案 |
|-----|------|---------|
| `config.py` 硬编码 URL | `config.py` | env 覆盖 |
| `llm/client.py` 无 HMAC 签名 | `llm/client.py` | v0.1 **不实装 HMAC**（走 Bearer token）|
| 测试用 SQLite 不支持 pgvector | `tests/test_memories.py` | 改用 testcontainers 真 PG |

---

## 6. 性能与可观测性（v0.1 必出）

### 6.1 性能预算

| 操作 | 目标 | 实装方法 |
|------|------|---------|
| `/memories/search` 5 阶段 | P50 < 300ms, P99 < 1s | 5 阶段并行 + HNSW |
| `/memories` POST | < 50ms | 不算 embedding |
| `/agents/{id}/state` GET | < 10ms | 主键查询 |
| `/health/ready` | < 100ms | 单条 SELECT 1 |

### 6.2 必出 metric

- `memos_graph_recall_stage_duration_seconds{stage="fts|vector|rrf|mmr|graph"}` histogram
- `memos_graph_recall_total{result="hit|miss"}` counter
- `memos_graph_chunks_total{agent_id, scope}` gauge
- `memos_graph_embedding_duration_seconds{model}` histogram
- `memos_graph_heartbeat_dispatched_total{agent_id, stage}` counter
- `memos_graph_http_requests_total{method, path, status}` counter

**实装方式**：prometheus_client + `/metrics` 端点

---

## 7. 安全 & 配置（v0.1）

- **绑定 127.0.0.1**，不开 0.0.0.0
- **.env 文件**放 `~/.hermes/.env` 或 `~/.config/memos-graph/.env`，权限 600
- **密码**（PG / API key）必须从 env 读，**严禁**写代码
- **SQL 注入**：全部走 SQLAlchemy 参数化，**严禁** `text(f"... {user_input} ...")`
- **API 不做鉴权**（localhost only），但**加 CORS 关闭**
- **依赖**：固定主版本（`fastapi>=0.109,<0.110`）

---

## 8. 版本与升级

- v0.1.0-docs = 当前文档阶段（**不发包**）
- v0.1.0 = 第一实装可发布版（**待实装**）
- v0.2 = LLM 抽取 + 多 channel
- v1.0 = HA + 性能基准 + 监控告警

---

## 9. 与现有项目（memos-local-plugin）的关系

- **不同进程、不同 DB schema**
- **同一台机器**部署时：memos-local 用 5433，memos-graph 用 5432（或反过来）
- **同一 port 8765** 会被 memos-local 占用 → memos-graph 用 8766
- **数据迁移**：`memos-graph pack install --migrate-from=memos-local` 把 memos-local 的 chunks 导入到 memos-graph

---

## 10. SPEC 修订历史

| 版本 | 日期 | 改动 | 评审 |
|------|------|------|------|
| v0.1.0 | 2026-07-02 | 初版 | MOA 2026-07-02 评审待跑 |
| v0.2.0 | (本文件) | 钉死 0.1/0.2 范围，6 端点砍到 25，14 CLI | — |

---

**状态**：✅ SPEC 钉死，等待 MOA 评审 → 进入 TDD test spec 阶段
