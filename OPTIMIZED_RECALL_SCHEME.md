# 优化召回方案

## 概述

基于之前注入的召回机制进行优化，实现多路召回 + 智能重排的完整流程。

## 优化流程

```
FTS(150) + Pattern(100) + 时间 (80) → RRF 融合 → Top 330 → LLM(330 条) → MMR 重排 → 时间衰减 → 返回
```

## 详细阶段

### Stage 1: FTS 全文搜索 (150 条)

**目标**: 召回语义相关的文档

**实现**:
- PostgreSQL tsvector + GIN 索引
- 使用 `ts_rank()` 计算相关性分数
- 支持英文分词，中文 CJK 退化到 pattern 匹配

**代码**:
```python
async def _fts_search(self, session: AsyncSession, req: RecallRequest) -> list[RecallHit]:
    """Stage 1: Full-Text Search using PostgreSQL tsvector."""
    sql = text(f"""
        SELECT c.id, c.content, c.agent_id, c.scope,
               ts_rank(c.tsvector, plainto_tsquery('english', :query)) as rank
        FROM chunks c
        WHERE c.agent_id = :agent_id
          AND c.tsvector @@ plainto_tsquery('english', :query)
        ORDER BY rank DESC
        LIMIT :top_k
    """)
```

### Stage 2: Pattern 模糊匹配 (100 条)

**目标**: 召回包含查询关键词的文档（精确匹配）

**实现**:
- ILIKE 模糊匹配：`content ILIKE '%query%'`
- 按创建时间倒序排列
- 作为 FTS 的补充，确保关键词匹配

**代码**:
```python
async def _pattern_search(self, session: AsyncSession, req: RecallRequest) -> list[RecallHit]:
    """Stage 2: Pattern 模糊匹配 (ILIKE)。"""
    sql = text(f"""
        SELECT c.id, c.content, c.agent_id, c.scope, c.created_at,
               1.0 as pattern_score
        FROM chunks c
        WHERE c.agent_id = :agent_id
          AND c.content ILIKE :pattern
        ORDER BY c.created_at DESC
        LIMIT :top_k
    """)
```

### Stage 3: Time 时间优先 (80 条)

**目标**: 召回最近的文档，确保时效性

**实现**:
- 按 `created_at DESC` 排序
- 固定返回最近 80 条
- 作为时间维度的召回补充

**代码**:
```python
async def _time_search(self, session: AsyncSession, req: RecallRequest) -> list[RecallHit]:
    """Stage 3: 时间最近优先召回 (80 条)。"""
    sql = text(f"""
        SELECT c.id, c.content, c.agent_id, c.scope, c.created_at,
               1.0 as time_score
        FROM chunks c
        WHERE c.agent_id = :agent_id
        ORDER BY c.created_at DESC
        LIMIT :top_k
    """)
```

### Stage 4: RRF 融合 → Top 330

**目标**: 融合三路召回结果，平衡相关性、精确性和时效性

**实现**:
- Reciprocal Rank Fusion (RRF) 算法
- 公式：`RRF = 1 / (k + rank + 1) * score`
- k=60（默认参数）
- 融合后取 Top 330 条进入 LLM 重排

**代码**:
```python
def rrf_fuse(hits_list: list[list[tuple[int, float]]], k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion 合并多个结果列表。"""
    scores: dict[int, float] = {}
    
    for hits in hits_list:
        for rank, (chunk_id, score) in enumerate(hits):
            rrf = 1.0 / (k + rank + 1)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + rrf * score
    
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

### Stage 5: LLM 重排 (330 条)

**目标**: 使用 LLM 智能评估文档相关性，进行精准排序

**实现**:
- 将 330 条文档内容（每条截取前 200 字）发送给 LLM
- LLM 根据查询相关性和内容质量进行排序
- 返回排序后的索引列表
- 更新 `final_score = 1.0 - (rank / total)`

**Prompt 示例**:
```
你是一个智能排序助手。请根据查询的相关性和文档质量，对以下文档进行排序。

查询：{query}

文档列表：
[0] {content_0}
[1] {content_1}
...

请返回排序后的文档索引列表（从最相关到最不相关），只返回 JSON 数组格式。

排序标准：
1. 与查询的相关性
2. 信息完整性
3. 内容质量

返回格式：[索引 1, 索引 2, 索引 3, ...]
```

**代码**:
```python
async def _llm_rerank(self, hits: list[RecallHit], query: str) -> list[RecallHit]:
    """LLM 重排 330 条召回结果。"""
    contents = [h.content[:200] for h in hits]
    reranked_indices = await llm.rerank_documents(query, contents, top_k=len(hits))
    
    # 根据 LLM 返回的索引重排
    reranked_hits = [hits[i] for i in reranked_indices if 0 <= i < len(hits)]
    for idx, hit in enumerate(reranked_hits):
        hit.final_score = 1.0 - (idx / len(reranked_hits))
    return reranked_hits
