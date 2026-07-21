# 🧠 memos-graph - GitNexus 项目分析报告

**分析日期**: 2026-07-21  
**GitNexus 版本**: 1.6.6  
**索引状态**: ✅ 已更新 (ac843d1)

---

## 📊 项目统计

### 代码库规模
- **文件数**: 88
- **代码节点**: 1,666 nodes
- **关系边**: 2,660 edges
- **功能集群**: 36 clusters
- **执行流程**: 110 flows

### 索引信息
- **最后提交**: `ac843d1` - "refactor: 清理临时数据和备份文件"
- **索引时间**: 2026-07-21 13:43:54 UTC
- **远程仓库**: https://github.com/26bk9ck5vr-stack/memos-graph

---

## 🏗️ 架构分析

### 核心模块结构

```
src/memos_graph/
├── 📡 api/                      # API 接口层 (12 个文件)
│   ├── realtime_sync.py         # 实时同步 API (P3 优化核心)
│   ├── retrieve_full.py         # 完整召回 API (P4 优化核心)
│   ├── retrieve.py              # 简单召回 API
│   ├── memories.py              # 记忆管理 API
│   ├── events.py                # 事件管理 API
│   ├── graph.py                 # Graph 查询 API
│   ├── health.py                # 健康检查 API
│   └── ...
│
├── 🔄 recall/                   # 召回引擎 (核心)
│   ├── __init__.py              # 7 阶段召回流水线
│   └── query_classifier.py      # 查询分类器
│
├── 🎯 reranker/                 # 重排序模块
│   ├── siliconflow_reranker.py  # SiliconFlow API (BAAI/bge-reranker-v2-m3)
│   └── cross_encoder.py         # 本地 CrossEncoder
│
├── 🧠 embedding/                # 向量嵌入
│   └── __init__.py              # BAAI/bge-m3 (1024 维)
│
├── 🗄️ db/                       # 数据库层
│   ├── models.py                # SQLAlchemy 模型 (Chunk, Event, Memory)
│   ├── session.py               # 数据库会话管理
│   └── migrations.py            # 数据库迁移
│
├── 🕸️ graph/                    # Graph 存储 (Neo4j)
│   └── neodb.py                 # Neo4j 连接和查询
│
├── ⏰ heartbeat/                # 心跳生成器
│   ├── scheduler.py             # 定时调度器
│   └── rules.py                 # 心跳规则
│
├── 📦 pack/                     # Pack 包管理
│   ├── loader.py                # Pack 加载器
│   ├── installer.py             # Pack 安装器
│   └── registry.py              # Pack 注册表
│
├── 🔌 sync/                     # 同步模块
│   └── hermes_sync.py           # Hermes 同步器
│
├── 🤖 llm/                      # LLM 客户端
│   ├── client.py                # LLM 客户端 (MOA 集成)
│   └── prompts/                 # Prompt 模板
│       ├── query_expand.py      # 查询扩展 Prompt
│       ├── entity_extract.py    # 实体提取 Prompt
│       └── ...
│
├── 📝 extractors/               # 提取器
│   ├── entity_extractor.py      # 实体提取器
│   └── event_summarizer.py      # 事件摘要器
│
├── 💾 storage/                  # 存储抽象层
│   └── __init__.py              # 存储接口
│
├── 🧩 context_engine/           # 上下文引擎
│   └── __init__.py              # 上下文管理
│
├── 🔧 ingest/                   # 数据摄入
│   └── __init__.py              # 数据摄入流水线
│
├── 🖥️ viewer/                   # 可视化查看器
│   ├── index.html               # 主页面
│   ├── dashboard.html           # 仪表盘
│   └── neo4j-graph.html         # Neo4j 图可视化
│
├── ⚙️ config.py                 # 配置管理
├── 🚀 server.py                 # FastAPI 服务器入口
└── 🛠️ cli.py                    # 命令行工具
```

---

## 🎯 核心功能流程

### 1. 实时写入流程 (P3 优化)
```
POST /api/v1/sync/realtime
  ↓
realtime_sync.py
  ↓
1. 解析消息 → Chunk 模型
2. jieba 分词 (Python)
3. 生成 tsvector (PostgreSQL + pg_jieba)
4. 异步向量生成 (后台任务)
  ↓
写入 PostgreSQL (35-50ms)
```

