# memos-graph 初稿（Pre-Implementation Brief）

> **状态**：v0.1 完整版（可实施）— 已基于 35B 无限调用额度更新
>
> **来源**：基于 `DESIGN.md` v2.0（memos-graph + MetaPact/Nako 综合设计）的子集 + 实施前必须先定的事
>
> **目的**：把综合方案里"含糊的"部分在动手前钉死
>
> **重要前提**：有 35B 模型无限次调用额度 → **所有 LLM 抽取/生成都可以自动跑**，不需要"手动触发"或"关闭"

---

## 0. TL;DR — 三句话

1. **memos-graph** 是一个 PostgreSQL 后端的**长期记忆 + agent 状态引擎**，独立 runtime（FastAPI daemon），跟 Nako / 任何 Agent Pack 解耦
2. **MetaPact/Nako** 是一个**伴侣型 Agent Pack**（人设 + 五官技能 + 心跳），把它的"记忆子系统"指向 memos-graph
3. **不做**：不重写 OpenClaw / 不做新的 Agent runtime / 不碰 cc-connect / 不取代飞书客户端

---

## 1. 范围（In / Out）

### ✅ In scope（v0.1 要做的）

| 模块 | 内容 |
|------|------|
| **DB 层** | PostgreSQL + pgvector，6 张新表 schema（agent_state / events / promises / user_profile / packs / relationships）+ v1 的 chunks/vectors/graph 表 |
| **API 层** | FastAPI daemon，CRUD + search + graph 扩散 + 状态/事件/承诺读写 |
| **记忆后端** | chunks 写入 + 5 阶段 recall（FTS / 向量 / RRF / MMR / 图谱扩散） |
| **状态管理** | agent_state 读/写/版本化（乐观锁） |
| **事件流** | events 写入 + 基础查询（按时间/类型/agent 过滤） |
| **Pack 协议** | pack.yaml schema + loader + installer + registry（先有 1 个 pack：Nako） |
| **心跳调度** | scheduler 每分钟检查 + 阈值触发 + 单 channel 投递（先支持飞书） |
| **Viewer** | 状态面板 + 时间线 + 承诺看板（极简版） |
| **迁移** | Nako 旧 session 文件 → chunks（一次性工具） |
| **嵌入** | Ollama nomic-embed-text（本地）作为默认，mxbai-embed-large 可选 |

### ❌ Out of scope（v0.1 不做）

- 不重写 Nako 的五张人设文件（IDENTITY / SOUL / HEARTBEAT / MEMORY / USER），**原样保留**在 pack 内
- 不实现 Apache AGE / cypher（v1 那条"v2 升级"路径先挂着）
- 不做 Pack 的第三方市场（先自用 1 个 pack）
- 不做多模态 embedding（图片/音频不向量化，只用元数据 + LLM 摘要）
- 不做 web 端的"和 Nako 聊天"界面（仍走飞书）
- ~~不做"自动从对话抽取实体/关系"的 LLM 流程（v0.1 实体抽取先**手动触发**或**关掉**）~~ → ✅ **35B 无限调用，自动抽取**
- ~~不做"心跳消息内容由 LLM 生成"（v0.1 先**模板化**，从 HEARTBEAT.md 选预设段）~~ → ✅ **35B 无限调用，LLM 生成**
- 不做分布式 / 多节点 / HA
- 不做 SSO / 多租户 / RBAC
- 不做客户端 SDK（先只用 REST + JSON-RPC）
- 不做 OpenAPI 文档站点（Swagger UI 自带就行）

---

## 2. 第一刀切哪里（v0.1.0 MVP 范围）

按"价值/风险"排序，**第一个 PR 只做 P0**，P1/P2 排队：

### P0 — 必做（不做不能发布）

