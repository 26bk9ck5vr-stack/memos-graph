# Nemos GitNexus 深度分析报告

**分析日期**: 2026-07-28  
**项目**: mmlong818/nemos (28⭐)  
**分析工具**: GitNexus (代码结构分析) + 人工深度阅读  
**核心焦点**: 5 层记忆模型 + MoE 路由 + 矛盾失效机制

---

## 📊 **项目概览**

```
Nemos SDK (TypeScript)
├── 总代码量：~5,252 行 (核心 src/)
├── 核心模块：12 个
├── 测试覆盖：v03-v05 单元测试 + 集成测试
└── 文档：RFCs + spec + paper (arXiv 论文)
```

### 核心文件结构

```
sdk/typescript/src/
├── nemos.ts           (168 行) - 主入口，Nemos 类
├── user-memory.ts     (817 行) - 用户记忆实例，ingest/getRelevantContext
├── types.ts           (771 行) - 类型定义，5 层 LAYERS 常量
├── storage.ts         (426 行) - 存储抽象
│   └── memory-impl.ts (705 行) - 内存实现 (测试用)
├── router.ts          (129 行) - MoE 路由 (LLMRouter + CentroidRouter)
├── reflect.ts         (593 行) - 反思整合 (consolidation)
├── reflect-domain.ts  (618 行) - 领域演化
├── domains.ts         (314 行) - 领域配置与激活
├── invalidation.ts    (399 行) - 矛盾失效 (双时间轴)
├── persist-derived.ts (378 行) - 派生记忆持久化
├── decay.ts           (215 行) - 遗忘曲线
├── queue.ts           (520 行) - 后台任务队列
├── prompts.ts         (520 行) - LLM Prompts
└── utils/             - 工具函数
```

---

## 🧠 **核心架构：5 层记忆模型**

### 1. **LAYERS 定义** (`types.ts:6-14`)

```typescript
export const LAYERS = [
  "archival",           // ① 原文层：未经加工的原话
  "episodic",           // ② 情景层：发生过的具体事件
  "semantic",           // ③ 语义层：客观事实
  "personal_semantic",  // ④ 个人语义层：关于"你"的偏好
  "procedural",         // ⑤ 程序层：做事的方式/习惯
] as const;

export type Layer = (typeof LAYERS)[number];
export type DerivedLayer = Exclude<Layer, "archival">; // 派生层 (非原文)
```

**关键设计**:
- ✅ `archival` 是原始数据，不可变
- ✅ 其他 4 层是 `derived` (派生)，由 LLM 从 archival 抽取
- ✅ 分层存储，检索时按需激活

---

### 2. **Memory 数据结构** (`types.ts:112-`)

```typescript
export interface Memory {
  id: string;
  layer: Layer;                    // 5 层之一
  type: MemoryType;                // user/feedback/project/reference
  content: string;                 // 内容
  scope: string;                   // "global" / "project:xxx"
  
  // 元数据
  source: MemorySource;            // 来源 (authoritative/derived)
  arousal: MemoryArousal;          // 情感强度 (0-1)
  surprise: MemorySurprise;        // 意外度
  ownership: MemoryOwnership;      // 所有权 (self/relational/public)
  
  // 时间戳
  created_at: string;              // 创建时间
  last_accessed: string;           // 最后访问
  access_count: number;            // 访问次数
  
  // 遗忘曲线
  stability: number;               // 稳定性 (FSRS 简化版)
  
  // 关系链
  archival_ref?: string;           // 指回 archival (派生必备)
  related?: string[];              // 相关记忆
  corrects?: string[];             // 纠正了谁
  corrected_by?: string[];         // 被谁纠正
  supersedes?: string;             // 替代了谁
  
  // v0.6 双时间轴 (RFC 0007)
  valid_at?: string;               // 何时为真 (derived 默认=created_at)
  invalidated_at?: string;         // 何时失效
  invalidation_reason?: BeliefState; // invalidated/superseded/corrected
}
```

**关键设计**:
- ✅ `archival_ref`: 派生记忆必须指回原文，可追溯
- ✅ `corrects` / `corrected_by`: 矛盾关系链
- ✅ `supersedes`: 替代关系 (新事实替代旧事实)
- ✅ `valid_at` + `invalidated_at`: 双时间轴，支持失效

---

## 🔄 **写入路径：ingest 流程**

### `user-memory.ts:90-` (核心方法)

