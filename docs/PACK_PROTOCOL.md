# memos-graph Pack Protocol v0.1

> **目的**：Agent Pack 是 memos-graph 的"角色产品"载体（人设 + 技能 + 多模态）。本协议规范 pack 的目录结构、配置文件、安装/升级、运行机制。
> **关联**：DESIGN §3（Agent Pack 协议）/ SPEC §0.1 P0.9 / INITIAL_DRAFT §3.4 pack.yaml schema
> **目标读者**：pack 作者 / memos-graph 实施者
> **状态**：v0.1 设计文档（**不实装**，等 TASK_BREAKDOWN T11 实施）

---

## 0. Pack 是什么

**Agent Pack** = 角色 + 人设 + 技能 + 配置 + 启动器的**可分发单元**。一个 pack 包含：

- **人设层**：`agent/` 下的 SOUL/IDENTITY/HEARTBEAT/MEMORY/USER 文档
- **技能层**：`skills/` 下每个能力（如 voice、vision、heart）
- **配置层**：`config/` 下模型/provider 映射
- **启动器**：`scripts/` 下 init / heartbeat / memory-write 脚本
- **环境**：`.env.agent.example`
- **元数据**：`pack.yaml` 唯一清单

**不是 runtime**：memos-graph 本身不执行 agent 逻辑，它**加载 + 调度**。pack 跑在 OpenClaw / Hermes / ClaudeCode 上。

---

## 1. 标准目录结构

```
my-pack/
├── pack.yaml                    # 清单（必需）
├── README.md                    # 必读
├── LICENSE                      # 必带
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
│   ├── voice/
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   └── ...
│   ├── vision/
│   ├── hearing/
│   ├── selfie/
│   └── ...（自由扩展）
├── config/
│   ├── model-map.yaml           # 模型映射
│   └── providers-preset.json    # provider 预设
├── scripts/                     # 启动 / 初始化 / 心跳脚本
│   ├── start.sh
│   ├── heartbeat-check.sh
│   └── memory-write.sh
├── assets/                      # 头像 / 图标 / 资源文件
│   ├── avatar.png
│   └── icon.png
├── .env.agent.example           # Agent 私有环境变量模板
├── install.sh                   # 一键安装
└── uninstall.sh                 # 一键卸载
```

---

## 2. pack.yaml 完整 schema

### 2.1 顶层字段

```yaml
# 必填
id: nako                          # 唯一 ID（kebab-case，a-z0-9-）
name: 野木奈子 Nako                # 显示名（任意 Unicode）
version: 0.3.0                    # semver
runtime: openclaw                 # openclaw | hermes | claude-code

# 推荐
description: 战斗女仆型 AI 伴侣    # 1 句话
author: gato <gato@example.com>
license: MIT
homepage: https://github.com/foo/bar

# 可选
tags: [companion, anime, japanese]
icon: assets/icon.png              # 相对路径
screenshot: assets/screenshot.png  # 相对路径
```

### 2.2 memos_graph 集成

```yaml
memos_graph:
  # 必填：声明本 pack 依赖 memos-graph
  required: true                   # 是否必须

  # agent_id 在 memos-graph DB 里的标识
  pack_agent_id: nako              # 默认 = id

  # 跨 pack 共享的用户 ID
  shared_user_id: default          # 默认 'default'

  # 默认 scope
  default_scope: shared            # private | shared | global

  # 记忆后端配置
  memory:
    backend: memos_graph          # 唯一支持 v0.1
    endpoint: http://localhost:8765
    auto_inject: true             # 启动时自动塞长期记忆到 prompt
    auto_extract: false           # v0.1 强制 false（v0.2 启用 LLM 抽取）
```

### 2.3 心跳

```yaml
heartbeat:
  enabled: true
  schedule_seconds: 1800           # 30 分钟检查一次
  thresholds:                      # 触发主动消息的阈值
    stage_1_hours: 48             # 初识
    stage_2_hours: 24             # 熟人
    stage_3_hours: 12             # 朋友
    stage_4_hours: 8              # 亲密
    stage_5_hours: 6              # 永恒
  quiet_hours: "23:00-08:00"       # 不主动消息
  template: agent/HEARTBEAT.md    # 规则模板
  state_file: memory/heartbeat-state.json  # 兼容旧版本（迁移用）
```