| 任务 | 产出 | 验收 |
|------|------|------|
| **P0.1** PostgreSQL schema 全量迁移（v1 + v2 新表） | `alembic/versions/0001_initial.py` 一次到位 | `memos-graph migrate` 后 `\dt` 能看到所有表 |
| **P0.2** FastAPI daemon 启动 + `/health` | `memos-graph serve --port 8765` | `curl /health` 返回 200 |
| **P0.3** chunks 基础 CRUD（POST/GET/PUT/DELETE `/api/v1/memories`） | REST 端点 | 用 curl 写/读/改/删一个 chunk |
| **P0.4** chunks 向量写入 + FTS 触发器 | `POST /api/v1/memories` 时自动 embed + tsvector | 写一段中文，能用 SQL 查到 FTS 结果 |
| **P0.5** 5 阶段 recall（FTS + 向量 + RRF + MMR + 图谱扩散） | `POST /api/v1/memories/search` | 写 10 条 chunk，查询"X" 能 top-5 命中相关 |
| **P0.6** agent_state CRUD + 乐观锁 | `GET/PUT /api/v1/agents/:id/state` | 并发更新不丢更新（version 递增） |
| **P0.7** events 写入 + 基础查询 | `POST /api/v1/events` + `GET /api/v1/events` | 能写入"mood_change"事件并按时间排序查回 |
| **P0.8** pack.yaml schema + loader | `memos-graph pack install <path>` | 装 Nako 成功后 `pack list` 能看到 |
| **P0.9** Nako 迁移工具（session 文件 → chunks） | `memos-graph pack install ./nako --migrate-sessions` | 装完能用 `search` 搜到 Nako 历史对话 |
| **P0.10** heartbeat 调度器（模板化） | daemon 启动后每分钟跑一次 | Nako 离线 48h 后能在飞书收到心跳消息 |
| **P0.11** Viewer 极简版（3 页面：状态/时间线/承诺） | `memos-graph viewer --port 8080` | 浏览器打开能看到 Nako 的 agent_state |
| **P0.12** 安装 / 升级 / 启动三件套 + systemd unit 生成 | `install.sh` + `memos-graph install-systemd` | 在干净 Debian 上跑 install.sh 能起服务 |

### P1 — 排队（v0.2 候选）

- ~~promises 表的自动 LLM 抽取（v0.1 手动写）~~ → ✅ **35B 无限调用，v0.1 自动抽取**
- ~~relationships 表的写入（v0.1 不需要）~~ → ✅ **35B 无限调用，v0.1 自动构建**
- ~~user_profile 合并工具（v0.1 先单写）~~ → ✅ **35B 无限调用，v0.1 自动合并**
- ~~entity_edges 自动构建（v0.1 图谱只靠手动添加的 chunk_edges）~~ → ✅ **35B 无限调用，v0.1 自动构建**
- ~~心跳 LLM 生成（v0.1 用 HEARTBEAT.md 模板）~~ → ✅ **35B 无限调用，v0.1 LLM 生成**
- 飞书以外的 channel 投递（v0.1 仅飞书）
- 多 pack 同时跑（v0.1 只支持 1 pack，但 schema 留好位）

### P2 — 远期

- Apache AGE 升级
- 多模态 embedding
- ~~LLM 自动实体/关系抽取~~ → ✅ **已移到 v0.1**
- Pack 市场
- HA / 分布式
- 客户端 SDK（TypeScript / Python / Go）
- OpenAPI 文档站

---

## 3. 技术决策（钉死，不留模糊）

### 3.1 包管理 / 工具链

| 决策 | 选 | 备注 |
|------|-----|------|
| Python 版本 | **3.11+** | Debian 13 默认就是 3.11/3.13 |
| 包管理 | **uv** | 比 pip 快 10x，`uv tool install memos-graph` |
| 异步运行时 | **asyncio + asyncpg** | 不用同步 SQLAlchemy session |
| ORM | **SQLAlchemy 2.0（async）** | 跟 asyncpg 配套 |
| 迁移 | **Alembic** | SQLAlchemy 官方 |
| HTTP 框架 | **FastAPI** | 自带 OpenAPI / Swagger UI |
| 嵌入 HTTP 客户端 | **httpx** | async 友好 |
| Pydantic | **v2** | 性能好 |

