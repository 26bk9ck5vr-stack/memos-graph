# memos-graph 综合设计方案 v2.0

> **本文档综合** `memos-graph/DESIGN.md` v1（PostgreSQL + pgvector + 图谱记忆引擎） **+** `Lovappen/MetaPact`（野木奈子 AI 伴侣 Agent Pack）
>
> **核心立场：** memos-graph 不再只是"记忆插件"，升级为 **Agent 状态与长期记忆引擎**；MetaPact/Nako 作为第一个 **伴侣型 Agent Pack** 跑在上面，两个项目合并为一个产品方向。

---

## 0. 合并动机（为什么）

### 0.1 两个项目各自的定位

| 项目 | 类型 | 解决什么 | 缺什么 |
|------|------|---------|--------|
| **memos-graph v1** | 底层引擎 | 持久化、向量 + 图谱检索、多 agent 共享 | 没有"角色"、没有"情绪"、没有"主动心跳" |
| **MetaPact/Nako** | 上层 Agent Pack | 人设、对话、飞书接入、五官能力 | 记忆是 session 文件，**不跨会话**、**无图谱**、**多 agent 不共享** |

### 0.2 合并后解决的新问题

| 场景 | 单独用 v1 | 单独用 Nako | **合并后** |
|------|----------|------------|-----------|
| 跨 session 记得"用户上周说喜欢什么" | ✅ 但无角色 | ❌ 忘了 | ✅ **角色一致 + 真长期记忆** |
| 多个 agent 共享"用户是谁" | ✅ | ❌ | ✅ **shared scope** |
| "她答应过主人周末做蛋糕" | ❌ 没图谱 | ❌ | ✅ **实体边 elapsed_promise** |
| 好感度 / 心跳 / 主动消息 | ❌ | ✅ 但状态在文件里 | ✅ **状态进库 + 多 agent 可见** |
| 用户可视化"她记得关于我的一切" | ❌ | ❌ | ✅ **Viewer UI** |

### 0.3 关键决策（一行版）

> **memos-graph 升级为"agent_runtime"层** —— 记忆 + 状态 + 关系 + 技能调用日志的统一引擎；**Nako 是它上面的第一个角色产品**。

---

## 1. 新架构总览

```
┌────────────────────────────────────────────────────────────────────┐
│  Agent Pack 层（MetaPact 模式，可多个并存）                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  nako/ 战斗女仆   │  │  work-coder/    │  │  morning-bot/   │  │
│  │  SOUL/IDENTITY/  │  │  工程师型 agent │  │  晨间简报 agent │  │
│  │  HEARTBEAT/      │  │                 │  │                 │  │
│  │  custom.md       │  │                 │  │                 │  │
│  │  + skills/       │  │  + skills/      │  │  + skills/      │  │
│  │    voice|vision| │  │    shell|git|   │  │    rss|weather| │  │
│  │    hearing|selfie│  │    docker|...   │  │    cron|...     │  │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘  │
│           │   Hermes / OpenClaw / ClaudeCode runtime  │            │
│           └─────────────────┬──────────────────────────┘            │
│                             │ JSON-RPC / REST                       │
│  ┌──────────────────────────┴─────────────────────────────────────┐ │
│  │                memos-graph daemon (FastAPI)                    │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │ │
│  │  │  Recall  │  │  Ingest  │  │ Context  │  │  Heartbeat   │  │ │
│  │  │  Engine  │  │ Pipeline │  │ Injector │  │  Scheduler   │  │ │
│  │  │ (5阶段)  │  │          │  │          │  │ (NEW!)       │  │ │
│  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │ │
│  │       └──────────────┴────────────┴────────────────┘          │ │
│  │                          ↓                                    │ │
│  │              SQLAlchemy Storage Layer                         │ │
│  │       (chunks · vectors · graph · state · logs)              │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                ↓                                   │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  PostgreSQL 15 + pgvector + ltree                            │ │
│  │  chunks | chunk_vectors | chunk_edges | entities |           │ │
│  │  entity_edges | skills | task_summaries | tool_logs |        │ │
│  │  ★ agent_state | ★ relationships | ★ events   (NEW)         │ │
│  └──────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────┘
```