```typescript
async ingest(content: string, options?: IngestOptions): Promise<IngestResult> {
  // 第 1 步：创建 archival (原文层)
  const archival: Memory = {
    id: newId(),
    layer: "archival",
    content: content,
    source: {
      authoritative: true,  // 用户亲口说的，权威
      kind: "authoritative",
      origin: "user_typed",
      chain_depth: 0,       // 0 = 用户直接输入
    },
    // ... 元数据
  };
  this.storage.insert(this.tenantId, this.userId, archival);
  
  // 第 2 步：LLM 抽取 derived (派生层)
  if (!options.skipAnalysis) {
    const derived = await analyze(content, this.llm, {
      perspectives: ["fact", "emotion", "method", "decision", "temporal"],
      doubleCheck: true,  // 双 pass 校验
    });
    
    // 第 3 步：持久化 derived
    for (const d of derived) {
      d.archival_ref = archival.id;  // 指回原文
      d.source.authoritative = false; // 派生的，非权威
      d.source.chain_depth = 1;       // 经 1 次 LLM 转述
      
      // 根据内容自动分层
      if (d.type === "preference") {
        d.layer = "personal_semantic";
      } else if (d.type === "event") {
        d.layer = "episodic";
      }
      // ...
      
      this.storage.insert(this.tenantId, this.userId, d);
    }
  }
  
  // 第 4 步：后台任务 (异步，不阻塞)
  // - 计算 embedding
  // - 触发 reflect (如果达到阈值)
  // - 领域演化
  this.worker.enqueue({ type: "post-ingest", userId: this.userId });
}
```

**关键设计**:
- ✅ **archival 不可变**: 用户原话永久保存
- ✅ **derived 分层**: LLM 自动抽取并分层
- ✅ **双 pass 校验**: 防止 LLM 幻觉
- ✅ **异步后台**: 不阻塞用户回复

---

## 🎯 **检索路径：getRelevantContext**

### `user-memory.ts:300-` (核心方法)

```typescript
async getRelevantContext(
  query: string,
  options?: ContextOptions
): Promise<string> {
  // 第 1 步：计算 query 向量
  const queryVec = await this.embedding.embed(query);
  
  // 第 2 步：MoE 路由 (决定查哪些领域)
  const routeResult = await this.router.route(query, queryVec, this.domains);
  // routeResult = {
  //   l1: "work",           // 主领域
  //   l2: ["personal"],     // 邻接领域
  //   confidence: 0.85
  // }
  
  // 第 3 步：领域内检索
  const memories = await this.storage.search({
    tenantId: this.tenantId,
    userId: this.userId,
    query: query,
    queryVec: queryVec,
    domains: [routeResult.l1, ...routeResult.l2],
    topK: options.topK || 20,
  });
  
  // 第 4 步：跨域联想 (一跳)
  const expanded = spreadActivation(memories, this.storage, {
    maxHops: 1,
    affinityThreshold: 0.5,
  });
  
  // 第 5 步：按激活度排序
  const ranked = rerankByActivation(expanded, queryVec);
  
  // 第 6 步：生成上下文
  return buildProspectiveContext(ranked, {
    includeArchival: false,  // 默认不包含原文
    tiered: true,            // 分层展示
  });
}
```

**关键设计**:
- ✅ **MoE 路由**: 先路由到相关领域，再检索 (不全量搜索)
- ✅ **跨域联想**: 沿领域关联边一跳，带出相关记忆
- ✅ **分层展示**: episodic/semantic/personal 分开呈现

---

## 🧠 **反思机制：Reflect (consolidation)**

### `reflect.ts:52-` (核心 Prompt)

```typescript
export const REFLECT_SYSTEM_PROMPT = `你是 nemos 反思整合器。

任务：读用户最近的 episodic 经验 (事件流) 与现有 personal_semantic (作为 anchor)，
抽出可升入 semantic / personal_semantic 的 pattern。

规则:
1. 仅当你看到**多条 episodic 反复指向同一模式**时，才输出新 derived (≥2 条支持)
2. 每条新 derived 必须填 consolidated_from = [对应 episodic id 数组]
3. layer 只能是 semantic / personal_semantic
4. 不要重复已有 personal_semantic 已经表达过的事实
5. 检测矛盾：新 episodic 与现有 personal_semantic 显著冲突
   → 输出新 derived，content 注明「过去 X，最近改为 Y」
   → source.perspectives_conflict=true
   → invalidates = [被推翻的 personal_semantic id]
   **此条不受规则 1「≥2 条」限制**
6. 不要输出 archival / episodic / procedural
7. 不要新增没有 episodic 支持的事实 (不要发明)

