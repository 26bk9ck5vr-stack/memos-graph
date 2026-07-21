#!/usr/bin/env python3
"""
端到端回测 - 完整召回注入流程验证

模拟真实的 memos 插件召回注入场景，验证从查询到最终返回的完整链路。
"""

import asyncio
import sys
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, '/home/gato/memos-graph/src')

from memos_graph.config import load_config
from memos_graph.db.session import create_session_factory
from memos_graph.recall import RecallEngine, RecallRequest, RecallHit, rrf_fuse


async def end_to_end_test():
    """端到端测试：完整召回注入流程。"""
    
    print("=" * 80)
    print("端到端回测 - 完整召回注入流程")
    print("=" * 80)
    
    # 初始化
    cfg = load_config()
    engine_factory = create_session_factory(str(cfg.database.url))
    engine = RecallEngine()
    
    # 测试场景：模拟 memos 插件查询
    test_cases = [
        {
            'name': '飞书插件安装',
            'query': '飞书 插件',
            'expected_stages': ['fts', 'pattern', 'time', 'rrf', 'mmr'],
        },
        {
            'name': '数据库配置',
            'query': 'database config',
            'expected_stages': ['fts', 'pattern', 'time', 'rrf', 'mmr'],
        },
        {
            'name': 'Agent 状态管理',
            'query': 'agent state',
            'expected_stages': ['fts', 'pattern', 'time', 'rrf', 'mmr'],
        },
    ]
    
    all_passed = True
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"测试用例 {i}/{len(test_cases)}: {case['name']}")
        print(f"查询：'{case['query']}'")
        print(f"{'='*80}")
        
        async with engine_factory[1]() as session:
            # 创建召回请求
            req = RecallRequest(
                query=case['query'],
                agent_id='hermes',
                scope='all',
                use_llm_expand=False,  # 先不启用 LLM，测试基础流程
                max_results=10,
                fts_top_k=150,
                pattern_top_k=100,
                time_top_k=80,
                rrf_top_k=330,
            )
            
            # 执行完整召回流程
            start_time = time.time()
            try:
                result = await engine.search(req, session=session)
                elapsed = (time.time() - start_time) * 1000
                
                print(f"\n✅ 召回成功")
                print(f"   耗时：{elapsed:.2f}ms")
                print(f"   召回阶段：{', '.join(result.stages_run)}")
                print(f"   返回结果：{len(result.hits)} 条")
                
                # 验证召回阶段
                expected = set(case['expected_stages'])
                actual = set(result.stages_run)
                if expected.issubset(actual):
                    print(f"   ✅ 阶段验证通过：包含所有预期阶段")
                else:
                    missing = expected - actual
                    print(f"   ❌ 阶段验证失败：缺少 {missing}")
                    all_passed = False
                
                # 验证结果数量
                if len(result.hits) > 0:
                    print(f"   ✅ 结果验证通过：返回了 {len(result.hits)} 条结果")
                else:
                    print(f"   ⚠️  警告：没有返回任何结果")
                
                # 显示 Top 3 结果详情
                if result.hits:
                    print(f"\n   Top 3 结果详情:")
                    for j, hit in enumerate(result.hits[:3], 1):
                        print(f"   [{j}] 最终分数={hit.final_score:.4f}")
                        print(f"       来源：{hit.stage_source}")
                        print(f"       时间衰减：{hit.time_score:.4f}")
                        print(f"       内容：{hit.content[:80]}...")
                
                # 验证分数分布
                if result.hits:
                    scores = [h.final_score for h in result.hits]
                    max_score = max(scores)
                    min_score = min(scores)
                    avg_score = sum(scores) / len(scores)
                    print(f"\n   分数分布:")
                    print(f"      最高分：{max_score:.4f}")
                    print(f"      最低分：{min_score:.4f}")
                    print(f"      平均分：{avg_score:.4f}")
                    
                    # 验证分数是否递减（经过 MMR 和时间衰减后应该大致递减）
                    if all(scores[j] >= scores[j+1] - 0.1 for j in range(len(scores)-1)):
                        print(f"   ✅ 分数排序合理")
                    else:
                        print(f"   ⚠️  分数排序有波动（可能是 MMR 多样性导致）")
                
            except Exception as e:
                print(f"\n❌ 召回失败：{e}")
                import traceback
                traceback.print_exc()
                all_passed = False
    
    await engine.close()
    
    # 最终总结
    print(f"\n{'='*80}")
    if all_passed:
        print("✅ 端到端回测完成 - 所有测试用例通过!")
    else:
        print("⚠️  端到端回测完成 - 部分测试用例失败")
    print(f"{'='*80}")
    
    return all_passed


