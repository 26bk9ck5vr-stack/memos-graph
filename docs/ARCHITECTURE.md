# memos-graph v0.1.0 Architecture

> **目的**：一图 + 一文说清 memos-graph 整体架构
> **关联**：DESIGN.md（v2 设计）/ SPEC.md（v0.1 范围）/ TEST_SPEC.md / PACK_PROTOCOL.md / VIEWER_DESIGN.md / TASK_BREAKDOWN.md / MIGRATION_PLAN.md
> **读者**：实施者、贡献者、pack author

---

## 0. 一句话

> **memos-graph** = PostgreSQL 后端的**长期记忆 + Agent 状态引擎**。Agent Pack（Nako 等）跑在 OpenClaw / Hermes / ClaudeCode 上，memos-graph 提供**跨会话真记忆 + 心跳调度 + 状态查询**。

---

## 1. 系统全景图

```
┌─────────────────────────────────────────────────────────────────────┐
│                    用户/渠道层                                        │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐                │
│  │  飞书    │  │  Web    │  │  Cron   │  │  CLI    │                │
│  │  (pack) │  │  Viewer │  │  (job)  │  │  (ops)  │                │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘                │
│       │            │            │            │                       │
└───────┼────────────┼────────────┼────────────┼───────────────────────┘
        │            │            │            │
        │ HTTP       │ HTTP       │ direct     │ direct
        │            │            │            │
        ▼            ▼            ▼            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    memos-graph daemon (FastAPI)                       │
│                                                                          │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌────────────┐ │
│  │  REST API           │  │  Viewer (Jinja2)    │  │  Heartbeat │ │
│  │  25 端点            │  │  4 页面 + 静态       │  │  Scheduler │ │
│  │  (§ SPEC §3)        │  │  (VIEWER_DESIGN)    │  │  (asyncio) │ │
│  └──────────┬──────────┘  └──────────┬──────────┘  └──────┬─────┘ │
│             │                         │                      │          │
│             └─────────────────────────┴──────────────────────┘         │
│                               │                                          │
│  ┌────────────────────────────┴──────────────────────────────┐        │
│  │              Recall Engine (5 阶段)                          │        │
│  │  FTS → Vector → Pattern → Graph Seed → RRF → MMR → Diff  │        │
│  │  (recall/pipeline.py)                                       │        │
│  └────────────────────────────┬───────────────────────────────┘        │
│                               │                                          │
│  ┌────────────────────────────┴───────────────────────────────┐        │
│  │  Embedding Service (Ollama + SQLite cache)                    │        │
│  │  (embedding/)                                                 │        │
│  └────────────────────────────┬───────────────────────────────┘        │
│                               │                                          │
│  ┌────────────────────────────┴───────────────────────────────┐        │
│  │  Pack Manager (install / update / run)                       │        │
│  │  (pack/)                                                      │        │
│  └────────────────────────────┬───────────────────────────────┘        │
│                               │                                          │
│  ┌────────────────────────────┴───────────────────────────────┐        │
│  │  Context Engine (injector)                                    │        │
│  │  注入 agent_state + user_profile + open promises + recent    │        │
│  │  events 到 runtime prompt                                      │        │
│  └────────────────────────────┬───────────────────────────────┘        │
│                               │                                          │
│  ┌────────────────────────────┴───────────────────────────────┐        │
│  │  SQLAlchemy 2.0 (async) + Alembic                            │        │
│  │  (db/)                                                         │        │
│  └────────────────────────────┬───────────────────────────────┘        │
│                               │                                          │
└───────────────────────────────┼──────────────────────────────────────┘
                                │ asyncpg
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       PostgreSQL 15 + pgvector                            │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │  9 实体表 (chunks/entities/entity_edges/agent_state/events/   │        │
│  │  promises/user_profile/packs/tool_logs)                        │        │
│  │  2 向量表 (chunk_vectors/event_vectors)                       │        │
│  │  2 junction (chunk_edges/chunk_entities)                       │        │
│  └────────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
                                ▲
                                │ asyncpg
                                │
┌───────────────────────────────┼──────────────────────────────────────┐
│                    Ollama (localhost:11434)                              │
│  ┌────────────────────────────┴───────────────────────────────┐        │
│  │  nomic-embed-text (768 dim) / mxbai-embed-large (1024 dim)  │        │
│  └────────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    Agent Runtimes (外部进程)                              │
│  ┌────────────────────┐  ┌────────────────────┐                     │
│  │  OpenClaw          │  │  Hermes Agent      │                     │
│  │  (Nako 等伴侣)     │  │  (work-coder 等)   │                     │
│  │  spawn by pack     │  │  spawn by pack     │                     │
│  │  manager           │  │  manager           │                     │
│  └────────────────────┘  └────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 三层架构

### 2.1 存储层 (Storage Layer)

**PostgreSQL 15+ + pgvector** 是唯一数据源。11 张表 + 2 个向量表 + 2 个 junction。

**关键不变量**（SPEC §2.2）：
- `chunks.agent_id` 必填
- `chunks.scope` ∈ {private, shared, global}
- `agent_state.version` 乐观锁
- `promises.status` 状态机单向不回退
- `packs.id` kebab-case 唯一

### 2.2 引擎层 (Engine Layer)

5 个核心模块：

| 模块 | 文件 | 职责 |
|------|------|------|
| **Recall Engine** | `recall/pipeline.py` | 5 阶段检索 |
| **Embedding Service** | `embedding/` | 向量生成 + 缓存 |
| **Pack Manager** | `pack/manager.py` | pack install/run/upgrade |
| **Heartbeat Scheduler** | `heartbeat/scheduler.py` | 主动消息调度 |
| **Context Injector** | `context_engine/injector.py` | 注入 prompt |

### 2.3 接口层 (Interface Layer)

| 接口 | 协议 | 用途 |
|------|------|------|
| **REST API** | HTTP/JSON | 25 端点（pack、agent、event、memory、promise、user） |
| **JSON-RPC** | JSON-RPC 2.0 | Hermes plugin |
| **Viewer** | HTTP/HTML+Jinja2 | 4 页面 dashboard |
| **CLI** | Click | 17 命令（doctor / config / pack / recall-debug） |

---

## 3. 关键数据流

### 3.1 写 chunk（用户说话 → memos-graph）

```
[用户] → [飞书] → [OpenClaw (Nako runtime)] → POST /api/v1/memories
  ↓
