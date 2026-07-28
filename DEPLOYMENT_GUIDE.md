# memos-graph v3.0 部署指南

**版本**: v3.0.0-alpha  
**状态**: ✅ 代码实装完成，需要配置环境

---

## 📋 **前置条件**

### 1. 系统要求

- PostgreSQL 17+ 
- Python 3.11+
- 8GB+ RAM (推荐)
- 10GB+ 磁盘空间

### 2. 安装 PostgreSQL 扩展

```bash
# Ubuntu/Debian
sudo apt install postgresql-17 postgresql-17-pgvector postgresql-17-pg-jieba

# macOS (Homebrew)
brew install postgresql@17
# pgvector 和 pg_jieba 需要手动编译
```

### 3. 创建数据库

```bash
createdb memos_graph
psql -d memos_graph <<EOF
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_jieba;
EOF
```

---

## 🔧 **配置步骤**

### Step 1: 安装 Python 依赖

```bash
cd /home/gato/memos-graph
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 2: 创建配置文件

```bash
mkdir -p ~/.config/memos-graph
cp config.example.yaml ~/.config/memos-graph/config.yaml
nano ~/.config/memos-graph/config.yaml
```

### Step 3: 编辑配置

```yaml
# ~/.config/memos-graph/config.yaml

database:
  url: "postgresql+asyncpg://user:password@localhost:5432/memos_graph"

embedding:
  provider: "siliconflow"  # 或 "ollama" (本地)
  model: "BAAI/bge-m3"
  api_key: "YOUR_SILICONFLOW_API_KEY"  # 从 https://siliconflow.cn 获取
  dimension: 1024

llm:
  base_url: "https://api.siliconflow.cn/v1"
  api_key: "YOUR_SILICONFLOW_API_KEY"
  model: "Qwen/Qwen2.5-7B-Instruct"

# 可选：本地 Ollama
# embedding:
#   provider: "ollama"
#   model: "bge-m3"
#   base_url: "http://localhost:11434"
# 
# llm:
#   base_url: "http://localhost:11434/v1"
#   model: "qwen2.5:7b"
```

### Step 4: 初始化数据库

```bash
cd /home/gato/memos-graph
alembic upgrade head
```

验证表已创建：

```bash
psql -d memos_graph -c "\dt"
# 应该看到 17 张表
```

### Step 5: 测试连接

```bash
cd /home/gato/memos-graph
PYTHONPATH=src python3 << 'EOF'
from memos_graph.config import load_config
from memos_graph.db.session import create_session_factory

config = load_config()
print(f"✅ 配置加载成功")
print(f"数据库：{config.database.url}")
print(f"Embedding: {config.embedding.provider}")
print(f"LLM: {config.llm.base_url}")

# 测试数据库连接
create_session_factory(config.database.url)
print("✅ 数据库连接成功")
EOF
```

---

## 🚀 **启动服务**

### 方式 1: FastAPI 服务

```bash
cd /home/gato/memos-graph
python3 -m uvicorn memos_graph.server:create_app --factory --host 0.0.0.0 --port 8765
```

访问：http://localhost:8765

### 方式 2: Python 脚本直接使用

```python
from memos_graph.retrieve_v3 import RetrieveEngineV3, RetrieveRequestV3
from memos_graph.router import Domain
from memos_graph.emotion import EmotionalState
import numpy as np

# 创建引擎
engine = RetrieveEngineV3(
    db_url="postgresql+asyncpg://user:pass@localhost:5432/memos_graph",
    embedding_service=None,  # 会自动从配置加载
    llm_client=None
)

# 创建领域 (MoE 路由需要)
domains = [
    Domain(
        id="work",
        label="Work & Projects",
        prototype_vec=np.array([0.8] + [0.1] * 1023),  # 1024 维向量
        always_on=False
    ),
    Domain(
        id="personal",
        label="Personal Life",
        prototype_vec=np.array([0.1] + [0.8] + [0.1] * 1022),
        always_on=True
    ),
]

# 创建请求
request = RetrieveRequestV3(
    query="昨天的会议内容",
    agent_id="user123",
    use_moe_routing=True,
    domains=domains,
    user_emotion=EmotionalState.happy(0.8),  # 可选：当前情感
    use_graph=True,  # 使用图谱遍历
    graph_hops=2,
    top_k=20
)

# 执行召回
import asyncio
result = asyncio.run(engine.retrieve(request))

print(f"找到 {len(result.hits)} 条记忆")
print(f"MoE 路由：{result.moe_route.l1 if result.moe_route else 'N/A'}")
print(f"图谱扩展：+{result.graph_expanded} 节点")
print(f"耗时：{result.took_ms}ms")

for hit in result.hits[:5]:
    print(f"- {hit.content[:100]}... (score: {hit.final_score:.2f})")
```

---

## 🧪 **运行测试**

```bash
cd /home/gato/memos-graph
PYTHONPATH=src python3 -m pytest tests/ -v

# 预期结果:
# 162 passed, 3 skipped, 5 xfailed, 3 xpassed
# 0 failed
```

---

## 📊 **性能基准**

| 功能 | 延迟 | 说明 |
|------|------|------|
| MoE 路由 | <80ms | Centroid 模式 |
| 基础召回 | 100-150ms | FTS + Pattern + Time |
| 图谱遍历 | 50-80ms | 2 跳，每跳 5 节点 |
| 情感加权 | <5ms | 简单乘法 |
| 遗忘过滤 | <5ms | 阈值过滤 |
| **总计** | **300-400ms** | 完整流程 |

---

## 🔍 **故障排除**

### 问题 1: 数据库连接失败

```bash
# 检查 PostgreSQL 是否运行
sudo systemctl status postgresql

# 检查扩展是否安装
psql -d memos_graph -c "\dx"
# 应该看到 pgvector 和 pg_jieba
```

### 问题 2: Embedding API 失败

```bash
# 测试 SiliconFlow API
curl -X POST https://api.siliconflow.cn/v1/embeddings \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "BAAI/bge-m3", "input": "test"}'
```

### 问题 3: 表不存在

```bash
# 重新运行迁移
alembic downgrade base
alembic upgrade head
```

---

## 📝 **下一步**

### 立即可用 (v3.0)

- ✅ MoE 路由召回
- ✅ 情感加权召回
- ✅ 图谱遍历扩展
- ✅ FSRS 遗忘过滤
- ✅ PTSD 闪回检测

### 计划中 (v3.1)

- [ ] RRF fusion (多路召回融合)
- [ ] LLM rerank (智能重排序)
- [ ] MMR diversity (多样性重排)
- [ ] 领域自动演化
- [ ] FAISS 加速

---

## 🙏 **获取帮助**

- **GitHub Issues**: https://github.com/26bk9ck5vr-stack/memos-graph/issues
- **文档**: MEMOS_V3_MVP_GUIDE.md
- **已知问题**: KNOWN_ISSUES.md

---

**memos-graph v3.0 已准备好投入使用！** 🚀