输出严格 JSON:
{
  "derived": [
    {
      "layer": "personal_semantic",
      "content": "用户喜欢浅色主题",
      "type": "user",
      "source": {
        "authoritative": false,
        "origin": "reflect-consolidation",
        "chain_depth": 1,
        "confidence": "high"
      },
      "consolidated_from": ["ep_xxx", "ep_yyy"],
      "invalidates": ["psem_zzz"]  // 推翻的旧事实
    }
  ]
}
`;
```

**关键设计**:
- ✅ **≥2 条原则**: 单条 episodic 不升层 (防过度概括)
- ✅ **consolidated_from**: 追溯来源 (哪些 episodic 整合出的)
- ✅ **矛盾检测**: 新旧事实冲突时，标记 `invalidates`
- ✅ **防发明**: 必须有 episodic 支持

---

## ⚡ **矛盾失效：双时间轴 (RFC 0007)**

### `invalidation.ts:1-` (核心逻辑)

```typescript
// v0.6: 双时间轴失效机制
// 旧事实不物理删除，而是标记 invalidated_at

export async function applyInvalidations(
  newDerived: Memory[],
  existingPersonalSemantic: Memory[],
  storage: Storage
): Promise<void> {
  for (const newMem of newDerived) {
    if (!newMem.invalidates || newMem.invalidates.length === 0) continue;
    
    // 找到被推翻的旧事实
    const oldMems = existingPersonalSemantic.filter(
      m => newMem.invalidates!.includes(m.id)
    );
    
    // 标记失效
    for (const oldMem of oldMems) {
      oldMem.invalidated_at = nowIso();
      oldMem.invalidation_reason = "superseded";
      oldMem.corrected_by = newMem.id;
      
      // 新事实的 corrects 指向旧事实
      newMem.corrects = [...(newMem.corrects || []), oldMem.id];
      
      storage.update(oldMem);
    }
  }
}
```

**关键设计**:
- ✅ **不物理删除**: 历史可追溯
- ✅ **invalidated_at**: 何时失效
- ✅ **invalidation_reason**: 为何失效 (superseded/corrected)
- ✅ **双向链**: `corrects` ↔ `corrected_by`

---

## 🎯 **MoE 路由：领域稀疏激活**

### `router.ts:1-` (核心实现)

```typescript
// 两种路由器：LLMRouter (保底) + CentroidRouter (热路径)

export class LLMRouter implements RouterProvider {
  async route(
    query: string,
    _queryVec: Float32Array | null,
    domains: Domain[]
  ): Promise<RouteResult> {
    // 用 LLM 选主领域 (L1) 和邻接领域 (L2)
    const system = `你是记忆领域路由器。给定 query 和候选领域清单，
    选出最相关的主领域 (L1) 和最多 3 个邻接领域 (L2)。
    输出 JSON: {"l1": "<domain_id>", "l2": ["<id>", ...], "confidence": 0-1}`;
    
    const user = `query: ${query}\n候选领域：${JSON.stringify(domains)}`;
    const raw = await this.llm.chat(system, user);
    const parsed = JSON.parse(raw);
    
    return {
      l1: parsed.l1,
      l2: parsed.l2,
      confidence: parsed.confidence
    };
  }
}

export class CentroidRouter implements RouterProvider {
  async route(
    _query: string,
    queryVec: Float32Array | null,
    domains: Domain[]
  ): Promise<RouteResult> {
    // 用向量相似度路由 (更快，<100ms)
    const scored = domains
      .filter(d => d.prototype_vec)  // 有质心向量
      .map(d => ({
        id: d.id,
        sim: cosineSimLocal(queryVec, d.prototype_vec)
      }))
      .sort((a, b) => b.sim - a.sim);
    
    return {
      l1: scored[0].id,
      l2: scored.slice(1, 4).map(x => x.id),
      confidence: (scored[0].sim + 1) / 2  // cosine ∈ [-1,1] → [0,1]
    };
  }
}
```

**关键设计**:
- ✅ **LLM Router**: 冷启动/领域少时用 (准确但慢)
- ✅ **Centroid Router**: 热路径用 (快，<100ms)
- ✅ **混合模式**: 自动降级 (LLM 失败→Centroid)

---

## 📉 **遗忘曲线：Decay 机制**

### `decay.ts:1-` (核心逻辑)