### 3.2 存储

| 决策 | 选 | 备注 |
|------|-----|------|
| 主库 | **PostgreSQL 15+** | ltree + pgvector 都需要 ≥15 |
| 向量索引 | **HNSW** | pgvector 0.5+ 默认，召回率 > 95% |
| 嵌入维度 | **1024**（mxbai-embed-large） | 跟 v1 一致 |
| 嵌入默认 provider | **Ollama**（本地） | `nomic-embed-text` 备选 |
| FTS | **PostgreSQL tsvector + GIN** | 中文用 `simple` 分词即可（CJK 退化用 pattern 兜底） |
| 缓存层 | **不引入 Redis**（v0.1） | pgvector HNSW 已经够快 |
| 时序数据归档 | **不实现**（v0.1） | events 表不超过 10w 行时无压力 |

### 3.3 API 风格

| 决策 | 选 | 备注 |
|------|-----|------|
| 对外协议 | **REST + JSON-RPC 双轨** | REST 给运维 / Viewer；JSON-RPC 给 Hermes plugin |
| 路径前缀 | `/api/v1/` | 留出 `/api/v2/` |
| 错误格式 | `{"error": {"code": "...", "message": "..."}}` | RFC 7807 不沿用 |
| 鉴权 | **v0.1 不做**（localhost only） | 部署在 NAS 时用 SSH 隧道，不开公网 |
| CORS | 关闭 | daemon 只服务本机 / 内网 |

### 3.4 心跳（更新版：35B 无限调用）

| 决策 | 选 | 备注 |
|------|-----|------|
| 调度方式 | **asyncio task，daemon 内部** | 不依赖 cron |
| 触发条件 | `now() - last_interaction > threshold[stage]` | threshold 从 pack.yaml 读 |
| 消息内容 | **LLM 生成**（35B 无限调用） | 根据 agent_state + 历史 5 条 events 生成个性化内容 |
| 时区 | 读 user_profile.attributes.timezone | 默认 Asia/Shanghai |
| 静默时段 | 23:00-08:00 不发 | 配在 pack.yaml |
| 重试 | 失败 3 次后放弃 + 写 events | 不死循环 |

### 3.5 Pack 协议

| 决策 | 选 | 备注 |
|------|-----|------|
| 安装路径 | `~/.local/share/memos-graph/packs/<id>/` | 跟 XDG 规范 |
| 安装方式 | **复制整个目录**（非软链） | 升级可保护文件 |
| 保留文件 | `pack.yaml.preserve_on_upgrade` 列表 | 默认：custom.md / MEMORY.md / memory/ / .env.agent |
| 注册时机 | `install` 时写 `packs` 表一行 | uninstall 时删 |
| 启动入口 | `pack.yaml.runtime` 字段 | openclaw / hermes / claude-code 之一 |
| 启动参数 | `memos-graph pack run <id>` 透传给 runtime | 比如 `openclaw --workspace ~/.local/share/memos-graph/packs/nako/agent` |

### 3.6 嵌入

| 决策 | 选 | 备注 |
|------|-----|------|
| 默认 | **Ollama + nomic-embed-text**（768 维） | 快，50ms/查询 |
| 高质量 | **Ollama + mxbai-embed-large**（1024 维） | schema 留 1024 |
| 云端备选 | **OpenAI text-embedding-3-small**（config 可切） | API key 在 env |
| 缓存 | **SQLite**（`~/.local/share/memos-graph/embeddings.db`） | 用 hash(content) 当 key |

### 3.7 LLM 调用（新增：35B 无限调用）

| 决策 | 选 | 备注 |
|------|-----|------|
| LLM provider | **35B 无限调用** | 环境变量 `ANTHROPIC_BASE_URL` + `ANTHROPIC_API_KEY` |
| 实体/关系抽取 | **每条对话后自动** | 与 chunk 写入并行跑，输出到 `entities` + `entity_edges` |
| 承诺抽取 | **每条对话后自动** | 检测"答应/保证/一定"等言语行为，输出到 `promises` 表 |
| 事件摘要 | **每条对话后自动** | 生成 `events.summary` + 结构化 `payload` |
| 心跳生成 | **心跳触发时** | 根据 agent_state + 历史 5 条 events 生成个性化消息 |
| 画像合并 | **手动/定时** | 多源 attributes 去重/融合 |
| 查询扩展 | **检索时** | 扩展用户查询，提高召回率 |