### 2.4 技能

> **⚠️ MOA v0.1.0 评审：必须强制 object map，禁止 string shorthand**（歧义、YAML 解析报错）

```yaml
# ✅ 唯一合法格式：object map（key=skill name, value=配置）
skills:
  voice:
    description: 发语音 / 唱歌
    trigger: 用户要求语音回复时
    dependencies:
      - MINIMAX_API_KEY
    scripts:
      tts: scripts/voice.sh
      sing: scripts/sing.sh
    env:
      VOICE_DEFAULT_MINIMAX: female-tianmei
      VOICE_SPEED_DEFAULT: 1.0
    docs: skills/voice/SKILL.md

  vision:
    description: 看图
    trigger: 用户发图片时
    dependencies: []
    scripts:
      resolve: scripts/resolve.sh
    docs: skills/vision/SKILL.md

  hearing:
    description: 听语音
    trigger: 用户发语音时
    scripts:
      stt: scripts/stt.sh

  selfie:
    description: 自拍 / 图生视频
    dependencies:
      - FAL_KEY

  dokidoki:
    description: 蓝牙互动设备
    dependencies:
      - npm:@tryjoy/dokidoki

  # 特殊：声明使用 memos-graph 当记忆后端
  memory:
    backend: memos_graph
    endpoint: http://localhost:8765
    auto_inject: true
    auto_extract: false   # v0.1 强制 false
```

> **附 `docs/pack-yaml.schema.json`**（**MOA 评审要求**）—— JSON Schema 用于自动 lint pack.yaml

**字段约束**：
- 必填：`description`（1 句话）、`scripts`（至少 1 个可执行）
- 可选：`trigger` / `dependencies` / `env` / `docs`
- 特殊 skill：`memory.backend` 必须 = `memos_graph`（v0.1 唯一）

### 2.5 升级保护

```yaml
# 升级时绝不覆盖的文件（v0.1 强制 + 自由加）
preserve_on_upgrade:
  - agent/custom.md               # 用户扩展
  - agent/MEMORY.md               # 累积记忆
  - memory/                        # 心跳 state 等
  - .env.agent                     # 用户私有环境变量
  - config/*.local.yaml           # 用户私有配置
```

### 2.6 元信息（可选）

```yaml
# 兼容性
min_memos_graph_version: 0.1.0
max_memos_graph_version: 0.2.x

# 平台支持
platforms:
  - feishu
  - telegram
  - discord

# 通道配置（按平台）
feishu:
  app_id: ${FEISHU_APP_ID}
  app_secret: ${FEISHU_APP_SECRET}
```

---

## 3. 安装流程

### 3.1 安装命令

```bash
memos-graph pack install <source>
# source: 本地路径 / git URL / registry name
```

### 3.2 步骤

1. **下载 pack**
   - 本地路径：直接 copy
   - git URL：`git clone` 到临时目录
   - registry：HTTP GET tarball

2. **验证 pack.yaml**
   - 解析 YAML
   - 必填字段检查（id/name/version/runtime）
   - id kebab-case 验证
   - runtime ∈ {openclaw, hermes, claude-code}
   - **id 不与已装 pack 冲突**

3. **复制到 `~/.local/share/memos-graph/packs/<id>/`**
   - **保留源目录所有文件**
   - 跳过 `.git/`、临时文件

4. **保留文件处理**
   - 如已装 pack，检查 `preserve_on_upgrade` 列表
   - **不覆盖**已存在的保留文件
   - 输出"以下文件未覆盖（已保留）"列表

5. **写 packs 表**（**v0.1 强约束：仅支持 PostgreSQL**）
   > **⚠️ MOA v0.1.0 评审：v0.1 硬要求 PostgreSQL 15+**。不支持 SQLite（pgvector 依赖）。`ON CONFLICT DO NOTHING` 是 PG UPSERT 语法。
   ```sql
   -- PG 15+ only
   INSERT INTO packs (id, name, version, manifest, install_path, enabled)
   VALUES ('nako', '野木奈子 Nako', '0.3.0', '{...pack.yaml...}', '/home/gato/.local/share/memos-graph/packs/nako', TRUE)
   ON CONFLICT (id) DO UPDATE
   SET version = EXCLUDED.version, updated_at = now();
   ```

