# memos-graph v0.1.0 Migration Plan

> **目的**：v0.1.0 实装 → 部署 → 验证 → 监控的完整步骤。
> **目标读者**：devops / 实施工程师
> **关联**：SPEC §6 性能预算 / §7 安全 / §9 与 memos-local 关系

---

## 0. 部署目标

| 维度 | 单机模式 | 局域网模式 | 公网模式 |
|------|---------|-----------|---------|
| **机器** | 笔记本/NUC/NAS | 1 主 + N 客户端 | VPS |
| **PG** | localhost:5432 | 主机器 localhost | localhost（只本机）|
| **memos-graph** | localhost:8765 | 0.0.0.0:8765 | 0.0.0.0:8765 + nginx |
| **资源** | 2GB RAM / 5GB 磁盘 | 4GB RAM / 20GB 磁盘 | 8GB RAM / 50GB 磁盘 |
| **v0.1 支持** | ✅ | ✅ | ❌（v0.2 需 auth/TLS） |

**本文档只覆盖单机模式**（v0.1 必做）。局域网/公网留 v0.2。

---

## 1. 前置条件

### 1.1 硬件

- **CPU**：2 vCPU 起
- **RAM**：2 GB 起（10k chunks 后建议 4 GB）
- **磁盘**：SSD，20 GB 起步（PG data + Ollama 模型 + embedding 缓存）
- **网络**：拉模型/包时出网

### 1.2 操作系统

- **Linux**：Debian 12+ / Ubuntu 22.04+
- **macOS**：13+（仅 dev）
- **Windows**：WSL2（**不直接支持**）

### 1.3 软件

```bash
# PG 15+ + pgvector
sudo apt install postgresql-15 postgresql-15-pgvector

# Python 3.11+
sudo apt install python3.11 python3.11-venv python3-pip

# Ollama（本地 embedding）
curl -fsSL https://ollama.com/install.sh | sh
ollama pull nomic-embed-text  # 768 维，50ms/查询
ollama pull mxbai-embed-large  # 1024 维（备选）

# 其他工具
sudo apt install jq curl postgresql-client
```

### 1.4 网络

- **Ollama 端口**：11434（localhost）
- **PG 端口**：5432（localhost）
- **memos-graph 端口**：8765（localhost，**v0.1 严禁 0.0.0.0**）
- **不需公网**（单机模式）

---

## 2. 安装步骤

### 2.1 准备 PG 用户 + 数据库

> **⚠️ MOA v0.1.0 评审：`CREATE EXTENSION vector` 需要 superuser，memos 用户没权限**

```bash
# 1. 先以 postgres superuser 装扩展
sudo -u postgres psql -c "CREATE USER memos WITH PASSWORD 'CHANGE_ME';"
sudo -u postgres psql -c "CREATE DATABASE memos OWNER memos;"
sudo -u postgres psql -d memos -c "CREATE EXTENSION vector;"  # 必须在 superuser 下

# 2. 验证扩展
sudo -u postgres psql -d memos -c "SELECT extversion FROM pg_extension WHERE extname='vector';"
# 期望: 0.5.0 以上

# 3. 给 memos 用户 GRANT（防 schema 后续创建权限不足）
sudo -u postgres psql -d memos -c "GRANT ALL ON SCHEMA public TO memos;"

# 4. （可选）后续 alembic 跑迁移时用 memos 用户即可（schema 已建好）
```

### 2.2 安装 memos-graph

```bash
# 用 uv（推荐）
uv tool install memos-graph

# 或 pip
pip install memos-graph

# 验证
memos-graph --version  # 0.1.0
```

### 2.3 生成配置

```bash
memos-graph init
# 写 ~/.config/memos-graph/config.yaml
# 提示输入 PG password / embedding 选择
```

**生成的内容**（示例）：
```yaml
server:
  host: 127.0.0.1
  port: 8765
database:
  url: postgresql+asyncpg://memos:CHANGE_ME@localhost:5432/memos
  pool_size: 10
embedding:
  provider: ollama
  model: nomic-embed-text
  dimension: 768
  base_url: http://localhost:11434
viewer:
  enabled: true
  port: 8080
backup:
  schedule: "0 3 * * *"
  output_dir: ~/.local/share/memos-graph/backups
  retention_days: 30
logging:
  level: INFO
  format: json
  file: ~/.local/share/memos-graph/logs/daemon.log
```

**安全**：
```bash
chmod 600 ~/.config/memos-graph/config.yaml
chmod 700 ~/.local/share/memos-graph
```

### 2.4 跑迁移