**三个新模块（v1 → v2）：**
1. **`agent_state` 表** — 持久化角色状态（好感度 / 心情 / 阶段 / 心跳时间戳）
2. **`heartbeat` 调度器** — 主动消息调度（替代 Nako 的 `cron nako-heartbeat`）
3. **Agent Pack 协议** — 标准目录结构 + 加载器，让 Nako 这种角色包即插即用

---

## 2. PostgreSQL Schema 升级

### 2.1 v1 已有表（全部保留）
`chunks` · `chunk_vectors` · `chunk_edges` · `entities` · `chunk_entities` · `entity_edges` · `skills` · `task_summaries` · `tool_logs`

### 2.2 v2 新增表

```sql
-- ============================================================
-- A. agent_state：每个 agent 的运行时状态
-- ============================================================
CREATE TABLE agent_state (
    agent_id        TEXT PRIMARY KEY,
    pack_id         TEXT NOT NULL,              -- 哪个 Agent Pack（nako/work-coder/...）
    stage           INT NOT NULL DEFAULT 1,     -- 关系阶段 1-5
    affinity        REAL NOT NULL DEFAULT 0,    -- 好感度 0-100
    mood            REAL NOT NULL DEFAULT 50,   -- 当前心情 0-100
    energy          REAL NOT NULL DEFAULT 50,   -- 能量 0-100
    last_interaction TIMESTAMPTZ,                -- 上次互动
    last_heartbeat  TIMESTAMPTZ,                 -- 上次主动心跳
    pending_heartbeat BOOLEAN DEFAULT FALSE,     -- 是否待发心跳
    state           JSONB DEFAULT '{}',          -- 自定义状态（key-value）
    version         INT NOT NULL DEFAULT 1,      -- 乐观锁
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_state_pack ON agent_state(pack_id);
CREATE INDEX idx_state_pending ON agent_state(pending_heartbeat) WHERE pending_heartbeat = TRUE;

-- ============================================================
-- B. relationships：用户 ↔ agent 的关系边
-- ============================================================
CREATE TABLE relationships (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    relation_type   TEXT NOT NULL,              -- 'master' / 'colleague' / 'friend' / 'spouse'
    strength        REAL NOT NULL DEFAULT 0,   -- 0-1
    since           TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB DEFAULT '{}',
    UNIQUE(agent_id, user_id, relation_type)
);

-- ============================================================
-- C. events：结构化事件流（对话 / 心跳 / 任务 / 状态变更）
-- ============================================================
CREATE TABLE events (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        TEXT NOT NULL,
    event_type      TEXT NOT NULL,              -- 'message' / 'heartbeat' / 'mood_change' | 'stage_up' | 'tool_call' | 'promise_made' | 'promise_fulfilled'
    actor           TEXT NOT NULL,              -- 'user' / 'agent' / 'system'
    payload         JSONB NOT NULL,             -- 事件体（结构化）
    summary         TEXT,                       -- LLM 生成的摘要（用于检索）
    related_chunk_id BIGINT REFERENCES chunks(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_events_agent_time ON events(agent_id, created_at DESC);
CREATE INDEX idx_events_type ON events(event_type, created_at DESC);
CREATE INDEX idx_events_payload_gin ON events USING GIN(payload jsonb_path_ops);

-- 事件抽取的嵌入（区别于 chunks，专门用于"近期事件"检索）
CREATE TABLE event_vectors (
    event_id        BIGINT PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
    embedding       vector(1024) NOT NULL,
    model           TEXT NOT NULL
);

-- ============================================================
-- D. promises：承诺追踪（"她答应过主人周末做蛋糕"）
-- ============================================================
CREATE TABLE promises (
    id              BIGSERIAL PRIMARY KEY,
    agent_id        TEXT NOT NULL,
    user_id         TEXT,
    content         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open',  -- 'open' / 'fulfilled' / 'broken' / 'expired'
    due_at          TIMESTAMPTZ,
    fulfilled_at    TIMESTAMPTZ,
    event_id        BIGINT REFERENCES events(id),  -- 哪条事件产生的承诺
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_promises_agent_status ON promises(agent_id, status);

-- ============================================================
-- E. user_profile：跨 agent 共享的用户知识（"这个人是谁"）
-- ============================================================
CREATE TABLE user_profile (
    user_id         TEXT PRIMARY KEY,
    display_name    TEXT,
    attributes      JSONB DEFAULT '{}',         -- {likes: [...], dislikes: [...], work: ...}
    updated_by      TEXT,                        -- 上次写入的 agent_id
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- F. packs：已注册的 Agent Pack 清单
-- ============================================================
CREATE TABLE packs (
    id              TEXT PRIMARY KEY,            -- 'nako' / 'work-coder' / 'morning-bot'
    name            TEXT NOT NULL,
    version         TEXT NOT NULL,
    manifest        JSONB NOT NULL,              -- pack.yaml 完整内容
    install_path    TEXT,                        -- 本地路径
    enabled         BOOLEAN DEFAULT TRUE,
    installed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 2.3 实体边扩展（v1 已有 entity_edges，加 relation 词汇）

Nako 类伴侣场景需要这些新边类型：

```sql
-- 在 v1 entity_edges 表上扩展 relation 词汇（无需改 schema）
-- 新增推荐词汇：
--   'promised_to'        承诺 → 用户/事件
--   'remembered_about'   chunk → 实体（加强实体共现）
--   'mood_triggered_by'  mood_change 事件 → chunk（什么让 agent 开心/难过）
--   'callback_to'        chunk → chunk（callback/伏笔关系）
--   'first_met'          实体 → 时间锚点
```

---

## 3. Agent Pack 协议（核心新概念）

### 3.1 什么是 Agent Pack

> **Agent Pack = 角色 + 人设 + 技能 + 配置 + 启动器** 的标准目录，可以被 memos-graph 注册、加载、调度。

**它不是另一个 runtime** —— 仍跑在 Hermes / OpenClaw / ClaudeCode 上；memos-graph 负责：
- 提供**记忆 + 状态**后端
- 提供**心跳调度**
- 提供**Pack 注册表**（哪个 pack 装在哪儿、版本、enabled）
- 提供**Pack → Agent 启动 hook**（`memos-graph pack run nako` → 启动 Nako agent 并把状态从库加载到 prompt）

### 3.2 标准目录结构

```
my-pack/
├── pack.yaml                    # 清单（必需）
├── agent/                       # 人设层
│   ├── IDENTITY.md              # 身份卡（YAML frontmatter + Markdown）
│   ├── SOUL.md                  # 性格 / 价值观
│   ├── HEARTBEAT.md             # 主动消息规则（阶段化）
│   ├── MEMORY.md                # 初始记忆模板
│   ├── USER.md                  # 用户档案模板
│   ├── TOOLS.md                 # 工具使用文档
│   ├── AGENTS.md                # 主 prompt 入口
│   └── custom.md.example        # 用户扩展层（升级不覆盖）
├── skills/                      # 技能（OpenClaw/Hermes 兼容）
│   ├── voice/SKILL.md
│   ├── vision/SKILL.md
│   └── ...
├── config/
│   ├── model-map.yaml           # 模型映射
│   └── providers-preset.json
├── scripts/                     # 启动 / 初始化 / 心跳脚本
│   ├── start.sh
│   ├── heartbeat-check.sh
│   └── memory-write.sh
├── .env.agent.example           # Agent 私有环境变量模板
├── install.sh                   # 一键安装（注册到 memos-graph）
└── README.md
```

### 3.3 `pack.yaml` schema

```yaml
# pack.yaml — Agent Pack 清单
id: nako                            # 唯一 ID
name: 野木奈子 Nako
version: 0.3.0
runtime: openclaw                   # openclaw | hermes | claude-code
description: 战斗女仆型 AI 伴侣
author: Lovappen
license: MIT

