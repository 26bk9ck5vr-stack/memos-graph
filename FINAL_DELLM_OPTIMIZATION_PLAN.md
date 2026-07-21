# memos-graph 去 LLM 化最终优化方案

**版本**: v2.0  
**整合时间**: 2026-07-19 22:30  
**来源**: LLM 依赖分析 + MOA 评测 (部分) + 实施清单

---

## 执行摘要

### 核心发现

经过深度分析，当前 memos-graph 的 7 个 LLM 依赖环节存在**严重过度设计**：

1. **召回重排** (66k tokens/次) - 🔴 **最大瓶颈**，完全可用 Cross-Encoder 替代
2. **实体抽取/事件总结** - 🟡 **80% 可规则化**，仅 5% 需要 LLM
3. **查询扩展/用户画像/心跳** - 🟢 **应完全移除**，用简单方案替代
4. **承诺抽取** - 🟢 **关键词预筛**可减少 90% 调用

### 核心建议

**立即执行** (今天):
1. ✅ 减少重排数量 330→100 (立省 70%)
2. ✅ 集成 Cross-Encoder (延迟 -80%, 成本 -90%)

**不应该做** (明确反对):
- ❌ 不要自己训练模型 (成本高，收益低)
- ❌ 不要全面去 LLM 化 (保留 5% Fallback)
- ❌ 不要过度优化查询扩展 (同义词库足够)

**架构级创新**:
- 💡 引入**级联召回**架构 (粗排→精排→重排)
- 💡 实现**查询理解**模块 (智能路由)
- 💡 构建**缓存层** (热门查询 <10ms)

---

## 一、各环节深度评估

### 1.1 召回重排 🔴 **优先级最高**

| 维度 | 评估 |
|------|------|
| **当前状态** | 66k tokens/次，2-5 秒，$0.33/次 |
| **必要性** | ❌ **低** - Cross-Encoder 效果更好 |
| **优化方案** | Cross-Encoder (BAAI/bge-reranker-large) |
| **预期收益** | 延迟 <500ms (-80%), 成本 $0.01 (-97%) |
| **实施难度** | ⭐⭐ (2 小时) |
| **推荐指数** | ⭐⭐⭐⭐⭐ (必须做) |

**代码修改**:
```python
# src/memos_graph/recall/__init__.py
from sentence_transformers import CrossEncoder

class RecallEngine:
    def __init__(self):
        self.reranker = CrossEncoder('BAAI/bge-reranker-large')
    
    async def _rerank(self, hits, query):
        contents = [h.content[:200] for h in hits]
        pairs = [[query, c] for c in contents]
        scores = self.reranker.predict(pairs)
        indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [hits[i] for i in indices]
```

**配置修改**:
```python
# 第 56 行
rrf_top_k: int = 100  # 从 330 改过来
```

---

### 1.2 实体抽取 🟡 **中等优先级**

| 维度 | 评估 |
|------|------|
| **当前状态** | 500 tokens/次，1-3 秒，每条消息调用 |
| **必要性** | ⚠️ **中** - 80% 可规则化 |
| **优化方案** | 规则 (80%) + NER (15%) + LLM (5% Fallback) |
| **预期收益** | 平均延迟 <50ms (-95%), LLM 调用 -95% |
| **实施难度** | ⭐⭐⭐ (1 天) |
| **推荐指数** | ⭐⭐⭐⭐ (应该做) |

**混合架构**:
```
文本输入
    ↓
[规则匹配] ← 80% 简单文本 (<10ms)
    ↓ 无结果
[NER 模型] ← 15% 中等文本 (<100ms)
    ↓ 无结果
[LLM Fallback] ← 5% 复杂文本 (1-3 秒)
```

---

### 1.3 事件总结 🟡 **中等优先级**

| 维度 | 评估 |
|------|------|
| **当前状态** | 300 tokens/次，1-2 秒，每条消息调用 |
| **必要性** | ⚠️ **中** - 60% 可模板化 |
| **优化方案** | 模板 (60%) + 抽取式 (30%) + LLM (10% Fallback) |
| **预期收益** | 平均延迟 <30ms (-98%), LLM 调用 -90% |
| **实施难度** | ⭐⭐ (0.5 天) |
| **推荐指数** | ⭐⭐⭐⭐ (应该做) |

---

### 1.4 承诺抽取 🟢 **低优先级**