```bash
memos-graph doctor
# 检查：PG 通？Ollama 通？端口占用？

memos-graph migrate
# 跑 alembic 0001_initial.py，建 11 张表 + 2 向量表 + 索引

# 验证
sudo -u postgres psql -d memos -c "\dt"
# 期望: 11 张表
```

### 2.5 启动 daemon

> **⚠️ MOA v0.1.0 评审：systemd 缺资源限制**

```bash
# 前台（debug）
memos-graph serve --port 8765 --verbose

# 后台
memos-graph serve --port 8765 --daemon

# systemd（推荐生产）
memos-graph install-systemd
```

**生成的 systemd unit（必须含以下资源限制）**：

```ini
# /etc/systemd/system/memos-graph.service
[Unit]
Description=MemOS-Graph Memory Daemon
After=postgresql.service ollama.service
Wants=ollama.service

[Service]
Type=simple
User=memos
ExecStart=/usr/local/bin/memos-graph serve --port 8765
Restart=on-failure
RestartSec=5

# === MOA 评审要求的资源限制 ===
LimitNOFILE=65536         # 防 connection exhaustion
MemoryMax=1G              # 软上限
MemoryHigh=2G             # 触发 swap 的告警
TasksMax=512              # asyncio 任务上限

Environment=DB_URL=postgresql+asyncpg://memos:***@localhost:5432/memos
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now memos-graph
sudo systemctl status memos-graph
# 验证资源限制生效: systemctl show memos-graph | grep -E "LimitNOFILE|MemoryMax"
```

### 2.6 验证健康

```bash
# Liveness
curl -s http://localhost:8765/api/v1/health
# {"status": "alive"}

# Readiness（必须等"ready"才能用）
curl -s http://localhost:8765/api/v1/health/ready
# {"status": "ready", "pg": "ok", "ollama": "ok", "dimension": 768}

# 写一条 chunk
curl -X POST http://localhost:8765/api/v1/memories \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"test","content":"hello world","scope":"private"}'
# 期望: {"id": 1, ...}

# 搜
curl -X POST http://localhost:8765/api/v1/memories/search \
  -H "Content-Type: application/json" \
  -d '{"query":"hello","agent_id":"test","max_results":5}'
# 期望: top-1 是 "hello world"
```

---

## 3. 升级路径（v0.1.0 → v0.1.1 → ...）

### 3.1 升级流程

```bash
# 1. 备份
memos-graph backup
# 写 ~/.local/share/memos-graph/backups/memos-YYYYMMDD-HHMMSS.sql.gz

# 2. 停服务
sudo systemctl stop memos-graph

# 3. 升级包
uv tool upgrade memos-graph
# 或 pip install -U memos-graph

# 4. 跑迁移（alembic 自动检测新版本）
memos-graph migrate

# 5. 启动
sudo systemctl start memos-graph

# 6. 验证
memos-graph doctor
curl -s http://localhost:8765/api/v1/health/ready
```

### 3.2 回滚（**MOA v0.1.0 评审：alembic downgrade 不可靠，改用 backup restore**）

```bash
# 1. 停服务
sudo systemctl stop memos-graph

# 2. 降级包到上一个工作版本
uv tool install memos-graph==0.1.0  # 手动指定

# 3. **不要跑 alembic downgrade**（schema drop column 后 downgrade 容易失败）
#    直接恢复最近一次 backup
ls -t ~/.local/share/memos-graph/backups/memos-*.sql.gz | head -1
LATEST=$(ls -t ~/.local/share/memos-graph/backups/memos-*.sql.gz | head -1)
gunzip -c "$LATEST" | psql -U memos memos

# 4. 验证 HNSW 索引还在（restore 可能不保留 index，**MOA 提示**）
sudo -u postgres psql -d memos -c "\d+ chunk_vectors"
# 如果 idx_vectors_hnsw 缺失：
sudo -u postgres psql -d memos -c "REINDEX INDEX idx_vectors_hnsw;"

# 5. 启动
sudo systemctl start memos-graph

# 6. 验证
memos-graph doctor
curl -s http://localhost:8765/api/v1/health/ready
```

> **policy**：v0.1.x 之间回滚用 backup restore（不跑 alembic downgrade）
> **policy**：跨大版本（v0.1 → v0.0）不允许直接降级，要 fresh install + 数据迁移

### 3.3 不兼容升级的破坏性策略

v0.x → v0.y（如 v0.1 → v0.2 启用 LLM 抽取）：

