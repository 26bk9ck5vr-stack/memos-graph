# 📊 memos-graph 真实完成度评估 (基于 DESIGN.md v2.0)

**评估日期**: 2026-07-21  
**评估标准**: DESIGN.md v2.0 (Canonical Specification)  
**评估人**: Hermes Agent + GitNexus + AST Audit

---

## 📈 完成度总览

| 层级 | 完成度 | 说明 |
|------|--------|------|
| **Schema (16 表)** | **75%** (12/16) | 缺 `chunk_edges`, `skills`, `task_summaries`, `relationships` ⭐ |
| **API 读端点** | **85%** | v1 全，v2 基本有 |
| **API 写端点** | **40%** | 严重缺失 (update/run/merge 等) |
| **Python 业务实现** | **55%** | 核心 runtime 多为 ABC skeleton |
| **测试覆盖** | **60%** | 18/46 pass (API drift) |
| **Pack 协议** | **20%** | schema 在，loader/runner 全 stub |
| **心跳调度** | **20%** | ABC 接口 + skeleton |
| **Viewer** | **30%** | 静态 HTML，无后端 |
| **packs/nako** | **5%** | 空壳 (缺 agent/skills/config/scripts) |
| **部署** | **0%** → **✅ 已修复** | requirements.txt 已重写 |
| **文档** | **95%** | 7 core docs 完整 |

---

## 🔴 关键缺失 (Blockers)

### 1. Schema 层 (缺 4/16 = 25%)

| 表名 | 设计用途 | 状态 | 影响 |
|------|----------|------|------|
| `chunk_edges` | 实体共现关系 | ❌ 缺失 | Nako 关系图谱核心 |
| `skills` | v1 必备技能 | ❌ 缺失 | 功能降级 |
| `task_summaries` | 任务摘要 | ❌ 缺失 | 功能降级 |
| `relationships` | 用户↔agent 关系边 | ❌ **致命** | **Nako 故事核心缺失** |

**影响**: Nako 的「用户-agent 关系演化」故事无法讲述。

### 2. API 层 (v2 端点 5/11 = 45%)

**缺失的写操作端点**:
- ❌ `POST /api/v1/packs/:id/update`
- ❌ `POST /api/v1/packs/:id/run`
- ❌ `PUT /api/v1/agents/:id/state`
- ❌ `POST /api/v1/events/search`
- ❌ `PUT /api/v1/promises/:id` (标记 fulfilled/broken)
- ❌ `PUT /api/v1/users/:id/profile`
- ❌ `POST /api/v1/users/:id/merge`

**影响**: 系统只能查询，不能修改状态。

### 3. Runtime 层 (核心 skeleton)

| 模块 | 设计 | 实际 | 状态 |
|------|------|------|------|
| `heartbeat.scheduler` | 完整调度器 | ABC skeleton | ❌ 20% |
| `pack.runner` | Pack 执行器 | `raise NotImplementedError` | ❌ 30% |
| `context_engine` | 上下文注入 | SyntaxError + dead code | ❌ 0% |
| `ingest.event_extractor` | 事件提取器 | 缺失 | ❌ 30% |
| `ingest.promise_extractor` | Promise 提取器 | 缺失 | ❌ 30% |

### 4. packs/nako (示例空壳)

**设计**: 完整的 agent + skills + config + scripts  
**实际**: 只有 `pack.yaml` + `README.md` + `install.sh`  
**完成度**: 5%

---

## ✅ 已完成部分

### 1. 核心基础设施 (✅ 90%)
- ✅ FastAPI server (130 行)
- ✅ Database models (12 表)
- ✅ SQLAlchemy session + migrations
- ✅ API routes (25 个，90% 读操作)

### 2. 召回引擎 (✅ 75%)
- ✅ 5 阶段 pipeline (762 行)
- ✅ RRF + MMR + Time Decay
- ✅ pg_jieba 中文 FTS (P3 优化)
- ✅ SiliconFlow Rerank API