# 关联到 memos-graph
memos_graph:
  required: true                    # 必须有 memos-graph
  pack_agent_id: nako               # 在库里用这个 agent_id
  shared_user_id: default           # 用户 ID（跨 pack 共享）
  default_scope: shared             # 默认 chunk scope

# 心跳
heartbeat:
  enabled: true
  schedule: "*/30 * * * *"          # 每 30 分钟检查一次
  threshold:                        # 触发主动消息的阈值
    stage_1_hours: 48
    stage_2_hours: 24
    stage_3_hours: 12
    stage_4_hours: 8
    stage_5_hours: 6
  template: "agent/HEARTBEAT.md"   # 规则模板
  state_file: "memory/heartbeat-state.json"

# 技能清单
skills:
  - voice
  - vision
  - hearing
  - selfie
  - dokidoki
  - memory                          # ★ 必需：声明本包使用 memos-graph 当记忆后端
    memory:
      backend: memos_graph          # ★ 不再是 session 文件
      endpoint: http://localhost:8765
      auto_inject: true             # 启动时自动把长期记忆塞进 prompt
      auto_extract: true            # 对话后自动抽取记忆

# 升级保护
preserve_on_upgrade:
  - agent/custom.md
  - agent/MEMORY.md
  - memory/
  - .env.agent