```bash
# 1. 备份（强制）
memos-graph backup --force

# 2. 跑迁移脚本
memos-graph migrate --breaking-changes-ack

# 3. 数据迁移
memos-graph migrate data-ml-extract
# 把已有 chunks 用 LLM 抽实体/关系

# 4. 验证
memos-graph doctor --strict
```

---

## 4. 备份与恢复

### 4.1 自动备份（cron）

`/etc/cron.d/memos-graph-backup`:
```
0 3 * * * gato /usr/local/bin/memos-graph backup >> /var/log/memos-graph/backup.log 2>&1
```

**backup 命令做**：
- `pg_dump -U memos memos | gzip > ~/.local/share/memos-graph/backups/memos-$(date +%F-%H%M).sql.gz`
- 保留 30 天（按 config.retention_days）
- 老备份自动清理

### 4.2 手动备份

```bash
memos-graph backup
# 2026-07-02 11:30:00 wrote ~/.local/share/memos-graph/backups/memos-2026-07-02-113000.sql.gz (8.4 MB)
```

### 4.3 恢复

```bash
# 1. 停服务
sudo systemctl stop memos-graph

# 2. 恢复
gunzip -c ~/.local/share/memos-graph/backups/memos-2026-07-02-030000.sql.gz | \
  psql -U memos memos

# 3. 启动
sudo systemctl start memos-graph

# 4. 验证
memos-graph doctor
```

---

## 5. 监控

### 5.1 内置 metric（Prometheus 格式）

```bash
curl -s http://localhost:8765/metrics
# memos_graph_recall_stage_duration_seconds_bucket{stage="fts",le="0.1"} 42
# memos_graph_recall_total{result="hit"} 156
# memos_graph_chunks_total{agent_id="nako",scope="private"} 1024
# memos_graph_embedding_duration_seconds_bucket{model="nomic-embed-text",le="0.1"} 89
# memos_graph_heartbeat_dispatched_total{agent_id="nako",stage="1"} 3
# memos_graph_http_requests_total{method="POST",path="/memories/search",status="200"} 156
```

### 5.2 健康检查

| 端点 | 用途 | 失败怎么办 |
|------|------|----------|
| `/api/v1/health` | liveness | 重启 daemon |
| `/api/v1/health/ready` | readiness（含 PG + Ollama）| 检查 PG / Ollama / 配置 |
| `/metrics` | Prometheus 拉取 | 加监控 |

### 5.3 日志

```bash
# 实时
tail -f ~/.local/share/memos-graph/logs/daemon.log

# JSON 格式（loki/ELK 友好）
jq . ~/.local/share/memos-graph/logs/daemon.log | tail

# 按 level 过滤
jq 'select(.level=="ERROR")' ~/.local/share/memos-graph/logs/daemon.log
```

### 5.4 报警规则（建议）

| 指标 | 阈值（**MOA 调整**）| 行动 |
|------|------|------|
| `recall P99 > 1.5s` | 持续 5min | 加 PG 索引 / 限流 |
| `embedding error rate > 5%` | 持续 5min | 重启 Ollama / 切换 provider |
| `heartbeat dispatched = 0` | 24h | 检查 scheduler |
| `daemon memory > 1GB`（**原 500MB 触发太频繁**）| 持续 1h | 重启 + 调 pool size |
| `disk usage > 80%` | 持续 1h | 清理备份 / 扩盘 |
| **PG active connections > pool_size × 0.8`**（**MOA 新增**）| 持续 5min | 调 pool_size / 排查连接泄漏 |
| **Ollama queue length > 10**（**MOA 新增**）| 持续 5min | 加速 embedding 缓存 / 限流 |

---

## 6. 故障排查

### 6.1 daemon 起不来

| 症状 | 可能原因 | 解决 |
|------|---------|------|
| `connection refused :5432` | PG 没启 | `sudo systemctl start postgresql` |
| `password authentication failed` | .env 密码错 | 重设 PG password |
| `vector extension not found` | pgvector 没装 | `apt install postgresql-15-pgvector` |
| `port 8765 already in use` | memos-local 占用了 | memos-graph 用 8766（见 §7） |

### 6.2 search 没结果

| 症状 | 可能原因 | 解决 |
|------|---------|------|
| 搜不到刚写的 chunk | embed 异步还没跑 | 等 1-2s 再搜 |
| 全部 query 返回 0 | dimension 不匹配 | 检查 `chunk_vectors.dimension` |
| 性能差 | HNSW 索引没建 | `\d+ chunk_vectors` 确认有 idx |
| CJK query 不命中 | tsvector 词典问题 | 改用 `simple` 词典 |

### 6.3 heartbeat 不触发

| 症状 | 可能原因 | 解决 |
|------|---------|------|
| 24h 没消息 | pack 没装 | `memos-graph pack list` |
| 投递失败 | 飞书 token 过期 | 重新 lark CLI login |
| scheduler 没跑 | daemon 早期崩 | `memos-graph doctor` |

### 6.4 backup 失败

| 症状 | 可能原因 | 解决 |
|------|---------|------|
| `permission denied` | `~/.local/share/memos-graph/backups` 不存在 | 手动 mkdir |
| `pg_dump: error` | PG 不可达 | 修 PG |
| `disk full` | 备份累积 | `memos-graph backup --prune` 清理 |

---

## 7. 与 memos-local-plugin 共存

> **背景**：本机已装 `@memtensor/memos-local-plugin`，跟 memos-graph 抢资源。

### 7.1 端口冲突

| 服务 | memos-local 默认 | memos-graph 默认 | 共存方案 |
|------|-----------------|------------------|---------|
| PG | 5433 | 5432 | **互不抢**（不同端口）|
| 嵌入服务 | 18800 | 8765 + 11434 (Ollama) | **互不抢** |
| Viewer | 18800 | 8080 | **改 memos-graph viewer port** |
| memos daemon | 8765 | 8765 | **冲突！** |

**修法**：memos-graph 用 8766，memos-local 用 8765
```yaml
# ~/.config/memos-graph/config.yaml
server:
  port: 8766  # 不跟 memos-local 撞