| 维度 | 评估 |
|------|------|
| **当前状态** | 200 tokens/次，1-2 秒，10% 消息调用 |
| **必要性** | ✅ **高** - 语义理解要求高 |
| **优化方案** | 关键词预筛 (减少 90% 无效调用) |
| **预期收益** | LLM 调用 -90% |
| **实施难度** | ⭐ (30 分钟) |
| **推荐指数** | ⭐⭐⭐⭐ (应该做) |

**优化代码**:
```python
class PromiseExtractor:
    KEYWORDS = ['答应', '承诺', '保证', '会', '将', '一定', 'promise', 'will']
    
    def should_extract(self, text: str) -> bool:
        return any(kw in text.lower() for kw in self.KEYWORDS)
    
    async def extract(self, text: str):
        if not self.should_extract(text):
            return []
        return await self._llm_extract(text)
```

---

### 1.5 查询扩展 🟢 **建议移除**

| 维度 | 评估 |
|------|------|
| **当前状态** | 100 tokens/次，1-2 秒，可选调用 |
| **必要性** | ❌ **低** - 同义词库足够 |
| **优化方案** | 同义词库扩展 (<1ms) |
| **预期收益** | 完全移除 LLM 调用 |
| **实施难度** | ⭐ (1 小时) |
| **推荐指数** | ⭐⭐ (可做可不做) |

**建议**: **直接用同义词库替代**，无需 LLM

---

### 1.6 用户画像合并 🟢 **建议简化**

| 维度 | 评估 |
|------|------|
| **当前状态** | 400 tokens/次，1-2 秒，偶尔调用 |
| **必要性** | ⚠️ **中** - 规则合并可替代 |
| **优化方案** | 规则合并 (<1ms) |
| **预期收益** | 完全移除 LLM 调用 |
| **实施难度** | ⭐ (2 小时) |
| **推荐指数** | ⭐⭐⭐ (值得做) |

---

### 1.7 心跳生成 🟢 **建议简化**

| 维度 | 评估 |
|------|------|
| **当前状态** | 500 tokens/次，1-2 秒，定时调用 |
| **必要性** | ⚠️ **中** - 模板生成足够 |
| **优化方案** | 模板生成 (<1ms) |
| **预期收益** | 完全移除 LLM 调用 |
| **实施难度** | ⭐ (1 小时) |
| **推荐指数** | ⭐⭐⭐ (值得做) |

**注意**: 当前心跳调度器未启用，优先级低

---

## 二、架构级优化建议

### 2.1 级联召回架构 💡 **强烈推荐**

**当前问题**: 所有查询都走完整 7 阶段，过度处理

**新架构**:
```
用户查询
    ↓
[查询理解模块] ← 新增
    ├─ 简单查询 (50%) → [快速路径] → FTS + Pattern → 返回 (<50ms)
    ├─ 中等查询 (40%) → [标准路径] + Cross-Encoder → 返回 (<200ms)
    └─ 复杂查询 (10%) → [完整路径] + 7 阶段 → 返回 (<500ms)
```

**优势**:
- 50% 查询延迟 <50ms
- 平均延迟 <150ms
- 资源节省 60%

**实施**:
```python
class QueryClassifier:
    def classify(self, query: str) -> str:
        if len(query) < 10 and ' ' not in query:
            return 'simple'
        elif len(query) < 30:
            return 'medium'
        else:
            return 'complex'

class RecallEngine:
    async def search(self, req):
        query_type = self.classifier.classify(req.query)
        
        if query_type == 'simple':
            return await self._fast_path(req)
        elif query_type == 'medium':
            return await self._standard_path(req)
        else:
            return await self._full_path(req)
```

---

### 2.2 缓存层 💡 **强烈推荐**

**当前问题**: 相同查询重复计算

**方案**: Redis + lru_cache
```python
from functools import lru_cache
import redis

class CachedRecallEngine:
    def __init__(self):
        self.redis = redis.Redis(host='localhost', port=6379)
        self.local_cache = lru_cache(maxsize=1000)
    
    async def search(self, req):
        cache_key = f"recall:{req.agent_id}:{req.query}"
        
        # 本地缓存
        cached = self.local_cache(cache_key)
        if cached:
            return cached
        
        # Redis 缓存
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # 执行召回
        result = await self._search(req)
        
        # 缓存 (TTL 1 小时)
        self.redis.setex(cache_key, 3600, json.dumps(result))
        self.local_cache(cache_key, result)
        
        return result
```

