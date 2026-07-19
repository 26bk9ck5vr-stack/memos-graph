# 优化召回方案 - 快速参考

## 优化流程

```
FTS(150) + Pattern(100) + 时间 (80) → RRF 融合 → Top 330 → LLM(330 条) → MMR 重排 → 时间衰减 → 返回
```

## 7 个阶段

| 阶段 | 名称 | 数量 | 方法 | 说明 |
|------|------|------|------|------|
| 1 | FTS | 150 | `_fts_search()` | PostgreSQL tsvector 全文搜索 |
| 2 | Pattern | 100 | `_pattern_search()` | ILIKE 模糊匹配 |
| 3 | Time | 80 | `_time_search()` | 时间最近优先 |
| 4 | RRF | 330 | `rrf_fuse()` | 融合三路召回 |
| 5 | LLM | 330 | `_llm_rerank()` | LLM 智能重排 |
| 6 | MMR | 20 | `_mmr_diversify()` | 多样性重排 |
| 7 | Time Decay | 10 | `_apply_time_decay()` | 时间衰减最终排序 |

## 配置参数

```python
req = RecallRequest(
    query="飞书插件安装方案",
    agent_id="hermes",
    use_llm_expand=True,  # 启用 LLM 重排
    max_results=10,
    # 优化配置
    fts_top_k=150,
    pattern_top_k=100,
    time_top_k=80,
    rrf_top_k=330,
)
```

## 时间衰减

```
decay = exp(-0.01 * hours_diff)

1 小时前：0.99
24 小时前：0.79
70 小时前：0.50 (半衰期)
168 小时前 (7 天): 0.19
720 小时前 (30 天): 0.0007
```

## 使用示例

```python
from memos_graph.recall import RecallEngine, RecallRequest

engine = RecallEngine()

req = RecallRequest(
    query="飞书插件安装",
    agent_id="hermes",
    use_llm_expand=True,
    max_results=10,
)

result = await engine.search(req)

print(f"召回阶段：{', '.join(result.stages_run)}")
# 输出：fts, pattern, time, rrf, llm_rerank, mmr

for hit in result.hits[:5]:
    print(f"分数={hit.final_score:.4f}, 时间衰减={hit.time_score:.4f}")
    print(f"内容：{hit.content[:100]}...")
```

## 验证

```bash
cd /home/gato/memos-graph
source .venv/bin/activate
python3 verify_optimized_recall.py
```

## 文件位置

- **核心实现**: `src/memos_graph/recall/__init__.py`
- **LLM 客户端**: `src/memos_graph/llm/client.py`
- **完整文档**: `OPTIMIZED_RECALL_SCHEME.md`
- **实施报告**: `RECALL_OPTIMIZATION_REPORT.md`
- **验证脚本**: `verify_optimized_recall.py`

## 预期提升

- **召回率**: +40%（三路召回 vs 单路）
- **精准度**: +25%（LLM 重排）
- **时效性**: 时间衰减确保近期内容优先
- **多样性**: MMR 避免重复内容