```

### 3.4 Pack 安装 / 升级命令

```bash
# 安装（注册到 memos-graph）
memos-graph pack install ./nako
# → 检查 pack.yaml
# → 复制到 ~/.local/share/memos-graph/packs/nako/
# → 写入 packs 表
# → 初始化 agent_state 行
# → 把 custom.md.example 复制为 custom.md（如不存在）
# → 安装器保留：custom.md / memory/ / MEMORY.md / .env.agent

# 升级
memos-graph pack update nako
# → git pull 或下载新版本
# → **不覆盖** custom.md / MEMORY.md / memory/ / .env.agent
# → 提示是否覆盖 IDENTITY.md / SOUL.md / TOOLS.md（默认保留）

# 启动
memos-graph pack run nako
# → 从 DB 加载 agent_state（好感度 / 阶段 / 心情）
# → 注入 SOUL.md + IDENTITY.md + MEMORY.md 到 prompt
# → 调 Context Injector 自动塞入相关长期记忆
# → 启动底层 runtime（OpenClaw / Hermes）
# → 启动心跳调度器

# 列出
memos-graph pack list
# nako           0.3.0   enabled   agent_count=1
# work-coder     0.1.0   enabled   agent_count=2
# morning-bot    0.0.1   disabled  agent_count=1
```

---

## 4. 记忆 / 状态 / 心跳 三件套

### 4.1 写入路径

```
对话消息
  ↓
[1] skill-log.sh 触发：每次 skill 调用写 tool_logs
  ↓
[2] 对话结束钩子：memory-write.sh
  ├── 调 LLM 抽取实体 + 关系 → entity_edges
  ├── 调 LLM 抽取承诺 → promises 表
  ├── 调 LLM 生成摘要 → events.summary + chunk
  ├── 调 LLM 评估 mood/affinity 变化 → agent_state
  └── 调 LLM 检测 stage 升级 → agent_state.stage++
  ↓
[3] 全部进 PostgreSQL
```

### 4.2 读取路径（带状态注入）

```
新对话消息到来
  ↓
[1] Recall Engine 跑 5 阶段（v1 那套，FTS + 向量 + 图谱 + RRF + MMR + 扩散）
  ↓