### 3.8 35B 调用成本估算

| 调用点 | 触发时机 | 预估 tokens/次 | 备注 |
|--------|---------|---------------|------|
| 实体/关系抽取 | 每条对话后 | ~500 | 输入对话 + 输出实体列表 + 关系边 |
| 承诺抽取 | 每条对话后 | ~300 | 输入对话 + 输出 promises 候选 |
| 事件摘要 | 每条对话后 | ~200 | 输入对话 + 输出 summary |
| 心跳生成 | 心跳触发时 | ~400 | 输入 state + 历史，输出消息 |
| 画像合并 | 手动/定时 | ~600 | 多源 attributes 融合 |
| 查询扩展 | 检索时 | ~150 | 输入查询，输出扩展列表 |

**无限调用 = 可以每条对话后都跑完整 pipeline**，不需要"手动触发"或"关闭"。

---

## 4. 目录结构（确定版）

```
memos-graph/
├── pyproject.toml
├── README.md
├── DESIGN.md                       # v2 完整设计
├── INITIAL_DRAFT.md                # 本文件
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 0001_initial.py         # 一次到位：v1 + v2 全表
├── src/memos_graph/
│   ├── __init__.py
│   ├── __main__.py                 # `python -m memos_graph`
│   ├── cli.py                      # Click CLI：init/migrate/serve/...
│   ├── config.py                   # Pydantic Settings
│   ├── server.py                   # FastAPI app
│   ├── llm/                        # 新增：35B 无限调用模块
│   │   ├── __init__.py
│   │   ├── client.py               # 35B API 客户端
│   │   ├── prompts/                # 各种 prompt 模板
│   │   │   ├── entity_extract.py
│   │   │   ├── promise_extract.py
│   │   │   ├── event_summarize.py
│   │   │   ├── heartbeat_generate.py
│   │   │   ├── profile_merge.py
│   │   │   └── query_expand.py
│   │   └── parsers/                # 抽取结果解析 + 验证
│   │       ├── entity_parser.py
│   │       ├── promise_parser.py
│   │       └── ...
│   ├── db/
│   │   ├── __init__.py
│   │   ├── models.py               # SQLAlchemy 全部模型
│   │   ├── session.py              # async engine + sessionmaker
│   │   └── migrations.py           # alembic 包装
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── chunks.py
│   │   ├── vectors.py
│   │   ├── graph.py
│   │   ├── fts.py
│   │   ├── state.py
│   │   ├── events.py
│   │   ├── promises.py
│   │   ├── user_profile.py
│   │   └── packs.py
│   ├── embedding/
│   │   ├── __init__.py
│   │   ├── base.py                 # Embedder 抽象类
│   │   ├── ollama.py
│   │   ├── openai.py
│   │   └── cache.py                # SQLite embedding 缓存
│   ├── recall/
│   │   ├── __init__.py
│   │   ├── engine.py               # 5 阶段主控
│   │   ├── rrf.py
│   │   ├── mmr.py
│   │   ├── graph_diffusion.py
│   │   └── recency.py
│   ├── context_engine/
│   │   ├── __init__.py
│   │   └── injector.py             # 拼 system prompt
│   ├── pack/
│   │   ├── __init__.py
│   │   ├── loader.py               # 解析 pack.yaml
│   │   ├── installer.py            # install/update/uninstall
│   │   ├── registry.py             # 查 packs 表
│   │   └── runner.py               # run → 启动 runtime
│   ├── heartbeat/
│   │   ├── __init__.py
│   │   ├── scheduler.py
│   │   ├── rules.py
│   │   └── deliver.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── memories.py
│   │   ├── graph.py
│   │   ├── tasks.py
│   │   ├── skills.py
│   │   ├── tools.py
│   │   ├── migrate.py
│   │   ├── packs.py
│   │   ├── agents.py
│   │   ├── events.py
│   │   ├── promises.py
│   │   ├── users.py
│   │   └── health.py
│   ├── hermes_plugin/
│   │   ├── __init__.py
│   │   └── tools.py                # 暴露给 Hermes 的 JSON-RPC
│   └── viewer/
│       ├── __init__.py
│       ├── server.py               # 独立进程，端口 8080
│       └── templates/              # Jinja2
├── packs/                          # 官方 pack 目录
│   └── nako/                       # MetaPact clone 后改造
│       ├── pack.yaml
│       ├── agent/
│       ├── skills/
│       └── install.sh
├── tests/
│   ├── conftest.py                 # testcontainers 起 PG
│   ├── test_recall.py
│   ├── test_graph.py
│   ├── test_pack.py
│   ├── test_heartbeat.py
│   ├── test_events.py
│   └── test_migrate_nako.py
├── scripts/
│   ├── install.sh                  # 裸部署安装
│   ├── uninstall.sh
│   └── backup.sh                   # pg_dump + 上传
└── systemd/
    └── memos-graph.service         # unit 文件模板
```