[FastAPI handler] → [Chunk INSERT] → [auto-embed queue] → async
  ↓                                                  ↓
[Response 200]                              [Ollama embed]
  ↓                                                  ↓
[DB: chunks + chunk_vectors]                [DB: chunk_vectors 写入]
```

**关键**：embed 异步，不阻塞写响应。embed 失败时文本仍写（warn log）。

### 3.2 5 阶段 recall

```
[Query "MaaS 三个字母展开"] → POST /api/v1/memories/search
  ↓
[Stage 1: FTS]         → tsvector match       → top 50
[Stage 2: Vector]      → cosine similarity    → top 50
[Stage 3: Pattern]     → CJK fallback          → top 20
[Stage 4: Graph Seed]  → 1-hop 邻居           → top 20
  ↓
[RRF Fusion]           → 100 候选
  ↓
[MMR Re-rank]          → 30 去冗余
  ↓
[Graph Diffusion]      → +邻居×0.3 衰减
  ↓
[Time Decay + Scope Filter] → 10 候选
  ↓
[Response]
```

### 3.3 心跳调度

```
[daemon 启动] → [HeartbeatScheduler 启动 asyncio task]
  ↓
[每 30 分钟 tick] → [查所有 enabled pack 的 agent_state]
  ↓
[每 agent 判断]
  - now() - last_interaction > threshold[stage] ?
  - 不在 quiet_hours ?
  ↓
[触发] → 选 HEARTBEAT.md 模板 → 投递 (飞书 bot)
  ↓
[成功] → agent_state.last_heartbeat = now()
[失败 3 次] → 写 events 表，放弃
```

### 3.4 Pack 启动（注入上下文）

```
[CLI: memos-graph pack run nako] → [PackManager.run('nako')]
  ↓
[加载 pack.yaml] → [验证] → [DB 查 agent_state]
  ↓
[Context Injector 拼 system prompt]
  - SOUL.md + IDENTITY.md
  - agent_state 快照
  - user_profile
  - open promises (due_at 升序)
  - 最近 5 events 摘要
  ↓
[Spawn OpenClaw subprocess]
  ↓
[启动 heartbeat scheduler for this pack]
  ↓
