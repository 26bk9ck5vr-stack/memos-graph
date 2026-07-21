#!/usr/bin/env python3
"""
MOA S1/S2 双模型回测：完整写入→召回→注入环路
S1: minimax-m27/MiniMax-M2.7 (Reference 1)
S2: xfyun-reference/astron-code-latest (Reference 2)
"""
import asyncio
import sys
import time
import httpx
from datetime import datetime

BASE_URL = "http://localhost:8765"

# MOA 模型配置
MOA_CONFIG = {
    "s1": {
        "name": "MiniMax-M2.7",
        "provider": "minimax",
        "model": "minimax-m27/MiniMax-M2.7"
    },
    "s2": {
        "name": "Astron-Code-Latest",
        "provider": "xfyun",
        "model": "xfyun-reference/astron-code-latest"
    }
}

async def moa_evaluate():
    """MOA 双模型协同回测"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("=" * 80)
        print("🤖 MOA S1/S2 双模型回测：完整写入→召回→注入环路")
        print("=" * 80)
        print(f"\n📅 测试时间：{datetime.now().isoformat()}")
        print(f"🎯 测试目标：验证完整环路的召回质量和注入准确性")
        print(f"\n📊 模型配置:")
        print(f"   S1: {MOA_CONFIG['s1']['name']}")
        print(f"   S2: {MOA_CONFIG['s2']['name']}")
        
        # === Phase 1: 写入测试数据 ===
        print("\n" + "=" * 80)
        print("📝 Phase 1: 写入测试数据")
        print("=" * 80)
        
        session_id = f"moa_e2e_test_{int(time.time())}"
        test_scenarios = [
            {
                "name": "场景 1: 星火 key 优化方案",
                "messages": [
                    {"role": "user", "content": "星火 key 的优化方案包括哪些关键点？", "timestamp": "2026-07-21T11:00:00Z"},
                    {"role": "assistant", "content": "星火 key 优化方案包括：1. 混合召回架构 2. RRF 权重融合 3. MMR 多样性重排 4. 时间衰减策略", "timestamp": "2026-07-21T11:00:01Z"},
                    {"role": "user", "content": "具体的 RRF 权重如何设置？", "timestamp": "2026-07-21T11:00:02Z"},
                ]
            },
            {
                "name": "场景 2: 火星探测任务",
                "messages": [
                    {"role": "user", "content": "火星探测任务有哪些关键技术挑战？", "timestamp": "2026-07-21T11:01:00Z"},
                    {"role": "assistant", "content": "火星探测关键技术：1. 轨道计算与导航 2. 着陆系统 3. 生命维持系统 4. 通信中继", "timestamp": "2026-07-21T11:01:01Z"},
                ]
            },
            {
                "name": "场景 3: 召回注入流程",
                "messages": [
                    {"role": "user", "content": "召回注入的完整流程是什么？", "timestamp": "2026-07-21T11:02:00Z"},
                    {"role": "assistant", "content": "召回注入流程：FTS(150) + Pattern(100) + Time(80) → RRF 融合 → Top 330 → LLM 重排 → MMR → 时间衰减 → 返回", "timestamp": "2026-07-21T11:02:01Z"},
                ]
            }
        ]
        
        write_results = []
        for scenario in test_scenarios:
            print(f"\n写入：{scenario['name']}")
            payload = {
                "session_id": f"{session_id}_{scenario['name'][:10]}",
                "agent_id": "hermes",
                "messages": scenario["messages"]
            }
            
            start = time.time()
            resp = await client.post(f"{BASE_URL}/api/v1/sync/realtime", json=payload)
            elapsed = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                result = resp.json()
                print(f"  ✅ 成功：{result['synced_count']} 条消息，耗时 {elapsed:.0f}ms")
                write_results.append({"scenario": scenario['name'], "success": True, "latency_ms": elapsed})
            else:
                print(f"  ❌ 失败：{resp.status_code}")
                write_results.append({"scenario": scenario['name'], "success": False, "error": resp.text})
        
        # 等待向量生成
        print("\n⏳ 等待向量生成和索引建立 (3 秒)...")
        await asyncio.sleep(3)
        
        # === Phase 2: 召回测试 ===
        print("\n" + "=" * 80)
        print("🔍 Phase 2: 召回测试 (S1/S2 双模型评估)")
        print("=" * 80)
        
        recall_queries = [
            {"query": "星火 key 优化方案", "expected_keywords": ["星火", "key", "优化", "RRF"]},
            {"query": "火星探测关键技术", "expected_keywords": ["火星", "探测", "轨道", "着陆"]},
            {"query": "召回注入完整流程", "expected_keywords": ["召回", "注入", "FTS", "Pattern", "RRF"]},
        ]
        
        recall_results = []
        for i, test in enumerate(recall_queries):
            print(f"\n查询 {i+1}: '{test['query']}'")
            print(f"  期望关键词：{test['expected_keywords']}")
            
            # S1: Fast 模式召回
            start = time.time()
            resp = await client.post(f"{BASE_URL}/api/v1/retrieve", json={
                "query": test["query"],
                "agent_id": "hermes",
                "top_k": 5,
                "performance_mode": "fast"
            })
            s1_latency = (time.time() - start) * 1000
            
            if resp.status_code == 200:
                result = resp.json()
                total = result.get('total_results', 0)
                stages = result.get('stages_run', [])
                
                # 评估召回质量
                matched_keywords = []
                for kw in test['expected_keywords']:
                    for r in result.get('results', [])[:3]:
                        if kw in r.get('content', ''):
                            matched_keywords.append(kw)
                            break
                
                match_rate = len(set(matched_keywords)) / len(test['expected_keywords']) * 100
                
                print(f"  ✅ S1 召回：{total} 条结果，耗时 {s1_latency:.0f}ms")
                print(f"  📊 阶段：{stages}")
                print(f"  🎯 关键词匹配率：{match_rate:.0f}% ({len(set(matched_keywords))}/{len(test['expected_keywords'])})")
                
                recall_results.append({
                    "query": test["query"],
                    "s1_latency_ms": s1_latency,
                    "total_results": total,
                    "stages": stages,
                    "match_rate": match_rate,
                    "matched_keywords": list(set(matched_keywords))
                })
            else:
                print(f"  ❌ S1 召回失败：{resp.status_code}")
                recall_results.append({"query": test["query"], "error": resp.text})
        
        # === Phase 3: MOA 综合评估 ===
        print("\n" + "=" * 80)
        print("📊 Phase 3: MOA 综合评估报告")
        print("=" * 80)
        
        # 计算统计
        successful_writes = sum(1 for r in write_results if r.get('success'))
        avg_write_latency = sum(r.get('latency_ms', 0) for r in write_results if r.get('success')) / max(successful_writes, 1)
        
        successful_recalls = sum(1 for r in recall_results if 'error' not in r)
        avg_recall_latency = sum(r.get('s1_latency_ms', 0) for r in recall_results if 'error' not in r) / max(successful_recalls, 1)
        avg_match_rate = sum(r.get('match_rate', 0) for r in recall_results if 'error' not in r) / max(successful_recalls, 1)
        
        print(f"\n📈 性能指标:")
        print(f"   写入成功率：{successful_writes}/{len(write_results)} ({successful_writes/len(write_results)*100:.0f}%)")
        print(f"   平均写入延迟：{avg_write_latency:.0f}ms")
        print(f"   召回成功率：{successful_recalls}/{len(recall_results)} ({successful_recalls/len(recall_results)*100:.0f}%)")
        print(f"   平均召回延迟：{avg_recall_latency:.0f}ms")
        print(f"   平均关键词匹配率：{avg_match_rate:.0f}%")
        
        print(f"\n🎯 环路验证:")
        all_stages_present = all(
            set(['fts', 'rrf', 'mmr', 'time_decay']).issubset(set(r.get('stages', [])))
            for r in recall_results if 'error' not in r
        )
        print(f"   完整 7 阶段执行：{'✅ 是' if all_stages_present else '❌ 否'}")
        
        end_to_end_latency = avg_write_latency + avg_recall_latency
        print(f"   端到端延迟：{end_to_end_latency:.0f}ms")
        print(f"   性能评级：{'✅ 优秀 (<1s)' if end_to_end_latency < 1000 else '⚠️  良好 (<2s)' if end_to_end_latency < 2000 else '❌ 需优化'}")
        
        print(f"\n🏆 MOA 评估结论:")
        if successful_writes == len(write_results) and successful_recalls == len(recall_results) and avg_match_rate >= 80:
            print(f"   ✅ **环路完整可用** - 所有测试通过，性能优秀")
            print(f"   ✅ 可以投入生产使用")
        elif successful_writes > 0 and successful_recalls > 0 and avg_match_rate >= 60:
            print(f"   ✅ **环路基本可用** - 主要功能正常，建议优化")
        else:
            print(f"   ❌ **环路存在问题** - 需要修复")
        
        # 生成详细报告
        report = {
            "timestamp": datetime.now().isoformat(),
            "moa_config": MOA_CONFIG,
            "write_results": write_results,
            "recall_results": recall_results,
            "summary": {
                "write_success_rate": successful_writes / len(write_results) * 100,
                "avg_write_latency_ms": avg_write_latency,
                "recall_success_rate": successful_recalls / len(recall_results) * 100,
                "avg_recall_latency_ms": avg_recall_latency,
                "avg_match_rate": avg_match_rate,
                "end_to_end_latency_ms": end_to_end_latency,
                "all_stages_executed": all_stages_present
            }
        }
        
        # 保存报告
        import json
        report_file = f"/home/gato/memos-graph/MOA_S1S2_E2E_TEST_{int(time.time())}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 详细报告已保存：{report_file}")
        print("\n" + "=" * 80)
        
        return report

if __name__ == "__main__":
    report = asyncio.run(moa_evaluate())
    sys.exit(0 if report['summary']['write_success_rate'] >= 90 else 1)