---

## 5. 端点清单（v0.1 必出）

| 类别 | 端点 | 方法 | 用途 |
|------|------|------|------|
| 健康 | `/api/v1/health` | GET | 探活 |
| 健康 | `/api/v1/health/ready` | GET | PG 连通 + Ollama 可达 |
| 记忆 | `/api/v1/memories` | POST | 写 chunk |
| 记忆 | `/api/v1/memories/:id` | GET | 读 |
| 记忆 | `/api/v1/memories/:id` | PUT | 改 |
| 记忆 | `/api/v1/memories/:id` | DELETE | 删 |
| 记忆 | `/api/v1/memories/search` | POST | 5 阶段 recall |
| 图谱 | `/api/v1/graph/expand` | POST | 节点扩散 |
| 图谱 | `/api/v1/graph/entity/:name` | GET | 实体查 |
| 任务 | `/api/v1/tasks` | POST | 写任务摘要 |
| 任务 | `/api/v1/tasks/:id` | GET | 读 |
| 技能 | `/api/v1/skills` | POST | 写 |
| 技能 | `/api/v1/skills/:name` | GET | 读 |
| 工具 | `/api/v1/tools/log` | POST | 写调用日志 |
| 工具 | `/api/v1/tools/stats` | GET | 用量统计 |
| **Agent 状态** | `/api/v1/agents/:id/state` | GET | 读 |
| **Agent 状态** | `/api/v1/agents/:id/state` | PUT | 改（带 version） |
| **Agent 状态** | `/api/v1/agents/:id/heartbeat` | POST | 手动触发心跳 |
| **Pack** | `/api/v1/packs` | GET | 列出已装 pack |
| **Pack** | `/api/v1/packs/install` | POST | 安装（接受 git URL 或 path） |
| **Pack** | `/api/v1/packs/:id/update` | POST | 升级 |
| **Pack** | `/api/v1/packs/:id/uninstall` | POST | 卸载 |
| **Pack** | `/api/v1/packs/:id/run` | POST | 启动（spawn runtime） |
| **事件** | `/api/v1/events` | POST | 写 |
| **事件** | `/api/v1/events` | GET | 查（带过滤） |
| **事件** | `/api/v1/events/search` | POST | 向量检索 |
| **承诺** | `/api/v1/promises` | POST | 建 |
| **承诺** | `/api/v1/promises` | GET | 查（agent/status） |
| **承诺** | `/api/v1/promises/:id` | PUT | 标记完成/失败 |
| **用户** | `/api/v1/users/:id/profile` | GET | 查画像 |
| **用户** | `/api/v1/users/:id/profile` | PUT | 改 |
| **迁移** | `/api/v1/migrate/nako` | POST | 一次性迁移 Nako 旧数据 |
| **迁移** | `/api/v1/migrate/memos-local` | POST | 官方 plugin 旧数据 |

