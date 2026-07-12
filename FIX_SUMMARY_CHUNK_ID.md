# RecallHit.chunk_id 为 None 修复总结

## 问题症状
- 召回返回 1 条结果 ✅
- 但 `chunk_id` 显示 `N/A` 或 `None`
- `score` 显示 `0.000`

## 根因分析

### 数据流追踪

RecallHit 在以下阶段创建：

1. **FTS 阶段** (`recall/__init__.py:357-366`)
   - `chunk_id=row.id` (从 DB 获取)
   
2. **Vector 阶段** (`recall/__init__.py:416-425`)
   - `chunk_id=row.id` (从 DB 获取)
   
3. **RRF 阶段** (`recall/__init__.py:241-251`)
   - `chunk_id=cid` (从 RRF 融合结果获取)
   
4. **Graph 扩散阶段** (`recall/__init__.py:481-490`)
   - `chunk_id=row.id` (从 DB 获取)

### 问题定位

**根本原因**：代码中缺少对 `chunk_id` 为 `None` 的防御性检查，导致在某些边界情况下：

1. RRF 阶段：如果 `rrf_ranked` 中包含 `cid=None` 的元组，会创建无效的 RecallHit
2. Graph 扩散阶段：如果 `seed_hits` 中有 `chunk_id=None` 的 hit，SQL 查询可能行为异常
3. API 层：没有日志记录，难以调试问题

## 修复方案

### 修复 1：添加 `__post_init__` 验证

**文件**: `src/memos_graph/recall/__init__.py`

```python
@dataclass
class RecallHit:
    """一条召回结果。"""
    chunk_id: int
    content: str
    score: float
    stage_source: str
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate chunk_id is not None."""
        if self.chunk_id is None:
            raise ValueError(f"chunk_id cannot be None, stage_source={self.stage_source}")
```

**作用**：在 RecallHit 创建时立即捕获 `chunk_id=None` 的问题，并抛出明确的错误信息。

### 修复 2：RRF 阶段添加防御性检查

**文件**: `src/memos_graph/recall/__init__.py:255`

```python
rrf_hits = [
    RecallHit(
        chunk_id=cid,
        content=chunk_map[cid].content,
        score=score,
        stage_source="rrf_merged",
        metadata={"agent_id": chunk_map[cid].agent_id, "scope": chunk_map[cid].scope},
    )
    for cid, score in rrf_ranked
    if cid is not None and cid in chunk_map  # ← 添加 cid is not None 检查
]
```

**作用**：过滤掉 `cid=None` 的元组，防止创建无效的 RecallHit。

### 修复 3：Graph 扩散阶段添加防御性检查

**文件**: `src/memos_graph/recall/__init__.py:442`

```python
seed_chunk_ids = [h.chunk_id for h in seed_hits if h.chunk_id is not None]
```

**作用**：过滤掉 `chunk_id=None` 的 hit，确保 SQL 查询不会收到 `None` 值。

### 修复 4：API 层添加日志和检查

**文件**: `src/memos_graph/api/memories.py`

```python
import logging
logger = logging.getLogger(__name__)

# 在 search_memories 函数中
results = []
for hit in recall_result.hits:
    if hit.chunk_id is None:
        logger.warning(f"Skipping hit with chunk_id=None, stage_source={hit.stage_source}, score={hit.score}")
        continue
    c = chunk_map.get(hit.chunk_id)
    if c:
        results.append(MemoryResponse(...))
    else:
        logger.warning(f"Chunk not found for hit chunk_id={hit.chunk_id}, stage_source={hit.stage_source}")
```

**作用**：
- 记录 `chunk_id=None` 的 hit，帮助调试
- 记录找不到 chunk 的情况，帮助定位数据一致性问题

## 修改的文件

1. `src/memos_graph/recall/__init__.py`
   - 添加 `RecallHit.__post_init__()` 验证
   - RRF 阶段添加 `cid is not None` 检查
   - Graph 扩散阶段添加 `h.chunk_id is not None` 检查

2. `src/memos_graph/api/memories.py`
   - 添加 `logging` 导入和 `logger` 定义
   - 添加 `chunk_id=None` 检查和日志
   - 添加 chunk 未找到的日志

## 验证方法

1. **运行测试**：
   ```bash
   cd /home/gato/memos-graph
   python -m pytest tests/ -v
   ```

2. **测试召回功能**：
   ```bash
   curl -X POST http://localhost:8000/api/v1/memories/search \
     -H "Content-Type: application/json" \
     -d '{"query": "test", "agent_id": "test-agent", "top_k": 10}'
   ```

3. **检查日志**：
   - 查看是否有 `chunk_id=None` 的警告
   - 查看是否有 `Chunk not found` 的警告

## 预期效果

修复后：
- 如果任何阶段尝试创建 `chunk_id=None` 的 RecallHit，会立即抛出 `ValueError`
- RRF 和 Graph 阶段会自动过滤掉无效的 hit
- API 层会记录详细日志，帮助调试问题
- 响应中的 `chunk_id` 应该显示正确的值，而不是 `N/A` 或 `None`

## 后续建议

1. **添加单元测试**：测试 `chunk_id=None` 的边界情况
2. **监控日志**：生产环境中监控 `chunk_id=None` 的警告频率
3. **数据审计**：检查 DB 中是否有异常数据（虽然 `id` 是主键，理论上不会是 `NULL`）