[Daemon 继续接受 API 请求]
```

---

## 4. 跨进程边界

| 边界 | 协议 | 原因 |
|------|------|------|
| **memos-graph ↔ PG** | asyncpg | async/await 友好 |
| **memos-graph ↔ Ollama** | HTTP | Ollama 自带 HTTP API |
| **memos-graph ↔ OpenClaw/Hermes** | subprocess + JSON-RPC | runtime 独立进程崩溃不影响 daemon |
| **Viewer ↔ memos-graph** | HTTP（同源）| 防 XSS + 防直接改 state |
| **CC-connect ↔ Claude Code** | TCP/IPC | 飞书 ↔ Claude Code 桥 |

---

## 5. 部署拓扑

### 5.1 v0.1 单机模式

```
┌─────────── 1 台机器（localhost）───────────┐
│                                                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
│  │ memos-  │  │  PG 15  │  │ Ollama  │  │
│  │ graph   │  │ +vector │  │  768d   │  │
│  │ :8765   │  │ :5432   │  │ :11434  │  │
│  └─────────┘  └─────────┘  └─────────┘  │
│                                                │
│  ┌─────────┐  ┌─────────┐                  │
│  │ Viewer  │  │ OpenClaw│                  │
│  │ :8080   │  │ (spawn) │                  │
│  └─────────┘  └─────────┘                  │
│                                                │
│  ┌─────────┐                                  │
│  │ 飞书 bot│ (cc-connect :8766)             │
│  └─────────┘                                  │
│                                                │
└────────────────────────────────────────┘
```

**资源**：4 vCPU / 8GB RAM / 20GB SSD

### 5.2 与 memos-local-plugin 共存

> **MOA v0.1.0 评审：缺长期演化路径**

| 服务 | 端口 |
|------|------|
| memos-local daemon | 8765 |
| memos-graph daemon | **8766**（让开 8765）|
| memos-local viewer | 18800 |
| memos-graph viewer | 8080 / 8081 |
| PG memos-local | 5433 |
| PG memos-graph | 5432 |

**长期演化路径**（**MOA 评审要求明确**）：

| 阶段 | 时间 | 状态 |
|------|------|------|
| **Phase 1（当前）** | 2026 Q3 | 两套并存，**Nako 等伴侣 agent 跑 memos-local，工作 agent 跑 memos-graph** |
| **Phase 2** | 2026 Q4 | **Nako 切换到 memos-graph**（用 `memos-graph pack install MetaPact/nako`），memos-local 仅做兜底 |
| **Phase 3** | 2027 Q1 | memos-local 退役，**memos-graph 成为唯一 agent 引擎**。老 memos-local 数据通过 `memos-graph migrate from-memos-local` 导入 |
| **Phase 4** | 2027 Q2 | memos-local 仓库 archive |

**Phase 1 决策依据**：
- 两套 schema 完全不同（memos-local 是 SQLite，memos-graph 是 PG）
- 业务不冲突（Nako 陪伴 vs 工作 agent）
- 给 memos-graph 留 1-2 个季度验证稳定性

**何时加速 Phase 1→2**：
- memos-graph v0.1.0 发布 30 天后无 critical bug
- 至少 2 个 pack 跑通 `install + run + heartbeat`
- 飞书对话实测能跨 session recall

---

## 6. 启动顺序

> **⚠️ MOA v0.1.0 评审：§5.2 写 memos-graph 用 8766，§6 默认 8765 矛盾**

**默认端口**（无 memos-local 时）：8765  
**共存端口**（有 memos-local 时）：8766（`--port 8766`）

```bash
# === 单机模式（无 memos-local）===
sudo systemctl start postgresql
sudo systemctl start ollama
ollama pull nomic-embed-text
memos-graph serve --port 8765       # ← 默认端口

# === 共存模式（已有 memos-local 占 8765）===
memos-graph serve --port 8766       # ← 让开 8765

# 启动后（无论哪种模式）：
memos-graph pack install ./nako
memos-graph pack run nako
memos-graph viewer --port 8080      # viewer 不冲突
```

---

## 7. 数据生命周期

```
用户说话
  ↓
[chunks 表写入] (scope=private/shared)
  ↓
[chunk_vectors 异步 embed]
  ↓
[时间衰减] 7 天 × 0.7
  ↓
[图谱边自动构建] (v0.2 启用 LLM 抽取)
  ↓
[用户读取/recall 命中]
  ↓
[30 天未读] (v0.2 加归档)
  ↓
[180 天未读] (v0.2 加冷存)
  ↓
[events 表 90 天滚动归档]
  ↓
