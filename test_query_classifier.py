"""测试查询分类器"""

import sys
sys.path.insert(0, '/home/gato/memos-graph/src')

from memos_graph.recall.query_classifier import QueryClassifier

def test_classifier():
    """测试查询分类器"""
    print("🧪 测试查询分类器...")
    print()
    
    classifier = QueryClassifier()
    
    # 测试用例
    test_cases = [
        ("安装", "simple"),
        ("飞书插件", "simple"),
        ("如何安装飞书", "simple"),
        ("飞书插件怎么配置 API", "medium"),
        ("安装飞书插件需要哪些步骤", "medium"),
        ("比较飞书和企业微信的优缺点", "complex"),
        ("如果我要安装飞书插件，并且配置 API，应该怎么做？", "complex"),
        ("总结过去一个月的所有会议记录", "complex"),
    ]
    
    print("测试结果:")
    all_passed = True
    
    for query, expected_type in test_cases:
        result = classifier.classify(query)
        status = "✅" if result == expected_type else "❌"
        
        if result != expected_type:
            all_passed = False
        
        print(f"  {status} '{query}' -> {result} (期望：{expected_type})")
    
    print()
    
    # 测试策略
    print("策略配置:")
    for qtype in ['simple', 'medium', 'complex']:
        strategy = classifier.get_strategy(qtype)
        print(f"  {qtype}: {strategy['description']}")
        print(f"    - FTS: {strategy['use_fts']}, Pattern: {strategy['use_pattern']}, Time: {strategy['use_time']}")
        print(f"    - LLM Rerank: {strategy['use_llm_rerank']}, Cache: {strategy['use_cache']}, Top-K: {strategy['top_k']}")
    
    print()
    
    if all_passed:
        print("✅ 所有测试通过！")
        return True
    else:
        print("❌ 部分测试失败")
        return False

if __name__ == "__main__":
    try:
        success = test_classifier()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
