"""端到端基准测试 - 验证优化后的召回性能"""

import sys
import time
import asyncio
sys.path.insert(0, '/home/gato/memos-graph/src')

from memos_graph.recall import RecallEngine, RecallRequest
from memos_graph.recall.query_classifier import QueryClassifier
from memos_graph.cache.recall_cache import get_cache, generate_cache_key
from memos_graph.db.session import _async_session_factory

async def benchmark_query(engine, classifier, query, expected_type):
    """测试单个查询"""
    print(f"\n{'='*60}")
    print(f"查询：'{query}'")
    print(f"预期类型：{expected_type}")
    print(f"{'='*60}")
    
    # 1. 查询分类
    start = time.time()
    query_type = classifier.classify(query)
    classify_time = (time.time() - start) * 1000
    print(f"\n1️⃣ 查询分类：{query_type} (耗时：{classify_time:.2f}ms)")
    
    # 2. 获取策略
    strategy = classifier.get_strategy(query_type)
    print(f"   策略：{strategy['description']}")
    print(f"   - FTS: {strategy['use_fts']}, Pattern: {strategy['use_pattern']}, Time: {strategy['use_time']}")
    print(f"   - LLM Rerank: {strategy['use_llm_rerank']}, Cache: {strategy['use_cache']}, Top-K: {strategy['top_k']}")
    
    # 3. 检查缓存
    cache = get_cache()
    cache_key = generate_cache_key('hermes', query, strategy['top_k'])
    cached_result = cache.get(cache_key)
    
    if cached_result and strategy['use_cache']:
        print(f"\n2️⃣ 缓存命中！ (耗时：<1ms)")
        return {
            'query': query,
            'type': query_type,
            'cached': True,
            'latency_ms': classify_time,
            'results': len(cached_result.get('hits', []))
        }
    else:
        print(f"\n2️⃣ 缓存未命中，执行召回...")
    
    # 4. 执行召回
    start = time.time()
    
    req = RecallRequest(
        query=query,
        agent_id='hermes',
        use_llm_expand=strategy['use_llm_rerank'],
        max_results=strategy['top_k']
    )
    
    session = _async_session_factory()()
    
    try:
        result = await engine.search(req, session)
        total_time = (time.time() - start) * 1000
        
        print(f"\n3️⃣ 召回完成:")
        print(f"   - 总耗时：{total_time:.2f}ms")
        print(f"   - 执行阶段：{', '.join(result.stages_run)}")
        print(f"   - 召回数量：{len(result.hits)}")
        print(f"   - 平均分数：{sum(h.final_score for h in result.hits) / len(result.hits):.3f}" if result.hits else "   - 无结果")
        
        # 5. 显示前 3 条结果
        if result.hits:
            print(f"\n4️⃣ Top 3 结果:")
            for i, hit in enumerate(result.hits[:3], 1):
                print(f"   {i}. [分数：{hit.final_score:.3f}] {hit.content[:80]}...")
        
        # 6. 写入缓存
        if strategy['use_cache']:
            cache.set(cache_key, {
                'query': query,
                'hits': [{'chunk_id': h.chunk_id, 'content': h.content, 'score': h.final_score} for h in result.hits]
            }, ttl=3600)
            print(f"\n5️⃣ 结果已写入缓存")
        
        return {
            'query': query,
            'type': query_type,
            'cached': False,
            'latency_ms': total_time,
            'results': len(result.hits),
            'stages': result.stages_run
        }
    
    finally:
        await session.close()

async def main():
    """主测试函数"""
    print("🧪 memos-graph 端到端基准测试")
    print("="*60)
    
    # 初始化
    print("\n初始化组件...")
    engine = RecallEngine()
    classifier = QueryClassifier()
    cache = get_cache()
    
    # 初始化数据库会话
    from memos_graph.config import load_config
    from memos_graph.db.session import create_session_factory
    config = load_config()
    engine_obj, async_session = create_session_factory(
        config.database.url,
        pool_size=config.database.pool_size,
        pool_recycle=config.database.pool_recycle,
    )
    
    print("✅ 组件初始化完成")
    
    # 测试查询
    test_queries = [
        ("飞书安装", "simple"),
        ("飞书插件如何配置 API 密钥", "medium"),
        ("比较飞书和企业微信的优缺点", "complex"),
    ]
    
    results = []
    
    # 第一轮：冷启动
    print("\n\n📊 第一轮：冷启动测试")
    for query, expected_type in test_queries:
        result = await benchmark_query(engine, classifier, query, expected_type)
        results.append(result)
    
    # 第二轮：缓存测试
    print("\n\n📊 第二轮：缓存命中测试")
    for query, expected_type in test_queries:
        result = await benchmark_query(engine, classifier, query, expected_type)
        result['round'] = 2
        results.append(result)
    
    # 统计
    print("\n\n📈 性能统计")
    print("="*60)
    
    cold_results = [r for r in results if not r['cached'] and r.get('round', 1) == 1]
    hot_results = [r for r in results if r['cached']]
    
    if cold_results:
        avg_latency = sum(r['latency_ms'] for r in cold_results) / len(cold_results)
        print(f"\n冷启动平均延迟：{avg_latency:.2f}ms")
        for r in cold_results:
            status = "✅" if r['latency_ms'] < (50 if r['type'] == 'simple' else 500 if r['type'] == 'medium' else 1000) else "⚠️"
            print(f"  {status} {r['type']}: {r['latency_ms']:.2f}ms ({r['results']} 条结果)")
    
    if hot_results:
        avg_latency = sum(r['latency_ms'] for r in hot_results) / len(hot_results)
        print(f"\n缓存命中平均延迟：{avg_latency:.2f}ms")
        cache_stats = cache.get_stats()
        print(f"缓存统计：命中率 {cache_stats['hit_rate']}, Hits: {cache_stats['hits']}, Misses: {cache_stats['misses']}")
    
    # 最终结论
    print("\n\n✅ 测试完成！")
    
    # 验证目标
    print("\n🎯 目标验证:")
    targets = [
        ("简单查询 <50ms", any(r['latency_ms'] < 50 for r in cold_results if r['type'] == 'simple')),
        ("中等查询 <500ms", any(r['latency_ms'] < 500 for r in cold_results if r['type'] == 'medium')),
        ("复杂查询 <1s", any(r['latency_ms'] < 1000 for r in cold_results if r['type'] == 'complex')),
        ("平均延迟 <150ms", avg_latency < 150 if cold_results else False),
        ("缓存命中率 >80%", float(cache_stats['hit_rate'].rstrip('%')) > 80 if hot_results else False),
    ]
    
    for target, passed in targets:
        status = "✅" if passed else "⚠️"
        print(f"  {status} {target}")
    
    return results

if __name__ == "__main__":
    try:
        results = asyncio.run(main())
        print("\n" + "="*60)
        print("基准测试完成！")
        print("="*60)
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