[promises 终态保留] (fulfilled/broken 永久)
```

---

## 8. 安全边界

| 边界 | 控制 |
|------|------|
| memos-graph ↔ PG | 强制 TLS（生产） / asyncpg 信任内网（开发） |
| memos-graph ↔ Ollama | localhost only（11434 绑定 127.0.0.1）|
| memos-graph daemon | bind 127.0.0.1（v0.1 禁 0.0.0.0）|
| Viewer | bind 127.0.0.1，POST 白名单 |
| Pack runtime | bind 127.0.0.1（pack.yaml 显式声明才能 0.0.0.0）|
| Pack install | 不执行 install.sh |
| Pack runtime scripts | checksum 验证 + 用户确认 |
| .env | chmod 600 |

**v0.1 不提供**：
- 鉴权 / RBAC
- HTTPS
- 速率限制
- 审计日志（v0.2）

---

## 9. 扩展点

| 想加什么 | 在哪加 |
|---------|--------|
| 新 LLM provider | `embedding/base.py` 子类 + `embedding/__init__.py` 注册 |
| 新 skill | pack 内的 `skills/<name>/SKILL.md` |
| 新 pack | 创建新 pack 目录 + 写 pack.yaml + `memos-graph pack install` |
| 新 channel | 改 `heartbeat/deliver.py` 加 channel handler |
| 新 recall 阶段 | `recall/pipeline.py` 改 `_run_references_parallel` |
| 新 metric | `recall/engine.py` 加 `memos_graph_*` counter/histogram |
| 新端点 | `api/<resource>.py` 加 router |

---

## 10. v0.1 范围外（明确不做）

| 不做 | 原因 | v0.2 计划 |
|------|------|----------|
| Apache AGE / cypher | v1 升级路径 | v0.4 |
| LLM 自动抽取实体/承诺 | scope freeze | v0.2 启用 |
| 多模态 embedding | 复杂度 | v0.3 |
| 多 channel (微信/Discord) | v0.1 只飞书 | v0.2 |
| HA / 分布式 | 单机版 | v0.5 |
| 鉴权 / RBAC | localhost only | v0.2 |
| Pack 第三方市场 | 自用 | v0.4 |
| 客户端 SDK (TypeScript/Python) | REST 够 | v0.3 |
| OpenAPI 文档站 | Swagger UI 自带 | v0.3 |

---

## 11. 测试架构（**MOA 评审新增**）

### 11.1 测试金字塔

```
            ╔═══════╗
            ║ E2E   ║   9 测试点（VIEWER + API + CLI）— T14
            ╠═══════╣
          ╔═══════════╗
          ║ 集成测试  ║   50+ 测试点（PK-I, REC-PIP, EMB-I, API-M）
          ╠═══════════╣
        ╔═══════════════╗
        ║   单元测试     ║   80+ 测试点（DB-M, REC-FTS, EMB-C, CLI-*）— embedded 进 T1-T13
        ╚═══════════════╝
```

### 11.2 fixture 策略

| 类型 | 实现 | 用法 |
|------|------|------|
| **mock** | `ollama_mock` (httpx) | 99% 测试，CI 友好 |
| **live** | `ollama_live` (testcontainers) | `[LIVE]` 标测试，nightly CI |
| **真 DB** | `pg_engine` (testcontainers PG 15+pgvector) | 100% 测试（**禁用 SQLite**）|
| **种子数据** | `seed_chunks` 参数化（100 / 10000）| 单元 vs 性能测试 |

### 11.3 CI 集成

```yaml
# .github/workflows/test.yml
- PR 触发: pytest -m "not perf and not live" 覆盖率 ≥ 85%
- main 触发: 同上 + ruff + pyright
- nightly: pytest 全跑（含 perf + live），perf 回归报警
```

### 11.4 性能基线

| 指标 | 基线 | 回归阈值 |
|------|------|---------|
| recall P50 | 142ms | > 200ms fail |
| recall P99 | 720ms | > 1.5s fail |
| embed P50 | 38ms | > 100ms fail |
| daemon 内存（10k chunks）| 320MB | > 1GB fail |

---

## 12. 文档地图

| 文档 | 用途 | 跟本文档关系 |
|------|------|------------|
| **DESIGN.md** | v2 完整设计（13 节） | 上游"是什么" |
| **INITIAL_DRAFT.md** | v0.1 开题（14 节） | 上游"第一刀" |
| **SPEC.md** | v0.1 范围钉死 | **本架构文档对齐 SPEC** |
| **TEST_SPEC.md** | TDD 测试契约 | 本架构对应 TEST_SPEC |
| **TASK_BREAKDOWN.md** | 任务拆解 | 本架构对应 TASK_BREAKDOWN |
| **MIGRATION_PLAN.md** | 部署/迁移 | 本架构对应 §5 部署拓扑 |
| **PACK_PROTOCOL.md** | Pack 协议 | 本架构对应 §3.4 Pack 启动 |
| **VIEWER_DESIGN.md** | Viewer 设计 | 本架构对应 §2 接口层 |
| **ARCHITECTURE.md** | 本文档 | **总入口** |

**真源规则**（SPEC §1）：
- 表结构 → alembic
- 端点 URL → api/*.py
- CLI 命令 → cli.py
- 配置 schema → config.py
- **行为契约 → SPEC.md**
- **架构总图 → 本文档**

---

**状态**：✅ Architecture v0.1 钉死 → Final Review 阶段