```typescript
// 简化版 FSRS 遗忘曲线
// 稳定性 (stability) 越高，遗忘越慢

export function applyDecay(
  memory: Memory,
  now: string,
  config: DecayConfig
): Memory {
  const daysSinceAccess = daysBetween(memory.last_accessed, now);
  
  // 稳定性衰减 (简化版)
  const decayFactor = Math.exp(-daysSinceAccess / memory.stability);
  memory.stability *= decayFactor;
  
  // 访问次数加权 (常被访问的记忆更稳定)
  const accessBoost = Math.log10(memory.access_count + 1) * 0.1;
  memory.stability += accessBoost;
  
  // 情感加权 (高 arousal 的记忆更难忘)
  const arousalBoost = memory.arousal.value * 0.2;
  memory.stability += arousalBoost;
  
  // 阈值：稳定性过低→自动降权 (检索时排除)
  if (memory.stability < config.forgetThreshold) {
    memory.is_forgotten = true;
  }
  
  return memory;
}
```

**关键设计**:
- ✅ **时间衰减**: 久未访问→稳定性下降
- ✅ **访问加权**: 常被访问→更稳定
- ✅ **情感加权**: 高 arousal→更难忘
- ✅ **自动遗忘**: 稳定性低于阈值→标记 forgotten

---

## 🛡️ **防自污染：命名空间隔离**

### `persist-derived.ts:1-` (核心约束)

```typescript
// 硬约束：derived 不能伪装成 authoritative

export async function prepareDerived(
  content: string,
  llm: LLMProvider,
  options: AnalyzeOptions
): Promise<Memory[]> {
  const derived = await llm.analyze(content, {
    perspectives: ["fact", "emotion", "method"]
  });
  
  // 硬约束：derived 的 authoritative 必须=false
  for (const d of derived) {
    d.source.authoritative = false;  // 强制
    d.source.kind = "derived";
    d.source.origin = "llm_inference";
    d.source.chain_depth = 1;
    
    // 置信度 (多视角≥2 → high)
    if (d.source.perspectives && d.source.perspectives.length >= 2) {
      d.source.confidence = "high";
    } else {
      d.source.confidence = "medium";
    }
  }
  
  return derived;
}
```

**关键设计**:
- ✅ **硬约束**: `authoritative = false` (代码强制)
- ✅ **命名空间隔离**: archival (权威) vs derived (推断)
- ✅ **置信度**: 多视角交叉验证→high

---

## 📊 **MnemoBench 基准测试**

### `bench/README.md` (实测结果)

| 机制 | 主指标 (越低越好) | 关闭 → 开启 | 提升 |
|------|------------------|------------|------|
| **防自污染** | 污染率 | 96.8% → **1.6%** | **60×** |
| **遗忘衰减** | 琐事泄漏 | 100% → **16.4%** | **6×** |
| **矛盾失效** | 旧值泄漏 | 80.0% → **34.0%** | **2.4×** |

**在 LongMemEval 知识更新切片上**:
- 仅开关"矛盾失效"一项 → **+10 个百分点** QA 准确率

---

## 🆚 **Nemos vs memos-graph**

| 维度 | Nemos (实现) | memos-graph (提案) | 融合建议 |
|------|-------------|-------------------|----------|
| **5 层模型** | ✅ 完全实现 | ⏳ 可学习 | **直接采用 Nemos 的 LAYERS** |
| **archival** | ✅ 原文存储 | chunks 表 | **统一** |
| **episodic** | ✅ 事件层 | Event 表 | **统一** |
| **semantic** | ✅ 事实层 | Entity 表 | **统一** |
| **personal** | ✅ 偏好层 | ⏳ 新增 | **新增 personal_semantic 层** |
| **procedural** | ✅ 习惯层 | ⏳ 新增 | **新增 procedural 层** |
| **MoE 路由** | ✅ LLM+Centroid | ⏳ 可学习 | **采用 CentroidRouter** |
| **矛盾失效** | ✅ 双时间轴 | ⏳ 可学习 | **采用 invalidation 机制** |
| **防污染** | ✅ 硬约束 | ⏳ 可学习 | **采用 authoritative 约束** |
| **多跳推理** | ⚠️ 一跳跨域 | ✅ 多跳 | **memos-graph 优势** |
| **情感加权** | ✅ arousal | ✅ 情感节点 | **融合** |
| **指代消解** | ⏳ 未明确 | ✅ 关系定位 | **memos-graph 优势** |

---

## 💡 **memos-graph v2.0 设计建议**

### 1. **直接采用 Nemos 的 5 层模型**

```sql
-- 新增 layer 字段到 chunks 表
ALTER TABLE chunks ADD COLUMN layer TEXT CHECK (layer IN (
  'archival',
  'episodic',
  'semantic',
  'personal_semantic',
  'procedural'
));

-- archival 层 (原文)
-- episodic 层 (事件)
-- semantic 层 (事实)
-- personal_semantic 层 (偏好)
-- procedural 层 (习惯)
```