viewer:
  port: 8081  # 不跟 memos-local 撞
```

### 7.2 数据迁移

```bash
# 把 memos-local 的 chunks 导入 memos-graph
memos-graph migrate from-memos-local \
  --source ~/.memos_local/chunks/ \
  --agent-mapping "nako:nako,work:work-coder" \
  --scope private
```

### 7.3 互不感知运行

两套独立 daemon：
- memos-local 用飞书 bot 1（CLI 用户）
- memos-graph 用飞书 bot 2（新业务）

OR：
- memos-local 退役，逐步迁移到 memos-graph
- **不推荐**两套并存 6+ 个月

---

## 8. 性能调优

### 8.1 PG 调优

```sql
-- postgresql.conf
shared_buffers = 256MB
work_mem = 16MB
maintenance_work_mem = 128MB
effective_cache_size = 1GB
random_page_cost = 1.1  -- SSD
```

### 8.2 HNSW 参数

```sql
-- chunks_vectors 索引
CREATE INDEX idx_vectors_hnsw ON chunk_vectors 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
-- m=16 准确率/内存平衡
-- ef_construction=64 索引速度/质量平衡
```

### 8.3 memos-graph 调优

```yaml
# config.yaml
database:
  pool_size: 20  # 并发高时调大
  pool_recycle: 1800  # 30 分钟
embedding:
  cache_db: /var/lib/memos-graph/embeddings.db
  timeout_seconds: 60
```

---

## 9. 部署检查清单（v0.1.0 GA 前必过，共 15 项）

> **⚠️ MOA v0.1.0 评审：恢复演练缺定量指标、heartbeat 48h 太久**

- [ ] 干净机器跑 `install.sh` 一次成功
- [ ] `memos-graph doctor` 报 all OK
- [ ] `memos-graph migrate` 建全 11 张表
- [ ] `memos-graph pack install ./packs/nako` 成功
- [ ] `memos-graph pack run nako` 启动 + 飞书可聊
- [ ] **离线 ≤ 12h** 收到心跳（**MOA 评审：48h 太久，改 12h**）
- [ ] `memos-graph backup` 跑通
- [ ] **恢复演练（定量）**：
  - [ ] `psql -c "SELECT COUNT(*) FROM chunks"` = backup 前数量（误差 < 1%）
  - [ ] HNSW 索引 `\d+ chunk_vectors` 显示存在
  - [ ] `memos-graph doctor` 报 ready
- [ ] `pytest -m "not perf and not live"` 全绿
- [ ] 覆盖率 ≥ 85%
- [ ] `ruff check .` 无 error
- [ ] `pyright src/` 无 error
- [ ] systemd unit 在 3 个 Linux 发行版（Debian/Ubuntu/Arch）跑通
- [ ] `systemctl show memos-graph | grep -E "LimitNOFILE|MemoryMax"` 显示资源限制
- [ ] README 完整
- [ ] v0.1.0 tag 推到 git

---

**状态**：✅ Migration Plan v0.1 钉死，等待 MOA 评审