6. **初始化 agent_state**
   ```sql
   INSERT INTO agent_state (agent_id, pack_id, stage, affinity, mood, energy)
   VALUES ('nako', 'nako', 1, 0, 50, 50)
   ON CONFLICT (agent_id) DO NOTHING;
   ```

7. **创建初始 custom.md（如不存在）**
   - `agent/custom.md.example` → `agent/custom.md`（首次）

8. **写安装日志**
   - `~/.local/share/memos-graph/logs/pack-install.log`

### 3.3 选项

```bash
memos-graph pack install <source> [options]

  --dry-run                # 模拟，不实际安装
  --migrate-from=<name>    # 从 memos-local / 旧 memos 迁移数据
  --agent-id=<id>          # 覆盖默认 agent_id
  --scope=<scope>          # 覆盖默认 scope
  --skip-existing          # 跳过已存在的 chunk
  --force                  # 强制覆盖（包括保留文件，**危险**）
```

---

## 4. 升级流程

### 4.1 升级命令

```bash
memos-graph pack update <id>
memos-graph pack update --all  # 全部
```

### 4.2 步骤

1. **拉新版**（同 install 的下载逻辑）

2. **版本比较**
   - 解析新旧 `pack.yaml` 的 version
   - semver 校验：新版必须 ≥ 旧版（除非 `--force`）

3. **保留文件处理**
   - 对 `preserve_on_upgrade` 列表中每个文件：
     - **新版文件备份**到 `<file>.new.<timestamp>`
     - **旧版文件保留**（不覆盖）
   - 输出"以下文件被新版本提供但未覆盖"列表

4. **可覆盖文件更新**
   - `agent/IDENTITY.md` / `SOUL.md` / `HEARTBEAT.md` 等
   - **询问用户**是否覆盖（CLI 提供 `y/N` 交互）
   - 默认不覆盖

5. **写 packs 表（更新 version + updated_at）**
   ```sql
   UPDATE packs
   SET version = '0.3.1', updated_at = now()
   WHERE id = 'nako';
   ```

6. **重启关联 runtime**
   - 如果 pack 在跑（`packs.enabled=TRUE` + 进程存在），提示用户重启
   - 不自动重启（避免中断服务）

### 4.3 回滚升级

```bash
memos-graph pack update <id> --to-version=0.3.0
# 下载指定版本并按 upgrade 流程走
```

---

## 5. 运行流程

### 5.1 启动命令

```bash
memos-graph pack run <id> [options]

  --runtime=<rt>           # 覆盖 pack.yaml.runtime
  --no-heartbeat           # 不启动心跳调度
  --foreground             # 前台运行（debug）
  --agent-id=<id>          # 覆盖 agent_id
```

### 5.2 步骤

1. **校验 pack 已装**
   - 查 packs 表

2. **从 DB 加载 agent_state**
   ```sql
   SELECT * FROM agent_state WHERE agent_id = '<id>';
   ```

3. **注入到 prompt（auto_inject=true）**
   - SOUL.md + IDENTITY.md
   - **agent_state 快照**（"你现在阶段 2，心情 70，精力 60"）
   - user_profile（"主人喜欢甜食、讨厌香菜"）
   - open promises（"你答应过周末做蛋糕，还有 2 天到期"）
   - 最近 5 条 events 摘要

4. **启动 runtime**
   ```bash
   # openclaw 示例
   openclaw --workspace ~/.local/share/memos-graph/packs/nako/agent \
            --memos-graph-endpoint http://localhost:8765
   ```

5. **启动心跳调度（pack.yaml.heartbeat.enabled=true）**
   - asyncio task 跑在 memos-graph daemon 里
   - 30 分钟检查一次（schedule_seconds=1800）
   - 触发时按 pack.yaml.heartbeat.thresholds 判断

6. **graceful shutdown**
   - 收到 SIGTERM → 停 runtime → 写 events（status=stop）→ 停 heartbeat

### 5.3 状态机

```
[NOT_INSTALLED] ──install──> [INSTALLED] ──run──> [RUNNING] ──stop──> [INSTALLED]
                                │                                       │
                                └──update──> [INSTALLED (new version)] ─┘
                                │
                                └──uninstall──> [NOT_INSTALLED]
```

---

## 6. 保留文件机制

### 6.1 机制

`preserve_on_upgrade` 列表里的文件：

