# memos-graph v3.0 API 需求指南

**核心原则**: **最少只需 1 个 API key** (甚至可以 0 个，全本地运行)

---

## 🎯 **最小化配置方案**

### 方案 A: **0 API Keys - 全本地运行** (推荐开发测试)

```yaml
# ~/.config/memos-graph/config.yaml

database:
  url: postgresql+asyncpg://localhost:5432/memos_graph

# 本地 Ollama - 无需 API key
embedding:
  provider: ollama
  model: bge-m3
  base_url: http://localhost:11434
  dimension: 1024

llm:
  base_url: http://localhost:11434/v1
  model: qwen2.5:7b
  api_key: "ollama"  # 占位符，Ollama 不需要真实 key
```

**需要安装**:
```bash
# 1. 安装 Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 2. 拉取模型
ollama pull bge-m3      # Embedding 模型 (1024 维)
ollama pull qwen2.5:7b  # LLM 模型 (用于情感分析)

# 3. 启动 Ollama
ollama serve
```

**优点**:
- ✅ 完全免费
- ✅ 无需网络
- ✅ 数据完全本地
- ✅ 适合开发测试

**缺点**:
- ⚠️ 需要本地 GPU/大内存 (至少 8GB RAM)
- ⚠️ 速度较慢 (Embedding ~100ms/条)

---

### 方案 B: **1 API Key - 混合模式** (推荐生产)

```yaml
# ~/.config/memos-graph/config.yaml

database:
  url: postgresql+asyncpg://localhost:5432/memos_graph

# 本地 Ollama - 免费
embedding:
  provider: ollama
  model: bge-m3
  base_url: http://localhost:11434
  dimension: 1024

# SiliconFlow API - 便宜快速 (~¥0.002/次)
llm:
  base_url: https://api.siliconflow.cn/v1
  model: Qwen/Qwen2.5-7B-Instruct
  api_key: sk-YOUR_KEY_HERE  # 从 https://siliconflow.cn 获取
```

**需要**:
- 1 个 SiliconFlow API key (免费赠送 ¥10 额度)
- 本地 Ollama (仅用于 Embedding)

**优点**:
- ✅ LLM 快速准确 (~¥0.002/次)
- ✅ Embedding 免费本地
- ✅ 成本低 (1000 次召回 ≈ ¥2)

**缺点**:
- ⚠️ 需要网络访问 API

---

### 方案 C: **2 API Keys - 全云模式** (最简单)

```yaml
# ~/.config/memos-graph/config.yaml

database:
  url: postgresql+asyncpg://localhost:5432/memos_graph

# SiliconFlow Embedding API
embedding:
  provider: siliconflow
  model: BAAI/bge-m3
  base_url: https://api.siliconflow.cn/v1
  api_key: sk-YOUR_KEY_HERE
  dimension: 1024

# SiliconFlow LLM API
llm:
  base_url: https://api.siliconflow.cn/v1
  model: Qwen/Qwen2.5-7B-Instruct
  api_key: sk-YOUR_KEY_HERE
```

**需要**:
- 1 个 SiliconFlow API key (同时用于 Embedding 和 LLM)

**优点**:
- ✅ 最简单，无需本地模型
- ✅ 速度快 (Embedding ~50ms, LLM ~500ms)
- ✅ 适合无 GPU 环境

**缺点**:
- ⚠️ 成本稍高 (1000 次召回 ≈ ¥5)
- ⚠️ 需要网络

---

## 📊 **API 使用场景分析**

### v3.0 真正需要 API 的地方

| 功能 | 是否必须 | 可本地替代 | 说明 |
|------|---------|-----------|------|
| **Embedding** | ⚠️ 推荐 | ✅ Ollama | 生成向量 (1024 维) |
| **情感分析** | ⚠️ 推荐 | ✅ 规则降级 | LLM 分析文本情感 |
| **MoE 路由 (LLM)** | ❌ 可选 | ✅ Centroid | LLM 分类兜底方案 |
| **Rerank** | ❌ 未实现 | - | planned v3.1 |

### 实际 API 调用频率

假设每天 100 次召回查询：

| 模式 | Embedding 调用 | LLM 调用 | 日成本 | 月成本 |
|------|--------------|---------|--------|--------|
| **全本地** | 0 (本地) | 0 (本地) | ¥0 | ¥0 |
| **混合** | 0 (本地) | 100 (LLM) | ¥0.2 | ¥6 |
| **全云** | 100 (Embed) | 100 (LLM) | ¥0.5 | ¥15 |