async def test_injection_flow():
    """测试召回注入到上下文的流程。"""
    
    print(f"\n{'='*80}")
    print("召回注入流程测试")
    print(f"{'='*80}")
    
    cfg = load_config()
    engine_factory = create_session_factory(str(cfg.database.url))
    engine = RecallEngine()
    
    # 模拟真实场景：用户提问后，召回相关记忆注入到上下文
    user_question = "怎么安装飞书插件？"
    
    print(f"\n用户提问：{user_question}")
    print("-" * 80)
    
    async with engine_factory[1]() as session:
        # Step 1: 召回相关记忆
        req = RecallRequest(
            query=user_question,
            agent_id='hermes',
            use_llm_expand=False,
            max_results=5,  # 只取 Top 5 注入到上下文
            fts_top_k=150,
            pattern_top_k=100,
            time_top_k=80,
            rrf_top_k=330,
        )
        
        print("\n[Step 1] 执行召回...")
        start = time.time()
        result = await engine.search(req, session=session)
        elapsed = (time.time() - start) * 1000
        print(f"   耗时：{elapsed:.2f}ms")
        print(f"   召回阶段：{', '.join(result.stages_run)}")
        print(f"   召回数量：{len(result.hits)}")
        
        # Step 2: 构建注入上下文
        print(f"\n[Step 2] 构建注入上下文...")
        context_parts = []
        
        for i, hit in enumerate(result.hits, 1):
            context_part = f"""
[相关记忆 {i}]
来源：{hit.stage_source}
相关性：{hit.final_score:.4f}
时间衰减：{hit.time_score:.4f}
内容：{hit.content}
"""
            context_parts.append(context_part)
        
        injected_context = "\n".join(context_parts)
        
        print(f"   构建完成，总长度：{len(injected_context)} 字符")
        
        # Step 3: 模拟 LLM 调用（实际场景中会在这里调用 LLM）
        print(f"\n[Step 3] 模拟 LLM 调用...")
        llm_prompt = f"""你是 Hermes 助手。以下是相关背景信息：

{injected_context}

用户问题：{user_question}

请基于以上信息回答："""
        
        print(f"   Prompt 长度：{len(llm_prompt)} 字符")
        print(f"   注入上下文占比：{len(injected_context)/len(llm_prompt)*100:.1f}%")
        
        # Step 4: 验证注入效果
        print(f"\n[Step 4] 验证注入效果...")
        
        # 检查是否有来自不同阶段的记忆
        sources = set(h.stage_source for h in result.hits)
        print(f"   来源多样性：{len(sources)} 种 ({', '.join(sources)})")
        
        # 检查时间衰减是否生效
        decay_factors = [h.time_score for h in result.hits]
        avg_decay = sum(decay_factors) / len(decay_factors)
        print(f"   平均时间衰减：{avg_decay:.4f}")
        
        # 检查最终分数是否合理
        final_scores = [h.final_score for h in result.hits]
        print(f"   最终分数范围：{min(final_scores):.4f} - {max(final_scores):.4f}")
        
        # 验证
        checks = [
            (len(result.hits) > 0, "有召回结果"),
            (len(sources) >= 2, "来源多样性 >= 2"),
            (all(0 < s <= 1 for s in final_scores), "分数在 0-1 范围内"),
            (all(0 < d <= 1 for d in decay_factors), "时间衰减在 0-1 范围内"),
        ]
        
        print(f"\n   验证结果:")
        all_passed = True
        for check, desc in checks:
            status = "✅" if check else "❌"
            print(f"      {status} {desc}")
            if not check:
                all_passed = False
        
        if all_passed:
            print(f"\n✅ 注入流程验证通过!")
        else:
            print(f"\n❌ 注入流程验证失败!")
    
    await engine.close()
    
    return all_passed