- **install 时**：如果目标已存在，**保留旧版**（不覆盖）
- **update 时**：如果目标已存在，**保留旧版** + 新版写到 `<file>.new.<timestamp>`
- **uninstall 时**：默认**保留**（用户手动删）

### 6.2 必保留（v0.1 强制）

不管 `preserve_on_upgrade` 写啥，**这些永远不覆盖**：

| 文件 | 理由 |
|------|------|
| `agent/custom.md` | 用户扩展层 |
| `agent/MEMORY.md` | 累积记忆 |
| `memory/heartbeat-state.json` | 心跳 state |
| `.env.agent` | 用户私有环境变量 |
| `~/.config/memos-graph/config.yaml` | 用户的 memos-graph 主配置（不在 pack 内但在 ~/.config） |

### 6.3 升级后清理

```bash
# 看哪些 .new 文件待处理
ls ~/.local/share/memos-graph/packs/nako/agent/*.new.*

# diff 看差异
diff agent/IDENTITY.md agent/IDENTITY.md.new.202607021130

# 决定：覆盖 or 保留
mv agent/IDENTITY.md.new.202607021130 agent/IDENTITY.md  # 覆盖
rm agent/IDENTITY.md.new.202607021130                    # 删
```

### 6.4 安全检查

升级时**强制要求**：

- [ ] `custom.md` 未被新版本删除（如删了，警告 + 备份）
- [ ] `MEMORY.md` 大小变化 < 50%（如大幅变小，警告）
- [ ] `.env.agent` 数量 ≥ 0（不能被删空）

---

## 7. 安全

### 7.1 pack 来源

| 来源 | 风险 | 措施 |
|------|------|------|
| 本地路径 | 低 | 直接装 |
| git URL | 中 | 验证 URL（不装未审计代码） |
| registry | 中 | 验证签名（v0.2 引入 GPG 签名） |

### 7.2 install.sh 不执行（v0.1 限制）

v0.1 **不执行** pack 自带的 `install.sh`（避免任意代码执行）。所有安装逻辑走 memos-graph 自己。

**v0.2 计划**：
- 提供 `--allow-run-install-script` 标志
- 沙箱执行（pyseccomp / firejail）
- 强制 GPG 签名

### 7.3 运行时脚本安全（**MOA 评审新增**）⚠️

> **风险**：v0.1 限制 install.sh 不够，**runtime `scripts/*.sh` 是更大攻击面**——pack author 可注入 `rm -rf` / 后门 / 凭据窃取

v0.1 防御：