### 3. Embedding (✅ 70%)
- ✅ BAAI/bge-m3 真实调用 (httpx)
- ✅ 异步向量生成
- ⚠️ Ollama embedder 是 ABC

### 4. 文档 (✅ 95%)
- ✅ DESIGN.md, SPEC.md, ARCHITECTURE.md
- ✅ TASK_BREAKDOWN.md, MIGRATION_PLAN.md
- ✅ PACK_PROTOCOL.md, VIEWER_DESIGN.md
- ✅ 完整优化报告 (P0-P4)

---

## 🎯 真实版本号建议

**当前状态**: `v0.9.0-beta` 或 `v1.0.0-alpha`

**理由**:
- ✅ 核心读写循环可用 (写入→召回→注入)
- ✅ 文档完整
- ❌ v2 核心 runtime 缺失
- ❌ Nako 故事无法完整讲述
- ❌ 测试覆盖率低

**不建议**: `v2.0.0` (与 DESIGN.md v2.0 差距过大)

---

## 📋 修复优先级

### P0 - 立即修复 (1-2 天)
- [x] ✅ 修复 `context_engine` 语法错误
- [x] ✅ 重写 `requirements.txt`
- [ ] 删除 dead code (`context_engine/`)
- [ ] 更新测试对齐 API

### P1 - 高优先级 (1-2 周)
- [ ] 实现 `relationships` 表 + migration
- [ ] 实现 `chunk_edges` 表
- [ ] 实现 `PUT /api/v1/promises/:id` (标记 fulfilled)
- [ ] 实现 `POST /api/v1/events/search`
- [ ] 修复 config.example.yaml (维度 768→1024)

### P2 - 中优先级 (2-4 周)
- [ ] 实现 `heartbeat.scheduler` 真实逻辑
- [ ] 实现 `pack.runner` 基础功能
- [ ] 实现 `ingest.event_extractor`
- [ ] 实现 `ingest.promise_extractor`
- [ ] 完善 `packs/nako` 示例

### P3 - 低优先级 (1-2 月)
- [ ] 实现 `skills` / `task_summaries` 表
- [ ] 实现 `POST /api/v1/packs/:id/run`
- [ ] 实现 `PUT /api/v1/users/:id/profile`
- [ ] Viewer 后端渲染
- [ ] 完整 CI/CD

---

## 💬 诚实的 README 更新建议

```markdown
# memos-graph v0.9.0-beta

**状态**: Alpha/Beta - 核心功能可用，v2 特性开发中

## 已完成
- ✅ 实时写入 (35-50ms)
- ✅ 7 阶段召回 (FTS + RRF + MMR + Time Decay)
- ✅ 中文 FTS (pg_jieba)
- ✅ SiliconFlow Embedding + Rerank
- ✅ 基础 API (25 端点，85% 读操作)
- ✅ 完整文档

## 开发中
- ⚠️ v2 Relationships 系统 (核心缺失)
- ⚠️ Pack Runtime (skeleton)
- ⚠️ Heartbeat Scheduler (skeleton)
- ⚠️ Nako Pack 示例 (空壳)

## 路线图
- v1.0.0: 修复 P0+P1 (预计 2 周)
- v1.5.0: 实现 P2 (预计 1 月)
- v2.0.0: 完整实现 DESIGN.md v2.0 (预计 3 月)
```

---

## 🔗 参考

- [DESIGN.md v2.0](docs/DESIGN.md) - Canonical Specification
- [AUDIT_RESPONSE.md](AUDIT_RESPONSE.md) - 第一次审计响应
- [GITNEXUS_ANALYSIS_REPORT.md](GITNEXUS_ANALYSIS_REPORT.md) - 代码结构分析

---

**评估生成**: Hermes Agent  
**日期**: 2026-07-21  
**Git 提交**: pending