[2] Context Injector 额外塞入：
  ├── agent_state 当前快照（"你现在阶段 2，心情 70，精力 60"）
  ├── user_profile（"主人喜欢甜食、讨厌香菜"）
  ├── open promises（"你答应过周末做蛋糕，还有 2 天到期"）
  └── 最近 5 条 events 摘要
  ↓
[3] 拼成 system prompt 发给 LLM
```

### 4.3 心跳调度器（替代 Nako 的 cron）

```python
# memos-graph/heartbeat/scheduler.py
class HeartbeatScheduler:
    """每分钟跑一次，对每个 enabled pack 检查是否要主动消息"""

    async def tick(self):
        for pack in self.enabled_packs():
            for agent in self.agents_of(pack):
                state = await self.load_state(agent)
                if self.should_heartbeat(state, pack.thresholds):
                    msg = await self.generate_message(agent, state, pack.HEARTBEAT)
                    await self.deliver(agent, msg)
                    await self.mark_heartbeat_sent(agent)
```

**HEARTBEAT 规则现在由 LLM 解析**（而非 Nako 那种硬编码 if/else）：

```python
async def should_heartbeat(self, state, thresholds):
    hours_since = (now() - state.last_interaction).hours
    threshold = thresholds[f"stage_{state.stage}_hours"]
    if hours_since < threshold:
        return False
    if not self.is_quiet_hours(state.user.timezone):
        return False
    return True
```

---

## 5. 与 Nako / MetaPact 的迁移路径

### 5.1 阶段一：兼容（不动 Nako）

- 装好 memos-graph daemon
- 在 Nako 的 `openclaw.json` 加一个 hook：对话结束调 `POST /api/v1/events`
- 验证事件能写进 `events` 表
- **Nako 自带的 session 文件继续用**，但每次启动从 memos-graph 拉快照

### 5.2 阶段二：替换记忆后端

- 把 Nako 的 `~/.openclaw/agents/<id>/sessions/` → 迁移到 `chunks`（scope=`private`, agent_id=`nako`）
- 把 `MEMORY.md` 解析成 `user_profile` 行
- 删 `memory-write.sh` 里的 session 文件写入逻辑，改成调 `memos-graph ingest`
- 验证：Nako 能在新对话里"记得"上次说的内容

### 5.3 阶段三：把 Nako 改造成"标准 Pack"

- 在 Nako 根目录加 `pack.yaml`
- 把 `agent/IDENTITY.md` 等文件加 YAML frontmatter（`name`, `vibe`, `stage`）
- 跑 `memos-graph pack install ./nako` —— 一键注册
- 跑 `memos-graph pack run nako` —— 替换原本的 `bash nako/install.sh` 启动

### 5.4 阶段四：跨 Pack 共享

- 工作 agent 也注册成 pack
- 让它写入 `scope=shared` 的 chunks（"主人今天做了 X 项目"）
- Nako 在合适场景能 recall 到工作 agent 写的事
- **前提：chunk scope 设计是 v1 已有功能，无需改**

---

## 6. API 扩展（v2 在 v1 基础上加）

### 6.1 新增端点

```
# Pack 管理
POST   /api/v1/packs/install
POST   /api/v1/packs/:id/update
GET    /api/v1/packs
POST   /api/v1/packs/:id/run

# Agent 状态
GET    /api/v1/agents/:id/state
PUT    /api/v1/agents/:id/state        # 更新 mood/affinity/...
POST   /api/v1/agents/:id/heartbeat    # 手动触发心跳

# 事件流
POST   /api/v1/events                  # 写事件
GET    /api/v1/events                  # 查询事件流（带过滤）
POST   /api/v1/events/search           # 事件级向量检索

# 承诺
POST   /api/v1/promises
GET    /api/v1/promises?agent_id=&status=
PUT    /api/v1/promises/:id            # 标记 fulfilled/broken