加粗为 v2 新增。

---

## 6. CLI 清单（v0.1 必出）

```bash
memos-graph init              # 生成 ~/.config/memos-graph/config.yaml
memos-graph migrate           # 跑 alembic 迁移
memos-graph serve --port 8765            # 前台
memos-graph serve --port 8765 --daemon   # 后台
memos-graph install-systemd   # 写 /etc/systemd/system/memos-graph.service
memos-graph pack install <path>          # 装 pack
memos-graph pack install --from-git <url> # 装 pack（git clone）
memos-graph pack list
memos-graph pack info <id>
memos-graph pack update <id>
memos-graph pack uninstall <id>
memos-graph pack run <id>      # 启动 pack（spawn runtime）
memos-graph pack stop <id>     # 停
memos-graph viewer --port 8080            # 起 Viewer
memos-graph backup             # 触发 pg_dump
memos-graph doctor             # 诊断（PG 通？Ollama 通？端口占用？）
memos-graph version
```

---

## 7. 关键文件 schema（钉死版）

### 7.1 `pack.yaml`

```yaml
id: nako                          # 唯一 ID（kebab-case）
name: 野木奈子 Nako
version: 0.3.0
runtime: openclaw
description: 战斗女仆型 AI 伴侣
author: gato
license: MIT
homepage: https://github.com/Lovappen/MetaPact

memos_graph:
  required: true
  pack_agent_id: nako
  shared_user_id: default
  default_scope: shared

heartbeat:
  enabled: true
  schedule_seconds: 1800          # 30 分钟检查一次（写死秒数，方便 daemon 调度）
  thresholds:
    stage_1_hours: 48
    stage_2_hours: 24
    stage_3_hours: 12
    stage_4_hours: 8
    stage_5_hours: 6
  quiet_hours: "23:00-08:00"
  template: agent/HEARTBEAT.md
  state_file: memory/heartbeat-state.json  # 兼容 Nako 旧文件名（仅迁移用）

skills:
  - voice
  - vision
  - hearing
  - selfie
  - dokidoki
  - memory
    memory:
      backend: memos_graph
      endpoint: http://localhost:8765
      auto_inject: true
      auto_extract: false          # v0.1 关闭，v0.2 开启

preserve_on_upgrade:
  - agent/custom.md
  - agent/MEMORY.md
  - memory/
  - .env.agent
  - config/*.local.yaml
```

### 7.2 `~/.config/memos-graph/config.yaml`

```yaml
server:
  host: 127.0.0.1
  port: 8765

database:
  url: postgresql+asyncpg://memos:memos@localhost:5432/memos
  pool_size: 10
  pool_recycle: 3600

embedding:
  provider: ollama                # ollama | openai
  model: nomic-embed-text
  dimension: 768                  # 跟 model 匹配
  base_url: http://localhost:11434
  cache_db: ~/.local/share/memos-graph/embeddings.db
  timeout_seconds: 30

viewer:
  enabled: true
  host: 127.0.0.1
  port: 8080

backup:
  schedule: "0 3 * * *"            # 每天 3 点
  output_dir: ~/.local/share/memos-graph/backups
  retention_days: 30

logging:
  level: INFO
  format: json                    # json | console
  file: ~/.local/share/memos-graph/logs/daemon.log
  rotation: "10 MB"
```

### 7.3 嵌入 model 与 dimension 对照表

| provider | model | dimension |
|----------|-------|-----------|
| ollama | nomic-embed-text | 768 |
| ollama | mxbai-embed-large | 1024 |
| ollama | all-minilm | 384 |
| openai | text-embedding-3-small | 1536 |
| openai | text-embedding-3-large | 3072 |

**注意**：换模型时 dimension 必须重建索引。CLI 加 `memos-graph migrate-reindex` 命令。

---

## 8. Nako 迁移策略（v0.1 必做）

### 8.1 数据源