**关键文件**:
- `src/memos_graph/api/realtime_sync.py`
- `src/memos_graph/db/models.py`

### 2. 7 阶段召回流程 (P4 优化)
```
POST /api/v1/retrieve
  ↓
retrieve_full.py
  ↓
Stage 1: FTS (全文搜索) - pg_jieba 分词
Stage 2: Pattern (模糊匹配) - pg_trgm
Stage 3: Time (时间衰减) - 指数衰减
  ↓
RRF 融合 (Reciprocal Rank Fusion)
  ↓
Stage 4: MMR (最大边际相关性) - 去重
Stage 5: LLM Rerank (可选) - CrossEncoder
Stage 6: Time Decay - 最终时间加权
  ↓
返回 Top-K 结果 (~300ms)
```

**关键文件**:
- `src/memos_graph/api/retrieve_full.py`
- `src/memos_graph/recall/__init__.py`
- `src/memos_graph/reranker/siliconflow_reranker.py`

### 3. Hermes 同步流程
```
HermesSyncWorker (后台)
  ↓
1. 拉取 Hermes 会话
2. 提取事件和实体
3. 生成摘要
4. 写入 memos-graph
  ↓
PostgreSQL + Neo4j 双存储
```

**关键文件**:
- `src/memos_graph/sync/hermes_sync.py`
- `src/memos_graph/extractors/event_summarizer.py`

### 4. 心跳生成流程
```
HeartbeatScheduler (每 5 分钟)
  ↓
1. 应用规则 (rules.py)
2. 检查会话状态
3. 生成心跳消息
  ↓
写入数据库
```

**关键文件**:
- `src/memos_graph/heartbeat/scheduler.py`
- `src/memos_graph/heartbeat/rules.py`

---

## 🔥 核心集群分析

### Cluster 1: 召回引擎 (Recall Engine)
**节点数**: ~300  
**核心函数**:
- `rrf_fuse()` - RRF 融合算法
- `calculate_mmr_scores()` - 最大边际相关性
- `apply_time_decay()` - 时间衰减

**调用关系**:
```
retrieve_full.py → recall/__init__.py → reranker/
```

### Cluster 2: 实时同步 (Realtime Sync)
**节点数**: ~200  
**核心函数**:
- `sync_realtime()` - 实时同步入口
- `tokenize_for_fts()` - jieba 分词
- `generate_embedding_async()` - 异步向量生成

**优化点**:
- P3: pg_jieba 集成
- P1: 异步向量生成

### Cluster 3: 数据库模型 (DB Models)
**节点数**: ~250  
**核心模型**:
- `Chunk` - 文本块 (含 tsvector)
- `ChunkVector` - 向量 (1024 维)
- `Event` - 事件
- `Memory` - 记忆

**Trigger**:
- `update_chunks_tsvector()` - 自动更新 tsvector (jiebacfg)

### Cluster 4: LLM 集成 (LLM Integration)
**节点数**: ~150  
**功能**:
- 查询扩展
- 实体提取
- 事件摘要
- Promise 提取

**MOA 配置**:
- S1: minimax-m27/MiniMax-M2.7
- S2: xfyun-reference/astron-code-latest
- Aggregator: xfyun-aggregator/astron-code-latest

---

## 📈 执行流程 Top 10

1. **实时写入流程** (realtime_sync)
   - 步骤：5 步
   - 延迟：35-50ms

2. **7 阶段召回流程** (retrieve_full)
   - 步骤：7 步
   - 延迟：~300ms

3. **Hermes 同步流程** (hermes_sync)
   - 步骤：4 步
   - 频率：每 60 秒

4. **心跳生成流程** (heartbeat)
   - 步骤：3 步
   - 频率：每 5 分钟

5. **向量生成流程** (embedding)
   - 步骤：2 步
   - 模式：异步

6. **Pack 安装流程** (pack installer)
   - 步骤：4 步

7. **实体提取流程** (entity_extractor)
   - 步骤：3 步