# 用户画像（跨 agent）
GET    /api/v1/users/:id/profile
PUT    /api/v1/users/:id/profile
POST   /api/v1/users/:id/merge         # 合并多源对同一用户的画像
```

### 6.2 现有 JSON-RPC 协议扩展

```python
# 新增 method
{"method": "agent_state_get",    "params": {"agent_id": "nako"}}
{"method": "agent_state_update", "params": {"agent_id": "nako", "mood": 75, "affinity": 82}}
{"method": "event_emit",         "params": {"agent_id": "nako", "type": "mood_change", "payload": {...}}}
{"method": "promise_create",     "params": {"agent_id": "nako", "content": "周末做蛋糕", "due_at": "..."}}
{"method": "heartbeat_tick",     "params": {"agent_id": "nako"}}
```

---

## 7. Viewer UI 升级

v1 的 viewer 加上：
- **状态面板** — 每个 agent 的好感度/阶段/心情趋势图
- **时间线** — `events` 流的瀑布流（对话/心跳/状态变更/承诺）
- **承诺看板** — open promises 列表，到期前 24h 高亮
- **关系图谱** — 实体边可视化（v1 已有基础上加 `promised_to`、`mood_triggered_by`）
- **Pack 管理** — 安装 / 升级 / 启停 pack

---

## 8. 部署与升级策略

**部署模型不变（v1 那种"裸部署"）：**

| 组件 | 形式 | 端口 |
|------|------|------|
| PostgreSQL + pgvector | apt/brew 装 | 5432 |
| memos-graph | pip 装 + systemd | 8765 |
| Agent Pack | `memos-graph pack install <git-url>` 装到 `~/.local/share/memos-graph/packs/` | — |
| 心跳调度 | memos-graph daemon 内置 | — |
| 备份 | `pg_dump` cron | — |

**升级路径（关键决策）：**
- **memos-graph 升级** → `pip install -U memos-graph` → 跑 `memos-graph migrate`（加新表）
- **Agent Pack 升级** → `memos-graph pack update nako` → **绝不覆盖** `custom.md` / `MEMORY.md` / `memory/` / `.env.agent`
- **数据迁移** → Nako 旧 session 文件用 `memos-graph migrate from-nako` 命令一次性导入

---

## 9. 项目结构

```
memos-graph/
├── pyproject.toml
├── README.md
├── DESIGN.md                       # 本文件
├── alembic/                        # DB 迁移（v1 + v2 新表）
├── src/memos_graph/
│   ├── server.py                   # FastAPI app
│   ├── config.py
│   ├── db/
│   │   ├── models.py               # SQLAlchemy 全部模型
│   │   ├── session.py
│   │   └── migrations.py
│   ├── storage/
│   │   ├── chunks.py
│   │   ├── graph.py
│   │   ├── vectors.py
│   │   ├── fts.py
│   │   ├── state.py                # NEW
│   │   ├── events.py               # NEW
│   │   ├── promises.py             # NEW
│   │   └── user_profile.py         # NEW
│   ├── embedding/
│   │   └── ...
│   ├── ingest/
│   │   ├── chunker.py
│   │   ├── entity_extractor.py
│   │   ├── graph_builder.py
│   │   ├── event_extractor.py      # NEW（事件抽取）
│   │   └── promise_extractor.py    # NEW（承诺抽取）
│   ├── recall/
│   │   └── ...                     # 5 阶段流水线（v1 那套）
│   ├── context_engine/
│   │   └── injector.py             # 升级：注入状态/事件/承诺
│   ├── pack/                       # NEW 整目录
│   │   ├── loader.py               # 解析 pack.yaml
│   │   ├── installer.py            # 安装 / 升级 / 保留规则
│   │   ├── registry.py             # 查 packs 表
│   │   └── runner.py               # pack run → 启动 runtime + 注入状态
│   ├── heartbeat/                  # NEW 整目录
│   │   ├── scheduler.py
│   │   ├── rules.py                # 解析 HEARTBEAT.md
│   │   └── deliver.py              # 走对应 channel
│   ├── api/
│   │   ├── memories.py             # v1
│   │   ├── graph.py                # v1
│   │   ├── tasks.py                # v1
│   │   ├── skills.py               # v1
│   │   ├── tools.py                # v1
│   │   ├── migrate.py              # v1
│   │   ├── packs.py                # NEW
│   │   ├── agents.py               # NEW
│   │   ├── events.py               # NEW
│   │   ├── promises.py             # NEW
│   │   └── users.py                # NEW
│   ├── hermes_plugin/
│   │   └── tools.py                # 暴露给 Hermes
│   └── viewer/
│       ├── server.py
│       └── templates/              # 升级
├── packs/                          # 官方 pack（git submodule 或独立发布）
│   └── nako/                       # ★ MetaPact 收纳进来
│       ├── pack.yaml
│       ├── agent/...
│       ├── skills/...
│       └── install.sh
└── tests/
    ├── test_recall.py
    ├── test_graph.py
    ├── test_pack.py                # NEW
    ├── test_heartbeat.py           # NEW
    ├── test_events.py              # NEW
    └── test_migrate_nako.py        # NEW（Nako 旧数据导入）