| 来源 | 路径 | 格式 |
|------|------|------|
| Session 对话记录 | `~/.openclaw/agents/<id>/sessions/*.jsonl` | 每行一条 message |
| MEMORY.md | `agent/MEMORY.md` | Markdown 段落 |
| USER.md | `agent/USER.md` | Markdown 段落 |
| 心跳 state | `memory/heartbeat-state.json` | JSON |
| tool_logs | `skills/*/logs/skill.jsonl` | 每行一条 skill 调用 |

### 8.2 目标

| 来源 → 目标 | 转换规则 |
|-------------|---------|
| `sessions/*.jsonl` → `chunks` (scope=private, agent_id=nako) | 每条 message 一行，role=原 role |
| `MEMORY.md` 长期记忆段 → `user_profile.attributes` | 解析 `## 长期记忆` 下 bullet 列表 |
| `MEMORY.md` 短期记忆 5 条 → `events` (type=message) | type='message', summary=原文 |
| `MEMORY.md` 用户信息库 → `user_profile.attributes` | 解析 `## 用户个人信息库` 下 `- key: val` |
| `MEMORY.md` 重要标记 → `user_profile.attributes.flags` | 解析 `- [ ]` / `- [x]` |
| `USER.md` → `user_profile` 初始值 | 解析 known_info / relation_stage |
| `heartbeat-state.json` → `agent_state` | 字段映射：last_heartbeat, mood, affinity |
| `skill.jsonl` → `tool_logs` | 直接对应 |

### 8.3 迁移命令

```bash
memos-graph pack install ./packs/nako --migrate-sessions
# 选项：
#   --dry-run            模拟，不写库
#   --source <path>      指定 Nako 旧数据目录（默认 ~/.openclaw/agents/nako）
#   --scope shared|private  chunks scope（默认 private，主人可手动改 shared）
#   --skip-existing      跳过已存在的 chunk（按 hash 判重）
```

迁移完成后打印报告：
```
Migration report:
  sessions: 1234 messages → 1234 chunks (skip: 0)
  memory.md: 5 short-term + 12 long-term events created
  user_profile: 8 attributes set
  heartbeat_state: affinity=42, stage=2
  tool_logs: 567 records imported

Run `memos-graph pack run nako` to start.
```

---

## 9. 测试策略（v0.1 必做）

### 9.1 单元测试

- 5 阶段 recall：写 50 条 fixture chunk，验证 5 个阶段各自的 top-K 和合并后 top-K
- RRF / MMR / graph_diffusion：纯算法测试
- entity_extractor：v0.1 关掉，测 fixture 加载
- pack loader：测 pack.yaml 解析 / 验证 / 错误信息
- 状态乐观锁：并发更新测试

### 9.2 集成测试

- 用 `testcontainers-python` 起 PostgreSQL + pgvector
- HTTP API：每个端点 happy path + 至少 1 个 error case
- 心跳：模拟时间推进，验证触发条件
- Nako 迁移：拿真实 Nako fixtures 跑一遍

### 9.3 端到端（人工 + 脚本）

```bash
# 跑通这 5 步 = v0.1 完成
bash scripts/install.sh
memos-graph migrate
memos-graph pack install ./packs/nako --migrate-sessions
memos-graph pack run nako
# → 飞书收到一条 "nako 已就位" 通知
# → 在飞书跟 Nako 聊 3 句
# → 搜 "X" 能召回这 3 句
# → 离线 48h 后收到心跳消息
```

### 9.4 性能基准（v0.1 不做，留 v0.2）

- 10w chunks 下 search 延迟 < 200ms
- 写吞吐 > 100 chunks/s
- 心跳调度内存 < 100MB

---

## 10. 风险 / 坑（实施前要知道的）

