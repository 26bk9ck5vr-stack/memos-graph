#!/usr/bin/env python3
"""P4 优化回测：提升关键词匹配率到 >80%"""

import asyncio
import httpx
import json
from datetime import datetime, timezone

BASE_URL = "http://localhost:8765"

async def p4_optimization_test():
    print("=" * 80)
    print("🚀 P4 优化回测：提升关键词匹配率")
    print("=" * 80)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Phase 1: 写入丰富的测试数据
        print("\n📝 Phase 1: 写入丰富的测试数据")
        print("-" * 80)
        
        test_scenarios = [
            {
                "name": "星火 key 优化",
                "session_id": f"p4_test_xinghuo_{int(datetime.now().timestamp())}",
                "messages": [
                    {"role": "user", "content": "星火 key 的优化方案有哪些？"},
                    {"role": "assistant", "content": "星火 key 优化方案包括：1. RRF 权重调整 2. 查询智能拆分 3. 异步向量生成 4. jieba 分词优化"},
                    {"role": "user", "content": "RRF 权重如何设置？"},
                    {"role": "assistant", "content": "RRF 权重设置：FTS=4.0, Pattern=1.5, Time=0.5，提升关键词匹配优先级"},
                    {"role": "user", "content": "优化效果如何？"},
                    {"role": "assistant", "content": "优化后星火 key 的 FTS 触发率达到 100%，关键词匹配率显著提升"}
                ],
                "expected_keywords": ["星火", "key", "优化", "RRF"]
            },
            {
                "name": "火星探测任务",
                "session_id": f"p4_test_mars_{int(datetime.now().timestamp())}",
                "messages": [
                    {"role": "user", "content": "火星探测任务的关键技术"},
                    {"role": "assistant", "content": "火星探测关键技术包括：轨道计算、着陆系统、生命维持、通信导航"},
                    {"role": "user", "content": "轨道计算难在哪里？"},
                    {"role": "assistant", "content": "火星轨道计算难点：引力摄动、轨道修正、着陆精度要求高"},
                    {"role": "user", "content": "着陆系统如何工作？"},
                    {"role": "assistant", "content": "火星着陆系统：气动减速、反推发动机、悬停避障、软着陆"}
                ],
                "expected_keywords": ["火星", "探测", "轨道", "着陆"]
            },
            {
                "name": "召回注入流程",
                "session_id": f"p4_test_recall_{int(datetime.now().timestamp())}",
                "messages": [
                    {"role": "user", "content": "召回注入的完整流程是什么？"},
                    {"role": "assistant", "content": "召回注入完整流程：FTS 全文搜索 → Pattern 模糊匹配 → Time 时间召回 → RRF 权重融合 → MMR 多样性重排 → Time Decay 时间衰减 → 返回 Top-K"},
                    {"role": "user", "content": "FTS 是什么？"},
                    {"role": "assistant", "content": "FTS 是全文搜索 (Full-Text Search)，使用 PostgreSQL tsvector 和 jieba 中文分词"},
                    {"role": "user", "content": "RRF 如何工作？"},
                    {"role": "assistant", "content": "RRF (Reciprocal Rank Fusion) 权重融合：合并多路召回结果，按排名倒数加权求和"},
                    {"role": "user", "content": "注入阶段做什么？"},
                    {"role": "assistant", "content": "注入阶段：将召回的 chunks 注入到 LLM 上下文，增强回答准确性"}
                ],
                "expected_keywords": ["召回", "注入", "FTS", "Pattern", "RRF"]
            }
        ]
        
        # 写入所有测试数据
        write_times = []
        for scenario in test_scenarios:
            payload = {
                "session_id": scenario["session_id"],
                "agent_id": "hermes",
                "messages": [
                    {**msg, "timestamp": datetime.now(timezone.utc).isoformat()}
                    for msg in scenario["messages"]
                ]
            }
            
            start = datetime.now()
            resp = await client.post(f"{BASE_URL}/api/v1/sync/realtime", json=payload)
            elapsed = (datetime.now() - start).total_seconds() * 1000
            write_times.append(elapsed)
            
            data = resp.json()
            status = "✅" if data.get("success") else "❌"
            print(f"\n{scenario['name']}")
            print(f"  {status} 写入 {len(scenario['messages'])} 条消息，耗时 {elapsed:.0f}ms")
        
        print(f"\n⏳ 等待索引建立 (5 秒)...")
        await asyncio.sleep(5)
        
        # Phase 2: 召回测试
        print("\n" + "=" * 80)
        print("🔍 Phase 2: 召回测试")
        print("-" * 80)
        
        queries = [
            {
                "query": "星火 key 优化方案",
                "session_id": test_scenarios[0]["session_id"],
                "expected": ["星火", "key", "优化", "RRF"]
            },
            {
                "query": "火星探测关键技术",
                "session_id": test_scenarios[1]["session_id"],
                "expected": ["火星", "探测", "轨道", "着陆"]
            },
            {
                "query": "召回注入完整流程",
                "session_id": test_scenarios[2]["session_id"],
                "expected": ["召回", "注入", "FTS", "Pattern", "RRF"]
            }
        ]
        
        recall_times = []
        fts_trigger_count = 0
        keyword_match_rates = []
        all_results = []
        
        for i, q in enumerate(queries):
            # 测试两种模式
            for mode in ["standard", "fast"]:
                payload = {
                    "query": q["query"],
                    "agent_id": "hermes",
                    "top_k": 5,
                    "performance_mode": mode
                }
                
                start = datetime.now()
                resp = await client.post(f"{BASE_URL}/api/v1/retrieve", json=payload)
                elapsed = (datetime.now() - start).total_seconds() * 1000
                
                data = resp.json()
                stages = data.get("stages_run", [])
                results = data.get("results", [])
                
                fts_triggered = "fts" in stages
                if fts_triggered and mode == "standard":
                    fts_trigger_count += 1
                
                # 计算关键词匹配率
                matched = 0
                all_content = " ".join([r.get("content", "") for r in results])
                for kw in q["expected"]:
                    if kw.lower() in all_content.lower():
                        matched += 1
                
                match_rate = matched / len(q["expected"]) * 100
                
                if mode == "standard":
                    recall_times.append(elapsed)
                    keyword_match_rates.append(match_rate)
                    all_results.append({
                        "query": q["query"],
                        "mode": mode,
                        "match_rate": match_rate,
                        "matched": matched,
                        "total": len(q["expected"]),
                        "stages": stages,
                        "results": results
                    })
                    
                    status = "✅" if match_rate >= 80 else "⚠️ " if match_rate >= 50 else "❌"
                    print(f"\n查询 {i+1} ({mode}): '{q['query']}'")
                    print(f"  期望关键词：{q['expected']}")
                    print(f"  {status} 耗时 {elapsed:.0f}ms, 匹配率 {match_rate:.0f}% ({matched}/{len(q['expected'])})")
                    print(f"  📊 阶段：{stages}")
                    if matched < len(q["expected"]):
                        missing = [kw for kw in q["expected"] if kw.lower() not in all_content.lower()]
                        print(f"  ⚠️  缺失关键词：{missing}")
        
        # Phase 3: 综合评估
        print("\n" + "=" * 80)
        print("📊 Phase 3: P4 优化评估报告")
        print("-" * 80)
        
        avg_write = sum(write_times) / len(write_times)
        avg_recall = sum(recall_times) / len(recall_times)
        avg_match_rate = sum(keyword_match_rates) / len(keyword_match_rates)
        fts_trigger_rate = fts_trigger_count / len(queries) * 100
        e2e_latency = avg_write + avg_recall
        
        # 计算达标率
        high_quality_count = sum(1 for rate in keyword_match_rates if rate >= 80)
        high_quality_rate = high_quality_count / len(keyword_match_rates) * 100
        
        print(f"\n📈 性能指标:")
        print(f"   平均写入延迟：{avg_write:.0f}ms")
        print(f"   平均召回延迟：{avg_recall:.0f}ms")
        print(f"   端到端延迟：{e2e_latency:.0f}ms")
        print(f"   FTS 触发率：{fts_trigger_rate:.0f}%")
        print(f"   平均关键词匹配率：{avg_match_rate:.0f}%")
        print(f"   高质量召回率：{high_quality_rate:.0f}% ({high_quality_count}/{len(keyword_match_rates)} >= 80%)")
        
        print(f"\n🎯 目标达成情况:")
        target_fts = "✅" if fts_trigger_rate >= 95 else "❌"
        target_match = "✅" if avg_match_rate >= 80 else "❌"
        target_e2e = "✅" if e2e_latency < 1000 else "❌"
        
        print(f"   FTS 触发率 >= 95%: {target_fts} ({fts_trigger_rate:.0f}%)")
        print(f"   关键词匹配率 >= 80%: {target_match} ({avg_match_rate:.0f}%)")
        print(f"   端到端 < 1000ms: {target_e2e} ({e2e_latency:.0f}ms)")
        
        print(f"\n🏆 P4 优化结论:")
        if fts_trigger_rate >= 95 and avg_match_rate >= 80 and e2e_latency < 1000:
            print(f"   ✅ **P4 优化完全成功！** 所有指标达标")
        elif avg_match_rate >= 80:
            print(f"   ✅ **关键词匹配率达标！** 平均 {avg_match_rate:.0f}%")
        elif avg_match_rate >= 60:
            print(f"   ⚠️  **接近目标** - 匹配率 {avg_match_rate:.0f}%，需要继续优化")
        else:
            print(f"   ❌ **未达目标** - 匹配率 {avg_match_rate:.0f}%")
            print(f"      建议：1. 增加测试数据相关性 2. 调整 RRF 权重 3. 优化分词策略")
        
        # 保存报告
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": "P4_optimization",
            "metrics": {
                "write_latency_avg_ms": round(avg_write, 1),
                "recall_latency_avg_ms": round(avg_recall, 1),
                "e2e_latency_ms": round(e2e_latency, 1),
                "fts_trigger_rate": round(fts_trigger_rate, 1),
                "keyword_match_rate_avg": round(avg_match_rate, 1),
                "high_quality_rate": round(high_quality_rate, 1)
            },
            "targets": {
                "fts_trigger_target": 95,
                "fts_trigger_achieved": fts_trigger_rate >= 95,
                "match_rate_target": 80,
                "match_rate_achieved": avg_match_rate >= 80,
                "e2e_target_ms": 1000,
                "e2e_achieved": e2e_latency < 1000
            },
            "success": fts_trigger_rate >= 95 and avg_match_rate >= 80 and e2e_latency < 1000
        }
        
        report_file = f"P4_OPTIMIZATION_REPORT_{int(datetime.now().timestamp())}.json"
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 详细报告：{report_file}")
        print("=" * 80)
        
        return report

if __name__ == "__main__":
    result = asyncio.run(p4_optimization_test())
    exit(0 if result["success"] else 1)