```

---

## 10. 关键决策表（v2 增量）

| 决策点 | 选项 | v2 选 | 理由 |
|--------|------|-------|------|
| Nako 记忆 | session 文件 vs memos-graph | **memos-graph** | 跨会话、图谱、共享 |
| 状态存储 | 文件 (heartbeat-state.json) vs DB | **DB (agent_state)** | 跨设备、版本化、查询 |
| 心跳调度 | 外部 cron vs daemon 内置 | **daemon 内置** | 统一管理、跨 pack |
| Pack 加载 | 软链接 vs 复制到 packs 目录 | **复制** | 升级可保护文件 |
| Nako 升级 | 覆盖全部 vs 白名单保留 | **白名单保留** | 跟 Nako 现状一致 |
| 嵌入维度 | 1024（mxbai） | **沿用 v1 1024** | 兼容老数据 |
| 关系图谱边类型 | v1 4 种 + Nako 4 种 | **v1 词表 + 新词表** | 不破坏 schema |
| 用户画像 | 每 agent 一份 vs 跨 agent 共享 | **共享（user_profile 表）** | Nako + 工作 agent 都要知道"主人是谁" |
| 承诺追踪 | 不支持 vs 表 | **promises 表** | Nako 场景强需求 |

---

## 11. 实施时间线（v2 增量，v1 6 周基础上 +）

| 周 | 任务 | 依赖 |
|----|------|------|
| W1-W6 | **v1 全量**（已规划） | — |
| W7 | Pack loader + installer + pack.yaml schema + packs 表 | W3 后可启动 |
| W8 | agent_state + relationships 表 + Context Injector 扩展 | W7 |
| W9 | events + event_extractor + 事件级向量检索 | W5 |
| W10 | heartbeat scheduler + rules 解析 + 多 channel 投递 | W8 |
| W11 | Nako 迁移工具 + 改造成标准 Pack | W7, W9, W10 |
| W12 | Viewer 状态/时间线/承诺面板 + 文档 + v2.0 发布 | 全部 |

---

## 12. 风险与对策

| 风险 | 影响 | 对策 |
|------|------|------|
| LLM 抽取实体/承诺失败率高 | 记忆噪声 | 双模型投票 + 人工抽样审核界面 |
| 心跳打扰用户 | 用户疲劳 | 严格遵守 quiet hours；阶段1 限制 1/天；学用户行为主动调整 |
| Nako 旧数据迁移破坏 | 丢记忆 | 迁移前双写、3 天观察期、可回滚 |
| Agent Pack 协议太死 | 第三方难扩展 | `manifest` 字段允许自定义 JSON |
| 事件流无限增长 | DB 膨胀 | 定期归档 `events WHERE created_at < now() - 90d` 到冷表 |

---

## 13. 一句话总览

> **memos-graph v2 = 通用 Agent 状态与长期记忆引擎（PostgreSQL + pgvector + 图谱 + 心跳），把 MetaPact/Nako 这种 Agent Pack 当成"上层角色应用"加载，记忆和状态全部入库，跨 agent 共享，可视化可调度。**

---

## 附录 A：Nako 当前文件 → memos-graph v2 映射

| Nako v0.3 文件 | v2 落点 | 备注 |
|----------------|---------|------|
| `agent/IDENTITY.md` | `packs.nako/agent/IDENTITY.md` + `agent_state.stage` | 文件保留作为 prompt 源，状态入库 |
| `agent/SOUL.md` | `packs.nako/agent/SOUL.md` | 保持文件（升级不覆盖） |
| `agent/HEARTBEAT.md` | `packs.nako/agent/HEARTBEAT.md` + `heartbeat/scheduler.py` | 规则文件 + daemon 解析 |
| `agent/MEMORY.md` | `user_profile` + `events.summary` | 结构化入库，文件保留作为 fallback |
| `agent/USER.md` | `user_profile` | 入库 |
| `agent/AGENTS.md` | `packs.nako/agent/AGENTS.md` | prompt 模板，运行时由 Context Injector 注入状态 |
| `agent/custom.md.example` | `packs.nako/agent/custom.md` | 用户层，升级永不覆盖 |
| `agent/TOOLS.md` | `packs.nako/agent/TOOLS.md` | 文档 |
| `skills/voice/...` | `packs.nako/skills/voice/` | 保留 |
| `skills/vision/...` | `packs.nako/skills/vision/` | 保留 |
| `skills/hearing/...` | `packs.nako/skills/hearing/` | 保留 |
| `skills/selfie/...` | `packs.nako/skills/selfie/` | 保留 |
| `skills/dokidoki/...` | `packs.nako/skills/dokidoki/` | 保留 |
| `skills/skill-log.sh` | → `tool_logs` 表 | 日志结构化入库 |
| `scripts/heartbeat-check.sh` | → `heartbeat/scheduler.py` | 逻辑迁到 daemon |
| `scripts/mood-recovery.sh` | → `agent_state` 更新接口 | 调 `PUT /api/v1/agents/:id/state` |
| `scripts/memory-write.sh` | → `POST /api/v1/events` + ingest pipeline | 自动 LLM 抽取 |
| `config/model-map.yaml` | `packs.nako/config/model-map.yaml` | 保留 |
| `config/providers-preset.json` | `packs.nako/config/providers-preset.json` | 保留 |
| `install.sh` | `memos-graph pack install ./nako` | 改写为 pack 安装逻辑 |
| `~/.openclaw/agents/<id>/sessions/` | `chunks` (scope=private) | 一次性迁移 |

## 附录 B：Nako 现有"伴侣特性"在 v2 怎么落地

| Nako 概念 | v2 实现 | 数据位置 |
|-----------|---------|---------|
| 好感度 | `agent_state.affinity` | DB |
| 关系阶段 | `agent_state.stage` | DB |
| 心情 | `agent_state.mood` | DB |
| 精力 | `agent_state.energy` | DB |
| 短期记忆（最近 5 条） | `events WHERE agent_id=... ORDER BY created_at DESC LIMIT 5` | DB |
| 长期记忆（关键事件） | `events WHERE type IN ('promise_fulfilled','milestone')` | DB |
| 思念机制 | `heartbeat/scheduler.py` + `agent_state.last_interaction` | DB + daemon |
| 主动消息阈值 | `pack.yaml.heartbeat.threshold` + HEARTBEAT.md | 配置 + 文件 |
| "她答应过 X" | `promises` 表 | DB |
| 用户信息库 | `user_profile.attributes` | DB |
| 重要标记 | `events.payload.flags` | DB |
| 心跳 state 文件 | 全部进 `agent_state` 表 | DB |
| custom.md | `packs/nako/agent/custom.md` | 文件，升级不覆盖 |