*注：SiliconFlow 价格 (2026-07): Embedding ¥0.001/次，LLM ¥0.002/次*

---

## 🔑 **获取 API Keys**

### 1. SiliconFlow (推荐)

**注册地址**: https://siliconflow.cn

**免费额度**:
- 新用户赠送 ¥10
- 约等于 5000 次 LLM 调用
- 或 10000 次 Embedding 调用

**获取步骤**:
1. 注册账号
2. 进入控制台 → API Keys
3. 创建新 Key
4. 复制到配置文件

**模型推荐**:
- Embedding: `BAAI/bge-m3` (1024 维，中文优化)
- LLM: `Qwen/Qwen2.5-7B-Instruct` (快速便宜)

### 2. Ollama (本地，免费)

**安装**:
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**拉取模型**:
```bash
# Embedding 模型
ollama pull bge-m3

# LLM 模型 (选一个)
ollama pull qwen2.5:7b   # 7B, 快速 (~4GB VRAM)
ollama pull qwen2.5:14b  # 14B, 更准确 (~8GB VRAM)
ollama pull llama3.1:8b  # 8B, 英文更好 (~4GB VRAM)
```

**验证**:
```bash
ollama run bge-m3 "你好世界"
ollama run qwen2.5:7b "今天天气不错"
```

---

## ⚙️ **配置示例**

### 最小化配置 (仅本地 Ollama)

```yaml
# ~/.config/memos-graph/config.yaml

database:
  url: postgresql+asyncpg://localhost:5432/memos_graph

embedding:
  provider: ollama
  model: bge-m3
  base_url: http://localhost:11434
  dimension: 1024

llm:
  base_url: http://localhost:11434/v1
  model: qwen2.5:7b
  api_key: "ollama"  # 占位符
```

### 生产配置 (SiliconFlow + Ollama 混合)

```yaml
# ~/.config/memos-graph/config.yaml

database:
  url: postgresql+asyncpg://user:pass@localhost:5432/memos_graph

embedding:
  provider: ollama  # 本地免费
  model: bge-m3
  base_url: http://localhost:11434
  dimension: 1024

llm:
  base_url: https://api.siliconflow.cn/v1
  model: Qwen/Qwen2.5-7B-Instruct
  api_key: sk-xxxxxxxxxxxxxxxx  # 真实 API key
  timeout_seconds: 30
```

---

## 🚨 **常见问题**

### Q1: 没有 API key 能运行吗？

**可以！** 使用本地 Ollama：
```bash
ollama pull bge-m3
ollama pull qwen2.5:7b
```

配置中设置 `provider: ollama` 即可，无需任何 API key。

### Q2: API key 太贵怎么办？

**优化方案**:
1. Embedding 用本地 Ollama (免费)
2. LLM 只在需要情感分析时调用
3. 关闭 MoE 路由的 LLM 模式，只用 Centroid (免费)

这样 1000 次召回成本 < ¥2。

### Q3: 可以同时用多个 API 提供商吗？

**可以**，但配置文件中只能指定一个默认。可以：
- 主配置用 SiliconFlow
- 测试配置用 Ollama
- 通过环境变量切换

### Q4: 如何验证 API 是否工作？

```bash
# 测试 SiliconFlow
curl -X POST https://api.siliconflow.cn/v1/embeddings \
  -H "Authorization: Bearer sk-YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "BAAI/bge-m3", "input": "test"}'

# 测试 Ollama
curl http://localhost:11434/api/embeddings \
  -d '{"model": "bge-m3", "prompt": "test"}'
```

---

## 📝 **总结**

### 最低要求

- **0 API Keys**: 全本地 Ollama (推荐开发)
- **1 API Key**: SiliconFlow LLM + 本地 Ollama Embedding (推荐生产)
- **2 API Keys**: 全 SiliconFlow (最简单)

### 推荐方案

**开发测试**: 方案 A (全本地，0 成本)  
**小规模生产**: 方案 B (混合，月成本 ¥6)  
**大规模生产**: 方案 C (全云，月成本 ¥15/千次)

### 下一步

1. 选择方案 (A/B/C)
2. 获取对应 API keys (如果需要)
3. 编辑 `~/.config/memos-graph/config.yaml`
4. 运行 `memos-graph server start`

**开始使用吧！** 🚀