### 2. **采用 Nemos 的写入路径**

```python
async def ingest(content: str):
    # 1. 创建 archival (权威)
    archival = Chunk(
        layer="archival",
        content=content,
        source={"authoritative": True, "chain_depth": 0}
    )
    db.add(archival)
    
    # 2. LLM 抽取 derived
    derived = await llm_analyze(content)
    for d in derived:
        d.layer = classify_layer(d)  # 自动分层
        d.archival_ref = archival.id  # 指回原文
        d.source.authoritative = False  # 派生
        db.add(d)
    
    # 3. 后台任务
    enqueue_post_ingest(archival.id)
```

### 3. **采用 Nemos 的矛盾失效**

```python
# 双时间轴
class Chunk:
    valid_at: datetime  # 何时为真
    invalidated_at: datetime  # 何时失效
    invalidation_reason: str  # superseded/corrected
    
    # 关系链
    corrects: List[int]  # 纠正了谁
    corrected_by: List[int]  # 被谁纠正
```

### 4. **保留 memos-graph 的图谱优势**

```python
# 在层内和跨层用图谱遍历
def retrieve(query: str):
    # 1. MoE 路由 (学习 Nemos)
    route = router.route(query)
    
    # 2. 层内检索
    memories = search_in_layers(route.layers)
    
    # 3. 图谱多跳联想 (memos-graph 优势)
    expanded = graph_traverse(memories, max_hops=3)
    
    # 4. 情感加权 (memos-graph 特色)
    ranked = rerank_with_emotion(expanded)
    
    return ranked
```

---

## 🎯 **结论**

### Nemos 是什么？

> **Nemos = 目前开源界最成熟的记忆引擎实现**

- ✅ **5 层模型**: archival/episodic/semantic/personal/procedural
- ✅ **完整实现**: ingest/retrieve/reflect/decay/invalidation
- ✅ **生产可用**: TypeScript SDK, 5,252 行核心代码
- ✅ **论文背书**: arXiv 论文，MnemoBench 基准

### memos-graph 的机会？

**不是重复造轮子，而是**:

```
memos-graph v2.0 = Nemos 的 5 层模型 + memos-graph 的图谱架构

具体:
- 采用 Nemos 的 LAYERS 定义
- 采用 Nemos 的写入路径 (archival→derived)
- 采用 Nemos 的矛盾失效 (双时间轴)
- 采用 Nemos 的 MoE 路由
- 保留 memos-graph 的图谱多跳推理
- 保留 memos-graph 的情感加权
- 保留 memos-graph 的指代消解
```

---

## 📦 **行动清单**

### 立即做的 (本周)

1. **阅读 Nemos RFCs**
   - RFC-0004: 遗忘与整合
   - RFC-0005: 领域路由
   - RFC-0007: 双时间失效
   - RFC-0008: 陪伴记忆拓扑

2. **运行 Nemos SDK**
   ```bash
   cd /tmp/nemos-analysis/sdk/typescript
   npm install
   npx tsx examples/companion/server.ts
   ```

3. **设计 memos-graph v2.0 Schema**
   - 5 层模型
   - 双时间轴
   - 图谱关系

### 中期做的 (2 周)

4. **实现 5 层存储**
   - 修改 `chunks` 表，增加 `layer` 字段
   - 实现 `ingest()` 方法 (archival→derived)
   - 实现 `retrieve()` 方法 (MoE 路由 + 图谱遍历)

5. **实现矛盾失效**
   - 增加 `valid_at` / `invalidated_at` 字段
   - 实现 `apply_invalidations()` 方法

6. **实现 MoE 路由**
   - 领域表设计
   - CentroidRouter (向量相似度)
   - LLMRouter (保底)

---

**Nemos 已经帮你验证了方向，现在你要做的是站在巨人肩膀上，做得更深、更远！** 🚀

---

**附录：核心代码位置**

| 功能 | 文件 | 行号 |
|------|------|------|
| 5 层定义 | `types.ts` | 6-14 |
| Memory 结构 | `types.ts` | 112- |
| ingest 流程 | `user-memory.ts` | 90- |
| retrieve 流程 | `user-memory.ts` | 300- |
| Reflect Prompt | `reflect.ts` | 52- |
| MoE 路由 | `router.ts` | 1- |
| 矛盾失效 | `invalidation.ts` | 1- |
| 遗忘曲线 | `decay.ts` | 1- |
| 防污染 | `persist-derived.ts` | 1- |