**预期收益**:
- 热门查询命中率 >80%
- 缓存命中延迟 <10ms
- 平均延迟 -50%

---

### 2.3 监控与可观测性 🔴 **必须补充**

**当前状态**: 3.0/10，几乎为零

**必须添加的指标**:
```python
# Prometheus 指标
PROMETHEUS_METRICS = {
    'recall_stage_duration': '各阶段耗时',
    'recall_num_results': '各阶段召回数量',
    'llm_tokens_total': 'LLM Token 消耗',
    'cache_hit_total': '缓存命中数',
    'query_type_distribution': '查询类型分布',
}
```

**日志示例**:
```python
logger.info(f"""
Recall Performance:
- Query type: {query_type}
- Total time: {total_ms:.2f}ms
- Cache hit: {cache_hit}
- Stages: {stage_metrics}
- LLM tokens: {llm_tokens}
""")
```

---

## 三、技术选型推荐

### 3.1 Cross-Encoder 重排

| 模型 | 推荐度 | 延迟 (CPU) | 精度 | 大小 |
|------|--------|-----------|------|------|
| **BAAI/bge-reranker-large** | ⭐⭐⭐⭐⭐ | ~400ms | 最优 | 1.2GB |
| BAAI/bge-reranker-base | ⭐⭐⭐⭐ | ~200ms | 略低 | 400MB |
| cross-encoder/ms-marco-MiniLM-L-6-v2 | ⭐⭐⭐ | ~100ms | 中等 | 120MB |

**推荐**: **BAAI/bge-reranker-large** (中文支持好，CPU 友好)

**安装**:
```bash
pip install sentence-transformers
```

---

### 3.2 NER 实体抽取

| 模型 | 推荐度 | 延迟 (CPU) | 中文支持 | 大小 |
|------|--------|-----------|----------|------|
| **spacy zh_core_web_sm** | ⭐⭐⭐⭐⭐ | ~50ms | 好 | 50MB |
| transformers/bert-base-chinese | ⭐⭐⭐⭐ | ~100ms | 最优 | 400MB |
| HanLP | ⭐⭐⭐ | ~80ms | 好 | 200MB |

**推荐**: **spacy zh_core_web_sm** (轻量，够用)

**安装**:
```bash
pip install spacy
python -m spacy download zh_core_web_sm
```

---

### 3.3 缓存方案

| 方案 | 推荐度 | 延迟 | 容量 | 复杂度 |
|------|--------|------|------|--------|
| **lru_cache (本地)** | ⭐⭐⭐⭐ | <1ms | 1000 条 | 低 |
| **Redis** | ⭐⭐⭐⭐⭐ | <5ms | 无限 | 中 |
| **Memcached** | ⭐⭐⭐ | <5ms | 无限 | 中 |

**推荐**: **lru_cache + Redis** (两级缓存)

---

## 四、实施路线图

### 第 1 阶段：立即执行 (今天) 🔥

**任务**:
1. ✅ 修改 `rrf_top_k` 从 330→100
2. ✅ 安装 `sentence-transformers`
3. ✅ 集成 Cross-Encoder 重排
4. ✅ 验证延迟和精准度

**时间**: 2 小时  
**预期收益**: 延迟 -70%, 成本 -70%

**代码修改**:
```bash
# 1. 修改配置
sed -i 's/rrf_top_k: int = 330/rrf_top_k: int = 100/' src/memos_graph/recall/__init__.py

# 2. 安装依赖
pip install sentence-transformers

# 3. 集成代码 (见上方)

# 4. 验证
python3 quick_benchmark.py
```

---

### 第 2 阶段：本周内 🔥

**任务**:
1. ✅ 实现查询分类器 (简单/中等/复杂)
2. ✅ 实现缓存层 (lru_cache + Redis)
3. ✅ 添加基础监控指标
4. ✅ 承诺抽取关键词预筛

**时间**: 1 天  
**预期收益**: 平均延迟 -50%, LLM 调用 -50%

---

### 第 3 阶段：2 周内

**任务**:
1. ✅ 实现混合实体抽取器 (规则+NER+LLM)
2. ✅ 实现混合事件总结器 (模板 + 抽取+LLM)
3. ✅ 用户画像合并规则化
4. ✅ 心跳生成模板化