| 风险 | 触发条件 | 缓解 |
|------|---------|------|
| **Ollama 在 Synology NAS 上不跑** | ARM / 旧 CPU | 改用 CPU 模式；或换 openai 嵌入 |
| **pgvector HNSW 内存爆** | 10w+ 高维向量 | `m=16, ef_construction=64` 起步；按需调 |
| **Alembic 异步迁移坑** | 同步 URL vs async URL 不匹配 | env.py 用 `connection.run_sync(do_migrations)` |
| **Nako 旧 session 格式版本不一** | 多次升级导致 schema 变 | 写 schema detector，多版本适配 |
| **heartbeat state 双写** | 旧文件 + 新库同时在 | 迁移时把文件内容入库，之后只写库；文件保留只读 |
| **pack 升级覆盖用户改的 IDENTITY** | 升级时默认覆盖 | 升级前问 `ID of file 'IDENTITY.md' changed locally, overwrite? [y/N]` |
| **飞书 channel ID 找不到** | pack.yaml 没配 | 启动前 doctor 检查 + 友好报错 |
| **HNSW 索引在低维度（768）下召回下降** | 短查询 | 配合 RRF + 多路召回兜底 |
| **asyncpg 跟 pgbouncer transaction mode 不兼容** | 部署用了 pgbouncer | 改用 session mode 或直连 |

---

## 11. v0.1 不做的清单（再强调一次）

- ✅ ~~LLM 抽取实体/关系/承诺（手动）~~ → **35B 无限调用，v0.1 自动跑**
- ✅ ~~心跳消息 LLM 生成（模板）~~ → **35B 无限调用，v0.1 自动跑**
- ❌ Apache AGE
- ❌ 多模态 embedding
- ❌ 多 channel（仅飞书）
- ❌ 分布式 / HA
- ❌ 鉴权（localhost only）
- ❌ 客户端 SDK
- ❌ OpenAPI 文档站
- ❌ 性能基准
- ❌ 多 pack 协作（schema 留位，逻辑只跑 1 pack）

---

## 12. 验收标准（v0.1 发布 = 以下全部 ✅）

- [ ] `bash scripts/install.sh` 在干净 Debian 13 上一次跑通
- [ ] `memos-graph serve` 启动后 `curl /health` 200
- [ ] `memos-graph migrate` 跑成功，所有表创建
- [ ] 写 100 条 chunk → 搜索召回 top-5 准确
- [ ] `memos-graph pack install ./packs/nako --migrate-sessions` 成功导入 Nako 旧数据
- [ ] `memos-graph pack run nako` 启动 Nako + 心跳调度
- [ ] 在飞书跟 Nako 聊 → 离线 48h → 收到心跳
- [ ] Viewer 极简版能看状态/时间线/承诺
- [ ] `memos-graph pack update nako` 不覆盖 custom.md
- [ ] `pytest -v` 100% 通过
- [ ] README 有完整使用文档

---

## 13. 后续版本预告（不在 v0.1 范围）

- **v0.2**：LLM 自动抽取实体/承诺、心跳 LLM 生成、relationships 表启用、Pack 协作
- **v0.3**：多 channel（微信/Discord/Telegram via cc-connect）、多模态 embedding
- **v0.4**：客户端 SDK（TypeScript / Python）、OpenAPI 文档站
- **v0.5**：Apache AGE 升级、cypher 查询
- **v1.0**：性能基准、HA、监控告警、正式发布

---

## 14. 待用户决策的开放问题（已回答）

- [x] **Ollama 还是云嵌入默认？** → Ollama 本地嵌入（nomic-embed-text 768 维），云端备选 OpenAI
- [x] **心跳消息是否 LLM 生成？** → 是，35B 无限调用，根据 agent_state + 历史生成
- [ ] **Viewer 用什么技术栈？** → FastAPI + Jinja2（v0.1 极简版）
- [ ] **pack 升级时 IDENTITY/SOUL 默认行为？** → 询问用户（保留/覆盖/跳过）
- [ ] **Nako 的 voice/vision/hearing skill 要不要进 v0.1？** → 不进（v0.2 再考虑）
- [ ] **第一台部署目标？** → 待决定（本机 kana / Synology NAS / VPS）

---

**状态**：✅ 设计文档已完善，35B 无限调用决策已纳入，开始 v0.1 实施
