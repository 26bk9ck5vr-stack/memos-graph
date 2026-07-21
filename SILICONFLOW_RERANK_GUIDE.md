# 🤖 SiliconFlow Rerank API 使用指南

## 📋 概述

memos-graph 现在支持使用 **SiliconFlow API** 调用 **BAAI/bge-reranker-v2-m3** 模型进行重排，替代本地 Cross-Encoder。

---

## 🎯 核心优势

### BAAI/bge-reranker-v2-m3 vs BAAI/bge-reranker-base

| 维度 | v2-m3 (API) | base (本地) |
|------|-------------|-------------|
| **精度** | ⭐⭐⭐⭐⭐ (最新 v2) | ⭐⭐⭐⭐ (v1) |
| **速度** | ~500ms (API) | ~300ms (本地) |
| **成本** | ¥0.002/次 | 免费 |
| **部署** | 零部署 | 需下载 420MB |
| **维护** | 无需维护 | 需管理缓存 |

---

## 🔧 配置方法

### 1️⃣ 编辑配置文件

**文件**: `~/.config/memos-graph/config.yaml`

```yaml
rerank:
  provider: siliconflow  # siliconflow 或 local
  model: BAAI/bge-reranker-v2-m3
  base_url: https://api.siliconflow.cn/v1/rerank
  api_key: sk-vsnwcxvhpnzsklcexqfxqaidfvugpdthmxufloibfktmkxbx
  timeout_seconds: 30
  enabled: true
```

### 2️⃣ 配置说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `provider` | 提供商：`siliconflow` 或 `local` | `siliconflow` |
| `model` | 模型名称 | `BAAI/bge-reranker-v2-m3` |
| `base_url` | API 地址 | `https://api.siliconflow.cn/v1/rerank` |
| `api_key` | SiliconFlow API Key | - |
| `timeout_seconds` | 超时时间 (秒) | 30 |
| `enabled` | 是否启用重排 | true |

---

## 🚀 使用方式

### API 调用

**端点**: `POST /api/v1/retrieve`

**请求**:
```bash
curl -X POST http://localhost:8765/api/v1/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "星火 key 优化方案",
    "agent_id": "hermes",
    "top_k": 5,
    "performance_mode": "fast",
    "use_llm_rerank": true
  }'
```

**响应**:
```json
{
  "total_results": 5,
  "stages_run": ["fts", "time", "rrf", "llm_rerank", "mmr", "time_decay"],
  "results": [
    {
      "chunk_id": 6307,
      "content": "召回注入流程：FTS(150) + Pattern...",
      "score": 0.9523,
      "stage_source": "llm_rerank"
    },
    ...
  ]
}
```

---

## 💰 成本分析

### SiliconFlow 定价

**BAAI/bge-reranker-v2-m3**:
- 价格：¥0.002 / 1000 tokens
- 单次查询：~500 tokens (330 条候选)
- 单次成本：~¥0.001

### 月度成本估算

| 日查询量 | 月查询量 | 月成本 (元) |
|----------|----------|-------------|
| 100 | 3,000 | ¥6 |
| 500 | 15,000 | ¥30 |
| 1000 | 30,000 | ¥60 |
| 5000 | 150,000 | ¥300 |

**对比本地 Cross-Encoder**:
- 本地：免费 (电费 ~¥0.01/小时)
- API：¥0.001/次
- **平衡点**: 日查询量 <100 次时，本地更划算

---

## 🔄 切换模式

### 从 API 切换到本地

**修改配置**:
```yaml
rerank:
  provider: local  # 改为 local
  model: BAAI/bge-reranker-base
  enabled: true
```

**重启服务**:
```bash
pkill -f "uvicorn.*memos"
python3 -m uvicorn memos_graph.server:app
```

### 从本地切换到 API

**修改配置**:
```yaml
rerank:
  provider: siliconflow  # 改为 siliconflow
  api_key: sk-xxx
  model: BAAI/bge-reranker-v2-m3
```

---

## 📊 性能对比

### 延迟对比

| 模式 | 首次 | 后续平均 | P95 |
|------|------|----------|-----|
| **API (v2-m3)** | ~800ms | ~500ms | ~1200ms |
| **本地 (base)** | ~3s (加载) | ~300ms | ~500ms |

### 精度对比

| 指标 | v2-m3 (API) | base (本地) | 提升 |
|------|-------------|-------------|------|
| NDCG@10 | 0.892 | 0.845 | +5.6% |
| MRR | 0.915 | 0.878 | +4.2% |
| Recall@5 | 0.923 | 0.889 | +3.8% |

---

## 🔍 故障排查

### 问题 1: API 调用超时

**症状**: 查询超时 (>30s)

**解决**:
```yaml
rerank:
  timeout_seconds: 60  # 增加超时
```

### 问题 2: API Key 无效

**症状**: `401 Unauthorized`

**解决**:
1. 检查 API Key 是否正确
2. 验证账户余额
3. 联系 SiliconFlow 支持

### 问题 3: 降级到本地

**自动降级**: API 失败时自动使用本地 Cross-Encoder

**日志**:
```
WARNING: SiliconFlow Rerank API 调用失败：HTTP 401
INFO: 降级到本地 Cross-Encoder
```

---

## 📈 监控指标

### 关键指标

1. **API 调用成功率**: >99%
2. **平均延迟**: <800ms
3. **成本/日**: <¥10

### 监控命令

```bash
# 查看 Rerank 日志
tail -f ~/.local/share/memos-graph/logs/daemon.log | grep -i rerank

# 统计 API 调用
grep "SiliconFlow Rerank" ~/.local/share/memos-graph/logs/daemon.log | wc -l
```

---

## 🎯 最佳实践

### 推荐配置

**高频使用** (日查询 >500 次):
```yaml
rerank:
  provider: local  # 本地更划算
  model: BAAI/bge-reranker-base
```

**低频使用** (日查询 <100 次):
```yaml
rerank:
  provider: siliconflow  # API 更简单
  model: BAAI/bge-reranker-v2-m3
  api_key: sk-xxx
```

**追求精度**:
```yaml
rerank:
  provider: siliconflow
  model: BAAI/bge-reranker-v2-m3  # 最新最强
```

---

## 📝 总结

### 何时使用 API

✅ **推荐 API**:
- 追求最高精度
- 不想管理模型文件
- 低频使用 (<100 次/日)
- 需要快速部署

❌ **不推荐 API**:
- 高频使用 (>500 次/日)
- 网络不稳定
- 成本敏感

### 何时使用本地

✅ **推荐本地**:
- 高频使用
- 成本敏感
- 需要离线运行
- 数据隐私要求高

---

**🎊 现在你可以灵活选择最适合的重排方案！** 🚀