**时间**: 2 天  
**预期收益**: LLM 调用 -90%, 写入延迟 -95%

---

### 第 4 阶段：1 月内

**任务**:
1. ⚠️ 实现级联召回架构
2. ⚠️ 完善监控和告警
3. ⚠️ A/B 测试框架
4. ⚠️ 性能基准测试

**时间**: 5 天  
**预期收益**: 全面优化，可维护性提升

---

### 不做清单 ❌

**明确反对的优化**:
1. ❌ **不要自己训练模型** - 成本高，收益低，预训练模型足够
2. ❌ **不要全面去 LLM 化** - 保留 5% Fallback 处理复杂场景
3. ❌ **不要过度优化查询扩展** - 同义词库足够，无需 LLM
4. ❌ **不要在无 GPU 环境部署大模型** - CPU 友好模型优先
5. ❌ **不要忽略监控** - 可观测性必须同步建设

---

## 五、风险评估

### Top 5 风险

| 风险 | 概率 | 影响 | 应对策略 |
|------|------|------|----------|
| **1. Cross-Encoder 精度下降** | 中 | 中 | A/B 测试，保留 LLM Fallback |
| **2. 规则覆盖不足** | 高 | 低 | 持续迭代规则库，LLM Fallback |
| **3. 缓存穿透** | 中 | 中 | 布隆过滤器，空值缓存 |
| **4. Redis 单点故障** | 低 | 高 | 本地缓存降级，Redis Cluster |
| **5. 监控缺失** | 高 | 高 | 优先实施监控指标 |

### 降级策略

```python
# 降级链
Cross-Encoder 失败 → LLM 重排 → RRF 直接返回
NER 失败 → 规则匹配 → LLM Fallback
Redis 失败 → 本地缓存 → 直接查询
```

---

## 六、成本效益分析

### 优化对比

| 方案 | 开发成本 | 月费用 | 查询延迟 | LLM 调用 |
|------|----------|--------|----------|----------|
| **当前** | - | $9,900 | 2-5 秒 | 7 次/查询 |
| **阶段 1** | 2 小时 | $2,970 | 1-2 秒 | 2 次/查询 |
| **阶段 2** | 1 天 | $990 | <500ms | 0.5 次/查询 |
| **阶段 3** | 2 天 | $100 | <200ms | 0.05 次/查询 |
| **理想** | 5 天 | $10 | <100ms | 0.01 次/查询 |

**ROI 分析**:
- 阶段 1 投入产出比：1:50 (2 小时 vs $7,000/月)
- 阶段 2 投入产出比：1:20 (1 天 vs $2,000/月)
- 阶段 3 投入产出比：1:10 (2 天 vs $900/月)

---

## 七、总结与行动建议

### 核心结论

1. **召回重排是最大瓶颈** - 立即用 Cross-Encoder 替代
2. **80% LLM 调用可避免** - 规则 + 轻量模型替代
3. **级联架构是关键** - 简单查询快速路径
4. **缓存层收益巨大** - 热门查询 <10ms
5. **监控必须同步** - 避免盲优化

### 立即行动 (今天)

```bash
# 1. 修改配置 (5 分钟)
sed -i 's/rrf_top_k: int = 330/rrf_top_k: int = 100/' src/memos_graph/recall/__init__.py

# 2. 安装依赖 (5 分钟)
pip install sentence-transformers

# 3. 集成 Cross-Encoder (1 小时)
# 代码见上方"召回重排"章节

# 4. 验证 (15 分钟)
python3 quick_benchmark.py

# 5. 提交代码 (15 分钟)
git add .
git commit -m "feat: 集成 Cross-Encoder 重排，延迟 -70%, 成本 -70%"
git push
```

### 最终目标

| 指标 | 当前 | 目标 | 提升 |
|------|------|------|------|
| 查询延迟 | 2-5 秒 | <100ms | **-95%** |
| 写入延迟 | 1-3 秒 | <50ms | **-98%** |
| LLM 调用 | 7 次/查询 | 0.05 次 | **-99%** |
| 月费用 | $9,900 | $100 | **-99%** |
| 可观测性 | 3.0/10 | 9.0/10 | **+200%** |

---

*最终方案版本：v2.0*  
*整合时间：2026-07-19 22:30*  
*状态：待实施*  
*下一步：执行第 1 阶段 (今天)*
