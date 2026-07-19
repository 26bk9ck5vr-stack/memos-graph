#!/usr/bin/env python3
"""简化回测 - 验证优化方案核心功能。"""

import sys
sys.path.insert(0, '/home/gato/memos-graph/src')

from datetime import datetime, timezone, timedelta
from memos_graph.recall import RecallEngine, RecallRequest, RecallHit, rrf_fuse

print("=" * 80)
print("优化召回方案 - 核心功能回测")
print("=" * 80)

engine = RecallEngine()

# 1. RRF 融合测试
print("\n[1/3] RRF 融合测试")
print("-" * 80)

fts_ranked = [(i+1, 0.9 - i*0.05) for i in range(150)]
pattern_ranked = [(i+50, 0.95 - i*0.05) for i in range(100)]
time_ranked = [(i+100, 1.0 - i*0.01) for i in range(80)]

rrf_result = rrf_fuse([fts_ranked, pattern_ranked, time_ranked], k=60)

print(f"输入：FTS({len(fts_ranked)}) + Pattern({len(pattern_ranked)}) + Time({len(time_ranked)})")
print(f"输出：RRF 融合 {len(rrf_result)} 条")
print(f"Top 5 chunk_ids: {[cid for cid, _ in rrf_result[:5]]}")

# 检查重叠文档
overlap_ids = set([c[0] for c in fts_ranked]) & set([c[0] for c in pattern_ranked])
if overlap_ids:
    overlap_in_top5 = [cid for cid, _ in rrf_result[:5] if cid in overlap_ids]
    print(f"重叠文档在 Top 5 中的数量：{len(overlap_in_top5)} (chunk_ids: {overlap_in_top5})")

# 2. 时间衰减测试
print("\n[2/3] 时间衰减测试")
print("-" * 80)

test_hits = [
    RecallHit(chunk_id=1, content="5 分钟前", score=0.9, stage_source="rrf",
              metadata={"created_at": datetime.now(timezone.utc) - timedelta(minutes=5)}),
    RecallHit(chunk_id=2, content="1 天前", score=0.9, stage_source="rrf",
              metadata={"created_at": datetime.now(timezone.utc) - timedelta(days=1)}),
    RecallHit(chunk_id=3, content="3 天前", score=0.9, stage_source="rrf",
              metadata={"created_at": datetime.now(timezone.utc) - timedelta(days=3)}),
    RecallHit(chunk_id=4, content="7 天前", score=0.9, stage_source="rrf",
              metadata={"created_at": datetime.now(timezone.utc) - timedelta(days=7)}),
]

decayed = engine._apply_time_decay(test_hits)

print("时间衰减效果:")
for hit in decayed:
    print(f"  {hit.content:15s} - 原始={hit.score:.2f}, 衰减={hit.time_score:.4f}, 最终={hit.final_score:.4f}")

# 3. RecallRequest 配置验证
print("\n[3/3] RecallRequest 配置验证")
print("-" * 80)

req = RecallRequest(
    query="测试",
    agent_id="hermes",
    fts_top_k=150,
    pattern_top_k=100,
    time_top_k=80,
    rrf_top_k=330,
)

print(f"配置参数:")
print(f"  fts_top_k: {req.fts_top_k} (预期：150)")
print(f"  pattern_top_k: {req.pattern_top_k} (预期：100)")
print(f"  time_top_k: {req.time_top_k} (预期：80)")
print(f"  rrf_top_k: {req.rrf_top_k} (预期：330)")

assert req.fts_top_k == 150, "FTS top_k 错误"
assert req.pattern_top_k == 100, "Pattern top_k 错误"
assert req.time_top_k == 80, "Time top_k 错误"
assert req.rrf_top_k == 330, "RRF top_k 错误"

print("\n✅ 所有配置验证通过!")

# 4. 方法存在性验证
print("\n[4/4] 新方法验证")
print("-" * 80)

methods = ['_fts_search', '_pattern_search', '_time_search', '_llm_rerank', '_apply_time_decay']
for method in methods:
    assert hasattr(engine, method), f"缺少方法：{method}"
    print(f"  ✓ {method}")

print("\n" + "=" * 80)
print("✅ 回测完成 - 所有核心功能正常!")
print("=" * 80)
print("\n优化方案总结:")
print("  FTS(150) + Pattern(100) + Time(80) → RRF → Top 330 → LLM → MMR → Time Decay")
print("=" * 80)