8. **事件摘要流程** (event_summarizer)
   - 步骤：3 步

9. **健康检查流程** (health check)
   - 步骤：2 步

10. **数据库迁移流程** (migrations)
    - 步骤：5 步

---

## 🎯 优化历史

### P0 优化 (2026-07-19)
- **目标**: 解决"新数据总是赢"偏见
- **改进**: RRF 权重调整 (FTS=4.0, Pattern=1.5, Time=0.5)
- **效果**: E2E 延迟 1143ms → 670ms (-41%)

### P1 优化 (2026-07-20)
- **目标**: 降低写入延迟
- **改进**: 异步向量生成
- **效果**: 写入延迟 623ms → 35ms (-94%)

### P2 优化 (2026-07-20)
- **目标**: 中文查询分词
- **改进**: jieba 查询预处理
- **效果**: 短查询质量提升

### P3 优化 (2026-07-21)
- **目标**: 完整中文 FTS 支持
- **改进**: 
  - 安装 pg_jieba 扩展
  - 更新 trigger 使用 jiebacfg
  - 查询端使用 jiebacfg
- **效果**: FTS 触发率 67% → 100%

### P4 优化 (2026-07-21)
- **目标**: 提升召回质量
- **改进**:
  - FTS 查询从 simple 改为 jiebacfg
  - 过滤空格
  - 丰富测试数据
- **效果**: 关键词匹配率 47% → 100%

---

## 📦 外部依赖

### 数据库
- **PostgreSQL 17.9**
  - pgvector (向量搜索)
  - pg_jieba (中文分词)
  - pg_trgm (模糊匹配)
  - GIN 索引 (FTS)

- **Neo4j** (图存储)
  - 实体关系
  - 事件图谱

### API 服务
- **SiliconFlow**
  - Embedding: BAAI/bge-m3 (1024 维)
  - Rerank: BAAI/bge-reranker-v2-m3

- **MOA (Mixture of Agents)**
  - S1: MiniMax-M2.7
  - S2: astron-code-latest

### Python 库
- **FastAPI** - Web 框架
- **SQLAlchemy** - ORM
- **asyncpg** - PostgreSQL 驱动
- **jieba** - 中文分词
- **pydantic** - 数据验证

---

## 🔍 关键代码指标

### 最复杂模块
1. `retrieve_full.py` - 7 阶段召回逻辑
2. `realtime_sync.py` - 实时同步 + 异步向量
3. `recall/__init__.py` - RRF + MMR + Time Decay

### 最高调用频率
1. `sync_realtime()` - 每次写入
2. `retrieve()` - 每次查询
3. `update_chunks_tsvector()` - 数据库 trigger

### 最关键优化点
1. **pg_jieba 集成** - 中文 FTS 质量
2. **异步向量生成** - 写入性能
3. **RRF 权重** - 召回质量

---

## 🎓 学习建议

### 新开发者入门路径
1. 阅读 `README.md` 和 `docs/ARCHITECTURE.md`
2. 理解 `retrieve_full.py` 的 7 阶段召回
3. 学习 `realtime_sync.py` 的异步向量生成
4. 研究 P0-P4 优化报告

### 深入理解
1. 分析 `recall/__init__.py` 的 RRF 算法
2. 研究 pg_jieba 的集成方式
3. 理解 Neo4j + PostgreSQL 双存储架构

---

## 📊 GitNexus 能力

### 可用功能
- ✅ **图谱搜索** - LadybugDB
- ✅ **全文搜索** - LadybugDB-FTS
- ❌ **向量搜索** - 不可用 (exact scan limit: 10000)

### 索引覆盖
- **文件**: 88/88 (100%)
- **节点**: 1,666
- **边**: 2,660
- **集群**: 36
- **流程**: 110

---

## 🔗 相关资源

- **GitHub**: https://github.com/26bk9ck5vr-stack/memos-graph
- **文档**: `FINAL_PROJECT_SUMMARY.md`, `P3_P4_FINAL_REPORT.md`
- **测试**: `moa_s1s2_e2e_test.py`, `p4_optimization_test.py`

---

**报告生成**: GitNexus + Hermes Agent  
**日期**: 2026-07-21