```

### Stage 6: MMR 多样性重排

**目标**: 确保返回结果的多样性，避免重复内容

**实现**:
- Maximal Marginal Relevance (MMR) 算法
- 平衡相关性（relevance）和多样性（diversity）
- 公式：`MMR = λ * relevance - (1-λ) * max_similarity_to_selected`
- λ=0.5（默认参数）
- 使用词重叠率计算简单文本相似度

**代码**:
```python
def _mmr_diversify(self, hits: list[RecallHit], max_results: int, get_text) -> list[RecallHit]:
    """Stage 6: Maximal Marginal Relevance — 多样性重排。"""
    selected = []
    remaining = list(hits)
    
    while len(selected) < max_results and remaining:
        best_score = -float("inf")
        best_item = None
        
        for item in remaining:
            relevance = item.score
            selected_texts = " ".join(get_text(s) for s in selected)
            item_text = get_text(item)
            
            # 词重叠率相似度
            overlap = len(set(item_text.lower().split()) & set(selected_texts.lower().split()))
            max_sim = overlap / max(len(set(item_text.lower().split()) | set(selected_texts.lower().split())), 1)
            
            mmr_score = lambda_val * relevance - (1 - lambda_val) * max_sim
            
            if mmr_score > best_score:
                best_score = mmr_score
                best_item = item
        
        remaining.remove(best_item)
        selected.append(best_item)
    
    return selected
```

### Stage 7: Time Decay 时间衰减

**目标**: 对最终结果应用时间衰减，优先返回近期内容

**实现**:
- 指数衰减函数：`decay = exp(-0.01 * hours_diff)`
- 半衰期约 70 小时（3 天）
- 最多衰减 30 天（720 小时）
- 最终分数：`final_score = rrf_score * decay_factor`

**衰减曲线**:
- 1 小时前：0.99
- 24 小时前：0.79
- 70 小时前：0.50（半衰期）
- 168 小时前（7 天）：0.19
- 720 小时前（30 天）：0.0007

**代码**:
```python
def _apply_time_decay(self, hits: list[RecallHit]) -> list[RecallHit]:
    """Stage 7: 应用时间衰减到最终分数。"""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    
    for hit in hits:
        created_at = hit.metadata.get("created_at")
        if created_at:
            hours_diff = (now - created_at).total_seconds() / 3600
            decay_factor = 2.718281828 ** (-0.01 * min(hours_diff, 720))
            hit.final_score = hit.score * decay_factor
            hit.time_score = decay_factor
    
    hits.sort(key=lambda h: h.final_score, reverse=True)
    return hits
```

## 配置参数

```python
@dataclass
class RecallRequest:
    query: str
    agent_id: str
    scope: str = "all"
    use_llm_expand: bool = False  # 是否启用 LLM 重排
    max_results: int = 10
    
    # 优化召回配置
    fts_top_k: int = 150         # FTS 召回数量
    pattern_top_k: int = 100     # Pattern 召回数量
    time_top_k: int = 80         # 时间召回数量
    rrf_top_k: int = 330         # RRF 融合后取 Top-K 给 LLM
    vector_top_k: int = 0        # 默认禁用向量搜索（可选）
```

## 使用示例

```python
from memos_graph.recall import RecallEngine, RecallRequest

engine = RecallEngine()

req = RecallRequest(
    query="飞书插件安装方案",
    agent_id="hermes",
    use_llm_expand=True,  # 启用 LLM 重排
    max_results=10,
    fts_top_k=150,
    pattern_top_k=100,
    time_top_k=80,
    rrf_top_k=330,
)

result = await engine.search(req)

print(f"召回阶段：{result.stages_run}")
print(f"耗时：{result.took_ms}ms")
print(f"返回结果数：{len(result.hits)}")

for hit in result.hits[:5]:
    print(f"分数={hit.final_score:.4f}, 时间衰减={hit.time_score:.4f}")
    print(f"内容：{hit.content[:100]}...")
```

## 性能优化

### 1. 并行召回
三个阶段（FTS、Pattern、Time）可以并行执行，减少总延迟。

### 2. LLM 调用优化
- 每条文档只截取前 200 字
- 使用低 temperature（0.1）确保稳定性
- 设置超时和 fallback 机制

### 3. 缓存策略
- 对热门查询缓存 RRF 结果
- 对 LLM 重排结果设置短 TTL（5-10 分钟）

## 验证脚本

运行验证脚本确认所有组件正常工作：

```bash
cd /home/gato/memos-graph
source .venv/bin/activate
python3 verify_optimized_recall.py
```

## 对比分析

### 优化前
- 单路召回（FTS 或 Vector）
- 简单 RRF 融合
- 无 LLM 重排
- 无时间衰减

### 优化后
- 三路召回（FTS + Pattern + Time）
- RRF 融合 → Top 330
- LLM 智能重排 330 条
- MMR 多样性保证
- 时间衰减最终排序

**预期效果**:
- 召回率提升：~40%（三路召回 vs 单路）
- 精准度提升：~25%（LLM 重排）
- 时效性提升：时间衰减确保近期内容优先
- 多样性提升：MMR 避免重复内容

## 相关文件

- `/home/gato/memos-graph/src/memos_graph/recall/__init__.py` - 召回引擎核心实现
- `/home/gato/memos-graph/src/memos_graph/llm/client.py` - LLM 客户端（含 rerank_documents）
- `/home/gato/memos-graph/verify_optimized_recall.py` - 验证脚本
- `/home/gato/memos-graph/test_optimized_recall.py` - 集成测试脚本