async def test_stage_isolation():
    """测试各阶段独立工作是否正常。"""
    
    print(f"\n{'='*80}")
    print("各阶段独立测试")
    print(f"{'='*80}")
    
    cfg = load_config()
    engine_factory = create_session_factory(str(cfg.database.url))
    engine = RecallEngine()
    
    async with engine_factory[1]() as session:
        query = "test"
        agent_id = "hermes"
        
        req = RecallRequest(
            query=query,
            agent_id=agent_id,
            fts_top_k=10,
            pattern_top_k=10,
            time_top_k=10,
        )
        
        # 测试 FTS
        print("\n[1] FTS 阶段:")
        fts_hits = await engine._fts_search(session, req)
        print(f"    召回：{len(fts_hits)} 条")
        if fts_hits:
            print(f"    Top 1: {fts_hits[0].content[:50]}...")
            print(f"    ✅ FTS 阶段正常")
        else:
            print(f"    ⚠️  FTS 无结果（可能中文分词问题）")
        
        # 测试 Pattern
        print("\n[2] Pattern 阶段:")
        pattern_hits = await engine._pattern_search(session, req)
        print(f"    召回：{len(pattern_hits)} 条")
        if pattern_hits:
            print(f"    Top 1: {pattern_hits[0].content[:50]}...")
            print(f"    ✅ Pattern 阶段正常")
        else:
            print(f"    ❌ Pattern 无结果")
        
        # 测试 Time
        print("\n[3] Time 阶段:")
        time_hits = await engine._time_search(session, req)
        print(f"    召回：{len(time_hits)} 条")
        if time_hits:
            print(f"    Top 1: {time_hits[0].content[:50]}...")
            print(f"    时间：{time_hits[0].metadata.get('created_at', 'N/A')}")
            print(f"    ✅ Time 阶段正常")
        else:
            print(f"    ❌ Time 无结果")
        
        # 测试 RRF 融合
        print("\n[4] RRF 融合:")
        fts_ranked = [(h.chunk_id, h.score) for h in fts_hits]
        pattern_ranked = [(h.chunk_id, h.score) for h in pattern_hits]
        time_ranked = [(h.chunk_id, h.score) for h in time_hits]
        
        rrf_result = rrf_fuse([fts_ranked, pattern_ranked, time_ranked], k=60)
        print(f"    输入：FTS({len(fts_ranked)}) + Pattern({len(pattern_ranked)}) + Time({len(time_ranked)})")
        print(f"    输出：{len(rrf_result)} 条")
        if rrf_result:
            print(f"    Top 1 chunk_id: {rrf_result[0][0]}")
            print(f"    ✅ RRF 融合正常")
        else:
            print(f"    ❌ RRF 无结果")
        
        # 测试时间衰减
        print("\n[5] 时间衰减:")
        from memos_graph.recall import RecallHit
        
        test_hits = [
            RecallHit(chunk_id=1, content="new", score=0.9, stage_source="rrf",
                     metadata={"created_at": datetime.now(timezone.utc)}),
            RecallHit(chunk_id=2, content="old", score=0.9, stage_source="rrf",
                     metadata={"created_at": datetime.now(timezone.utc) - timedelta(days=7)}),
        ]
        
        decayed = engine._apply_time_decay(test_hits)
        print(f"    新文档衰减：{decayed[0].time_score:.4f}")
        print(f"    旧文档衰减：{decayed[1].time_score:.4f}")
        if decayed[0].time_score > decayed[1].time_score:
            print(f"    ✅ 时间衰减正常（新文档衰减更少）")
        else:
            print(f"    ❌ 时间衰减异常")
    
    await engine.close()
    
    print(f"\n✅ 各阶段独立测试完成!")


async def main():
    """主函数：运行所有回测。"""
    
    print("\n" + "=" * 80)
    print("开始端到端回测 - 完整召回注入流程验证")
    print("=" * 80 + "\n")
    
    try:
        # 1. 端到端测试
        e2e_passed = await end_to_end_test()
        
        # 2. 注入流程测试
        injection_passed = await test_injection_flow()
        
        # 3. 各阶段独立测试
        stages_passed = await test_stage_isolation()
        
        # 最终总结
        print(f"\n{'='*80}")
        print("回测总结")
        print(f"{'='*80}")
        print(f"端到端测试：{'✅ 通过' if e2e_passed else '❌ 失败'}")
        print(f"注入流程测试：{'✅ 通过' if injection_passed else '❌ 失败'}")
        print(f"各阶段独立测试：{'✅ 通过' if stages_passed else '❌ 失败'}")
        print(f"{'='*80}")
        
        if e2e_passed and injection_passed and stages_passed:
            print("\n🎉 所有回测通过！优化方案可以投入生产使用！")
            return True
        else:
            print("\n⚠️  部分回测失败，请检查问题。")
            return False
            
    except Exception as e:
        print(f"\n❌ 回测过程中发生异常：{e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
