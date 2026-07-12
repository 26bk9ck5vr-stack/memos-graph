# RecallHit.chunk_id 为 None 的根因分析

## 问题描述
- 召回返回 1 条结果 ✅
- 但 `chunk_id` 显示 `N/A` 或 `None`
- `score` 显示 `0.000`

## 数据流追踪

### RecallHit 创建位置

| 阶段 | 代码位置 | chunk_id 来源 |
|------|---------|--------------|
| FTS | `recall/__init__.py:357-366` | `row.id` (DB) |
| Vector | `recall/__init__.py:416-425` | `row.id` (DB) |
| RRF | `recall/__init__.py:241-251` | `cid` (RRF 融合结果) |
| Graph | `recall/__init__.py:481-490` | `row.id` (DB) |

### 数据流

```
FTS/Vector 搜索 → RecallHit(chunk_id=row.id)
    ↓
RRF 融合 → [(chunk_id, score), ...]
    ↓
创建 rrf_hits → RecallHit(chunk_id=cid)
    ↓
MMR 重排 → 保持原有 chunk_id
    ↓
Graph 扩散 (可选) → 追加新的 RecallHit(chunk_id=row.id)
    ↓
API 层 → MemoryResponse(id=chunk.id)
```

## 根因分析

### 发现的问题

**问题 1：Graph 扩散阶段使用 `fake_hit` 可能导致问题**

在 `expand_graph()` 方法 (line 292-296):
```python
async def expand_graph(self, chunk_id: int, decay: float = 0.3) -> list[RecallHit]:
    fake_hit = RecallHit(chunk_id=chunk_id, content="", score=1.0, stage_source="graph")
    return await self._graph_diffusion(session, [fake_hit], decay)
```

如果调用时传入 `chunk_id=None`，`fake_hit.chunk_id` 就是 `None`。

**问题 2：`_graph_diffusion` 使用 `seed_hits` 查询实体**

在 `_graph_diffusion()` (line 437):
```python
seed_chunk_ids = [h.chunk_id for h in seed_hits]
```

如果 `seed_hits` 中有 `chunk_id=None` 的 hit，`seed_chunk_ids` 会包含 `None`。

然后 SQL 查询 (line 440-445):
```sql
WHERE ce.chunk_id = ANY(:chunk_ids)
```

如果 `:chunk_ids` 包含 `None`，查询可能返回意外结果。

**问题 3：RRF 阶段可能丢失 chunk_id**

在 RRF 融合后创建 RecallHit (line 241-251):
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
    if cid in chunk_map
]
```

如果 `cid` 是 `None` 且 `None in chunk_map` 返回 `True`（理论上不可能），会创建 `chunk_id=None` 的 RecallHit。

### 最可能的根因

**Graph 扩散阶段的问题**：

1. 主流程中，`mmr_hits[:3]` 被传入 `_graph_diffusion` (line 259)
2. 如果 `mmr_hits` 中有 `chunk_id=None` 的 hit（虽然理论上不应该），会传递给 Graph 阶段
3. `_graph_diffusion` 返回的 hits 可能有问题

**或者**：

**API 层序列化问题**：

在 `memories.py` (line 243-255):
```python
for hit in recall_result.hits:
    c = chunk_map.get(hit.chunk_id)
    if c:
        results.append(MemoryResponse(
            id=c.id,  # ← 这里用的是 c.id，不是 hit.chunk_id
            ...
        ))
```

如果 `hit.chunk_id` 是 `None`，`chunk_map.get(None)` 返回 `None`，这个 hit 被跳过。

但用户说"召回返回 1 条结果"，说明有一个 hit 通过了检查。

**最终判断**：问题可能出在 **API 响应序列化** 或 **前端显示逻辑**，而不是 RecallHit 本身。

因为：
1. `MemoryResponse` 模型使用 `id=c.id`，不是 `hit.chunk_id`
2. 如果 `c` 存在，`c.id` 应该是有效的 int
3. 所以 `chunk_id` 显示 `N/A` 可能是前端显示问题，或者 API 响应中缺少字段

## 修复方案

### 方案 1：添加数据验证（推荐）

在 RecallHit 创建时验证 `chunk_id` 不为 `None`：

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
        if self.chunk_id is None:
            raise ValueError(f"chunk_id cannot be None, stage_source={self.stage_source}")
```

### 方案 2：添加防御性检查

在关键阶段添加检查：

```python
# RRF 阶段
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

# Graph 扩散阶段
seed_chunk_ids = [h.chunk_id for h in seed_hits if h.chunk_id is not None]
```

### 方案 3：添加日志

在关键阶段记录 `chunk_id` 的值：

```python
logger.debug(f"FTS: chunk_id={row.id}, score={row.rank}")
logger.debug(f"Vector: chunk_id={row.id}, score={row.similarity}")
logger.debug(f"RRF: cid={cid}, score={score}, chunk_exists={cid in chunk_map}")
logger.debug(f"Graph: chunk_id={row.id}, entity_overlap={row.entity_overlap}")
```

### 方案 4：修复 API 层

确保 API 响应包含正确的 `chunk_id`：

```python
# memories.py
for hit in recall_result.hits:
    c = chunk_map.get(hit.chunk_id)
    if c and hit.chunk_id is not None:  # ← 添加检查
        results.append(MemoryResponse(
            id=c.id,
            ...
        ))
    else:
        logger.warning(f"Skipping hit with chunk_id={hit.chunk_id}, chunk_found={c is not None}")
```

## 建议的调试步骤

1. **添加日志**：在 RRF 和 Graph 阶段记录 `chunk_id` 的值
2. **检查 DB**：确认 `chunks.id` 没有 `NULL` 值
3. **检查 API 响应**：查看实际的 JSON 响应，确认 `id` 字段的值
4. **检查前端**：确认前端显示逻辑是否正确

## 总结

根据代码分析，`chunk_id` 为 `None` 的最可能原因是：

1. **Graph 扩散阶段**：`fake_hit` 或 `seed_hits` 中有 `chunk_id=None`
2. **数据问题**：DB 中存在异常数据（不太可能，因为 `id` 是主键）
3. **API 序列化问题**：`MemoryResponse` 的 `id` 字段来自 `c.id`，应该没问题
4. **前端显示问题**：可能前端没有正确显示 `id` 字段

**推荐修复**：添加 `__post_init__` 验证和防御性检查，确保 `chunk_id` 不为 `None`。