| 措施 | 实现 |
|------|------|
| **脚本白名单路径** | pack 启动时只允许 `~/.local/share/memos-graph/packs/<id>/scripts/*` 下的脚本被 memos-graph 主动调 |
| **checksum 记录** | install 时算每个脚本的 SHA256，写入 packs 表 `manifest.checksums`，**用户可 `memos-graph pack verify <id>` 验证** |
| **用户确认 prompt** | `pack run` 时如脚本被首次运行，**显式问 y/N**（CI 模式 `--assume-no` 拒跑） |
| **不主动执行 scripts/** | memos-graph **只调 SKILL.md 里 `scripts:` 字段声明的脚本**，其他文件不调 |
| **不修改 PATH** | memos-graph 不把 pack scripts/ 加 PATH，runtime 看不到这些脚本 |

v0.2 计划：
- 强制 GPG 签名
- 沙箱（pyseccomp / firejail）
- 用户设置 `--trust-pack=<id>` 跳过 checksum 验证

**Pack author 守则**：
- `scripts/` 下脚本不超过 50KB（避免藏大段代码）
- 不在脚本里 `curl | sh`、不下载可执行文件
- 不在脚本里读 `~/.ssh/`、`~/.aws/`、`~/.config/memos-graph/`
- **任何 `.env.agent` 之外的密钥都不读**

### 7.4 权限

pack 跑在 memos-graph daemon 同一 user 下。**不提供** pack 提权机制。

### 7.5 网络

pack 启动的 runtime 默认 `127.0.0.1` bind。pack 不能 listen 0.0.0.0（除非 pack.yaml 显式声明 + 用户确认）。

---

## 8. 故障排查

### 8.1 安装失败

| 症状 | 原因 | 解决 |
|------|------|------|
| `pack.yaml not found` | 路径错 | 确认路径 |
| `id conflict` | 已装同 id pack | 先 uninstall |
| `runtime not supported` | runtime 不识别 | 升级 memos-graph |
| `schema_version mismatch` | 用的 memos-graph 太老 | 升级 memos-graph |
| `permission denied ~/.local/share/memos-graph/packs` | 权限错 | 修目录权限 |

### 8.2 运行失败

| 症状 | 原因 | 解决 |
|------|------|------|
| `agent_state not found` | 没初始化 | `memos-graph pack install --reinit` |
| `runtime not installed` | openclaw/hermes 没装 | 装 runtime |
| `port 8765 not reachable` | memos-graph 没启 | `memos-graph serve` |
| `heartbeat 0 dispatched` | 调度没启 | daemon 早期崩，查 logs |

### 8.3 升级失败

| 症状 | 原因 | 解决 |
|------|------|------|
| `version downgrade rejected` | 旧→新 | 加 `--force` |
| `preserve file write conflict` | 文件锁 | 看哪条 lock |
| `agent_state state corrupted` | DB 损坏 | 跑 `memos-graph pack repair` |

---

## 9. 示例：完整 Nako pack.yaml

```yaml
id: nako
name: 野木奈子 Nako
version: 0.3.0
runtime: openclaw
description: 战斗女仆型 AI 伴侣（元梦天使阵营）
author: Lovappen
license: MIT
homepage: https://github.com/Lovappen/MetaPact

memos_graph:
  required: true
  pack_agent_id: nako
  shared_user_id: default
  default_scope: shared
  memory:
    backend: memos_graph
    endpoint: http://localhost:8765
    auto_inject: true
    auto_extract: false

heartbeat:
  enabled: true
  schedule_seconds: 1800
  thresholds:
    stage_1_hours: 48
    stage_2_hours: 24
    stage_3_hours: 12
    stage_4_hours: 8
    stage_5_hours: 6
  quiet_hours: "23:00-08:00"
  template: agent/HEARTBEAT.md
  state_file: memory/heartbeat-state.json

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
      auto_extract: false

preserve_on_upgrade:
  - agent/custom.md
  - agent/MEMORY.md
  - memory/
  - .env.agent
  - config/*.local.yaml

min_memos_graph_version: 0.1.0
max_memos_graph_version: 0.2.x

platforms:
  - feishu
```

---

## 10. 与外部生态的接口

### 10.1 跟 MetaPact/Nako 关系

- MetaPact = **Nako Pack 的源**（GitHub `Lovappen/MetaPact`）
- memos-graph = **消费方**（不开发 Nako 本身）
- 路径：`memos-graph pack install https://github.com/Lovappen/MetaPact.git#nako`
- 升级：`memos-graph pack update nako`（git pull）

### 10.2 跟其他 Pack 框架

- **OpenClaw native pack**：本协议是 superset，兼容大部分字段
- **Claude Code agent**：memos-graph 包装为 `--pack=<id>` 启动参数
- **OpenCode opencode.config.json**：通过 plugin 适配

---

## 11. 实施细节（给 TASK_BREAKDOWN T11 用）

### 11.1 关键代码点

- `pack/loader.py`：YAML 解析 + 验证（PK-L-01..07 对应 TEST_SPEC）
- `pack/installer.py`：复制 + 保留文件处理 + DB 写入（PK-I-01..06）
- `pack/runner.py`：spawn runtime + 加载 agent_state + 启 heartbeat（PK-R-01..05）
- `pack/registry.py`：packs 表 CRUD（PK-REG-01..03）

### 11.2 数据迁移（pack 自带 → memos-graph）

- `agent/MEMORY.md` 长期记忆段 → `user_profile.attributes`
- `agent/MEMORY.md` 短期记忆 5 条 → `events` (type=message)
- `agent/USER.md` → `user_profile` 初始值
- `memory/heartbeat-state.json` → `agent_state` 字段
- `skills/*/logs/*.jsonl` → `tool_logs`

### 11.3 锁文件

```json
// ~/.local/share/memos-graph/packs/nako/.lock
{
  "version": "0.3.0",
  "installed_at": "2026-07-02T11:30:00Z",
  "checksum": "sha256:...",
  "preserved_files": ["agent/custom.md", ...]
}
```

---

**状态**：✅ Pack Protocol v0.1 钉死，等待 MOA 评审
