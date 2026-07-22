# MemOS 功能借鉴清单 - memos-graph v2.0 路线图

**分析日期**: 2026-07-22  
**分析方法**: 源码功能模块深度分析  
**目标**: 提取 MemOS 最值得借鉴的功能设计，指导 memos-graph v2.0 开发

---

## 📊 MemOS 核心功能架构

通过源码分析，MemOS 的核心功能可以归纳为：

```
MemOS 功能金字塔
        ▲
        │
    ┌───┴───┐
    │ 应用层 │ ← MemChat, MemAgent, Dream (应用)
    └───┬───┘
        │
    ┌───┴───┐
    │ 调度层 │ ← MemScheduler (异步任务调度)
    └───┬───┘
        │
    ┌───┴───┐
    │ 记忆层 │ ← MemCube (多记忆类型管理)
    └───┬───┘
        │
    ┌───┴───┐
    │ 存储层 │ ← Text/Activation/Parametric Memory (三种记忆)
    └───┬───┘
        │
    ┌───┴───┐
    │ 基础层 │ ← Embedder/LLM/GraphDB/VecDB (基础设施)
    └───────┘
```

---

## 🎯 最值得借鉴的 10 个功能设计

### 1. **三种记忆类型分离** ⭐⭐⭐⭐⭐

**MemOS 设计**:
```python
# src/memos/memories/
├── textual/      # 文本记忆 (语义记忆)
│   ├── TreeTextMemory      # 树状组织
│   ├── PreferenceMemory    # 用户偏好
│   └── NaiveMemory         # 简单实现
├── activation/   # 激活记忆 (短期工作记忆)
│   ├── KVMemory            # KV 存储
│   └── vLLMKVMemory        # vLLM 优化版
└── parametric/   # 参数记忆 (模型权重)
    └── LoRAMemory          # LoRA 微调
```

**设计理念**:
- **Textual Memory**: 长期语义记忆，可检索召回
- **Activation Memory**: 短期工作记忆，快速访问
- **Parametric Memory**: 模型参数记忆，技能固化

**memos-graph 借鉴**:
```python
# 当前 memos-graph 只有 Textual Memory
# v2.0 可以增加:

src/memos_graph/memories/
├── textual/      # ✅ 已有 (chunks + entities)
├── working/      # ⏳ 新增 (短期工作记忆)
│   └── kv_store.py  # Redis/内存 KV 存储
└── skills/       # ⏳ 新增 (技能记忆)
    └── skill_memory.py  # 常用对话模式固化
```

**实现优先级**: P1 (高)  
**工作量**: 2-3 周  
**价值**: 区分长短期记忆，提升响应速度

---

### 2. **MemCube 多记忆立方** ⭐⭐⭐⭐⭐

**MemOS 设计**:
```python
# src/memos/mem_cube/general.py
class GeneralMemCube:
    def __init__(self, config):
        self.text_mem: BaseTextMemory    # 文本记忆
        self.act_mem: BaseActMemory      # 激活记忆
        self.para_mem: BaseParaMemory    # 参数记忆
        self.pref_mem: BaseTextMemory    # 偏好记忆
    
    def load(self, dir: str):
        # 从目录加载所有记忆类型
        self.text_mem.load(dir)
        self.act_mem.load(dir)
        ...
    
    def dump(self, dir: str):
        # 导出所有记忆到目录
        self.text_mem.dump(dir)
        ...
```

**设计理念**:
- **封装**: 将多种记忆类型封装成一个"立方"
- **可移植**: 整个立方可以导出/导入
- **多用户**: 每个用户一个 MemCube
- **多场景**: 不同场景用不同 Cube

**memos-graph 借鉴**:
```python
# v2.0 新增 MemCube 概念

src/memos_graph/cube/
├── __init__.py
├── base.py          # BaseMemCube 抽象类
├── general.py       # GeneralMemCube 实现
└── manager.py       # 多 Cube 管理

# 使用示例:
cube = MemCube(user_id="user123")
cube.load("/path/to/user123/memory")
results = cube.search("query")
cube.dump()  # 保存
```

**实现优先级**: P0 (最高)  
**工作量**: 3-4 周  
**价值**: 支持多用户隔离，知识库管理

---

### 3. **树状记忆组织** ⭐⭐⭐⭐⭐

**MemOS 设计**:
```python
# src/memos/memories/textual/tree.py
class TreeTextMemory:
    def __init__(self, config):
        self.memory_manager = MemoryManager(
            graph_store=self.graph_store,
            embedder=self.embedder,
            extractor_llm=self.extractor_llm,
            memory_size={
                "WorkingMemory": 20,      # 工作记忆 20 条
                "LongTermMemory": 1500,   # 长期记忆 1500 条
                "UserMemory": 480,        # 用户记忆 480 条
            },
        )
    
    def add(self, memories):
        # LLM 自动组织到树状结构
        return self.memory_manager.add(memories)
    
    def search(self, query, top_k):
        # 树状遍历 + 多阶段召回
        searcher = self.get_searcher()
        return searcher.search(query, top_k)
```

**设计理念**:
- **层次化**: Topic → Concept → Fact 三层结构
- **自动组织**: LLM 自动分类新记忆
- **容量管理**: 每层有容量限制，自动整理
- **多粒度检索**: 可按层级检索

**memos-graph 借鉴**:
```python
# 当前 memos-graph 是扁平结构
# v2.0 可以升级为树状:

# 新增树状组织
src/memos_graph/memories/tree.py
├── Topic (主题层)     # 100 个主题
│   ├── Concept (概念层)  # 每个主题 10 个概念
│   │   └── Fact (事实层)   # 每个概念 50 个事实

# 容量管理:
# - Working Memory: 20 条 (最新)
# - Long-term Memory: 1500 条 (按重要性排序)
# - Archive: 无限 (冷存储)
```

**实现优先级**: P1 (高)  
**工作量**: 4-5 周  
**价值**: 提升检索精度，支持大规模记忆

---

### 4. **记忆反馈修正** ⭐⭐⭐⭐

**MemOS 设计**:
```python
# src/memos/mem_feedback/feedback.py (52KB!)
class MemoryFeedbackSystem:
    def __init__(self, config):
        self.feedback_llm = LLMFactory.from_config(config.llm)
        self.correction_strategy = config.strategy
    
    def correct(
        self,
        memory_id: str,
        feedback: str,  # 自然语言反馈
        user_id: str
    ) -> TextualMemoryItem:
        """
        用户：\"这个记忆不对，应该是...\"
        系统：自动修正记忆
        """
        # 1. 解析反馈
        correction = self.parse_feedback(feedback)
        
        # 2. 找到原记忆
        original = self.get_memory(memory_id)
        
        # 3. LLM 生成修正版本
        corrected = self.feedback_llm.generate(
            prompt=f"Original: {original}\nFeedback: {feedback}"
        )
        
        # 4. 更新记忆
        return self.update_memory(memory_id, corrected)
    
    def supplement(self, memory_id: str, supplement: str):
        """补充记忆细节\"\"\"
    
    def replace(self, memory_id: str, new_content: str):
        """完全替换记忆\"\""
```

**设计理念**:
- **自然语言反馈**: 用户用自然语言纠正
- **自动修正**: LLM 理解反馈并修正
- **版本管理**: 保留历史版本
- **置信度**: 修正后标记置信度

**memos-graph 借鉴**:
```python
# v2.0 新增记忆反馈

src/memos_graph/feedback/
├── __init__.py
├── parser.py        # 解析自然语言反馈
├── corrector.py     # 修正记忆
└── version.py       # 版本管理

# API 端点:
PUT /api/v1/memories/{id}/feedback
{
  "type": "correct",  # correct/supplement/replace
  "feedback": "这个记忆不对，应该是...",
  "confidence": 0.9
}
```

**实现优先级**: P2 (中)  
**工作量**: 2-3 周  
**价值**: 提升记忆质量，用户可纠正

---

### 5. **异步调度系统 (MemScheduler)** ⭐⭐⭐⭐⭐

**MemOS 设计**:
```python
# src/memos/mem_scheduler/ (12 个模块!)
├── task_schedule_modules/
│   ├── handlers/        # 任务处理器
│   └── scheduler.py     # 调度器
├── memory_manage_modules/  # 记忆管理
├── monitors/            # 监控
├── orm_modules/         # ORM
└── webservice_modules/  # Web 服务

# 核心功能:
- 异步任务队列
- 定时任务调度
- 记忆整理 (reorganize)
- 批量导入导出
- 监控告警
```

**设计理念**:
- **异步**: 不阻塞主线程
- **队列**: 任务排队处理
- **调度**: 定时/触发式执行
- **监控**: 实时任务状态

**memos-graph 借鉴**:
```python
# v2.0 新增异步调度

src/memos_graph/scheduler/
├── __init__.py
├── tasks/
│   ├── vector_gen.py   # 异步向量生成 (已有雏形)
│   ├── reorganize.py   # 定期整理记忆
│   ├── backup.py       # 定期备份
│   └── cleanup.py      # 清理过期记忆
├── queue.py           # 任务队列 (Redis/内存)
└── monitor.py         # 任务监控

# 使用示例:
scheduler.add_task(
    task="reorganize",
    schedule="0 3 * * *",  # 每天 3 点
    user_id="user123"
)
```

**实现优先级**: P1 (高)  
**工作量**: 3-4 周  
**价值**: 提升性能，支持大规模数据

---

### 6. **多模态记忆** ⭐⭐⭐⭐

**MemOS 设计**:
```python
# src/memos/mem_reader/read_multi_modal/
├── __init__.py
├── image_reader.py    # 图像记忆
├── audio_reader.py    # 音频记忆
├── tool_reader.py     # 工具调用记忆
└── persona_reader.py  # 人格记忆

# 支持:
- 文本 + 图像混合记忆
- 工具调用历史
- 人格特征记忆
```

**设计理念**:
- **多模态**: 不只是文本
- **统一表示**: 所有模态转为统一格式
- **混合检索**: 跨模态检索

**memos-graph 借鉴**:
```python
# v2.0 新增多模态 (可选)

src/memos_graph/multimodal/
├── image_memory.py    # 图像描述 + 向量
├── tool_memory.py     # 工具调用历史
└── persona_memory.py  # 人格特征

# 数据结构:
{
  "type": "image",
  "content": "图片描述文本",
  "image_url": "http://...",
  "embedding": [...],
  "metadata": {...}
}
```

**实现优先级**: P3 (低)  
**工作量**: 4-6 周  
**价值**: 扩展应用场景

---

### 7. **记忆组织管理器 (MemoryManager)** ⭐⭐⭐⭐

**MemOS 设计**:
```python
# src/memos/memories/textual/tree_text_memory/organize/manager.py
class MemoryManager:
    def __init__(
        self,
        graph_store,
        embedder,
        extractor_llm,
        memory_size: dict,  # 各层容量限制
        is_reorganize: bool
    ):
        self.memory_size = memory_size
        self.is_reorganize = is_reorganize
    
    def add(self, memories, user_name):
        # 1. LLM 提取关键信息
        # 2. 决定放入哪一层 (Working/Long-term/User)
        # 3. 如果该层满了，触发整理
        # 4. 返回记忆 ID
        
    def get_current_memory_size(self, user_name):
        # 返回当前各层记忆数量
        return {
            "WorkingMemory": 18/20,
            "LongTermMemory": 1450/1500,
            "UserMemory": 400/480
        }
    
    def reorganize(self, user_name):
        # 当某层满时触发:
        # 1. 合并相似记忆
        # 2. 删除不重要记忆
        # 3. 降级 (Working→Long-term)
```

**设计理念**:
- **容量管理**: 每层有明确限制
- **自动整理**: 满了自动整理
- **LLM 决策**: 用 LLM 决定记忆归类

**memos-graph 借鉴**:
```python
# v2.0 新增记忆管理器

src/memos_graph/manager/
├── __init__.py
├── memory_manager.py  # 记忆容量管理
└── reorganize.py      # 自动整理

# 容量配置:
{
  "working_memory_limit": 20,
  "longterm_memory_limit": 1500,
  "auto_reorganize": True,
  "reorganize_threshold": 0.9  # 90% 满时触发
}
```

**实现优先级**: P1 (高)  
**工作量**: 2-3 周  
**价值**: 自动管理记忆，防止爆炸

---

### 8. **多阶段搜索器 (AdvancedSearcher)** ⭐⭐⭐⭐⭐

**MemOS 设计**:
```python
# src/memos/memories/textual/tree_text_memory/retrieve/
├── searcher.py        # 高级搜索器
├── recall.py          # 多路召回
├── reranker.py        # 重排序
├── reasoner.py        # 推理合成
└── internet_retriever.py  # 互联网检索

# 搜索流程:
# 1. Query 解析 (LLM 理解意图)
# 2. 多路召回 (FTS + Vector + BM25 + Graph)
# 3. 重排序 (CrossEncoder)
# 4. 推理合成 (LLM 总结)
# 5. 可选：互联网检索增强
```

**设计理念**:
- **多阶段**: 召回→重排→推理
- **多策略**: 多种召回策略并行
- **可配置**: 可开关各阶段
- **互联网增强**: 可选外部检索

**memos-graph 借鉴**:
```python
# 当前 memos-graph 已有 7 阶段召回
# v2.0 可以增强:

src/memos_graph/search/
├── query_parser.py    # ⏳ 新增：LLM 解析查询意图
├── recall.py          # ✅ 已有：多路召回
├── reranker.py        # ✅ 已有：重排序
├── reasoner.py        # ⏳ 新增：LLM 推理合成
└── internet.py        # ⏳ 新增：互联网检索 (可选)

# 新增功能:
# 1. Query Parser: "昨天说的餐厅" → 解析时间/实体
# 2. Reasoner: 将召回结果合成为自然语言答案
# 3. Internet: 可选 Wikipedia/Google 检索
```

**实现优先级**: P1 (高)  
**工作量**: 3-4 周  
**价值**: 提升搜索智能度

---

### 9. **插件系统** ⭐⭐⭐

**MemOS 设计**:
```python
# src/memos/plugins/
├── base.py           # 插件基类
├── manager.py        # 插件管理器
└── hooks.py          # 生命周期钩子

# 插件类型:
- 记忆存储插件 (自定义后端)
- 召回策略插件 (自定义算法)
- LLM 插件 (自定义 provider)
- Embedder 插件 (自定义模型)
```

**设计理念**:
- **可扩展**: 不修改核心代码
- **钩子**: 生命周期钩子
- **热插拔**: 动态加载卸载

**memos-graph 借鉴**:
```python
# v2.0 新增插件系统

src/memos_graph/plugins/
├── __init__.py
├── base.py          # 插件基类
├── manager.py       # 插件管理
└── hooks/
    ├── on_add.py    # 添加记忆钩子
    ├── on_search.py # 搜索钩子
    └── on_dump.py   # 导出钩子

# 插件示例:
# - wechat_plugin: 微信消息自动存入
# - notion_plugin: Notion 同步
# - slack_plugin: Slack 集成
```

**实现优先级**: P2 (中)  
**工作量**: 2-3 周  
**价值**: 扩展生态

---

### 10. **类型系统** ⭐⭐⭐

**MemOS 设计**:
```python
# src/memos/types/
├── general_types.py
├── openai_chat_completion_types/
│   ├── chat_completion_user_message_param.py
│   ├── chat_completion_system_message_param.py
│   └── ... (完整 OpenAI 类型定义)
└── ...

# 设计理念:
- 完整类型注解
- IDE 友好
- 减少运行时错误
```

**memos-graph 借鉴**:
```python
# v2.0 增强类型系统

src/memos_graph/types/
├── __init__.py
├── memory.py        # 记忆相关类型
├── search.py        # 搜索相关类型
├── config.py        # 配置类型
└── api.py           # API 类型

# 当前 memos-graph 类型注解不完整
# v2.0 应该补全
```

**实现优先级**: P3 (低)  
**工作量**: 持续改进  
**价值**: 代码质量提升

---

## 📋 memos-graph v2.0 功能路线图

### P0 - 核心架构 (3-4 个月)

| 功能 | 工作量 | 优先级 | 状态 |
|------|--------|--------|------|
| **MemCube 多记忆立方** | 4 周 | P0 | ⏳ 待实现 |
| **树状记忆组织** | 5 周 | P0 | ⏳ 待实现 |
| **MemoryManager 容量管理** | 3 周 | P0 | ⏳ 待实现 |
| **异步调度系统** | 4 周 | P0 | ⏳ 待实现 |

**小计**: 16 周 ≈ 4 个月全职

---

### P1 - 增强功能 (2-3 个月)

| 功能 | 工作量 | 优先级 | 状态 |
|------|--------|--------|------|
| **三种记忆类型分离** | 3 周 | P1 | ⏳ 待实现 |
| **记忆反馈修正** | 3 周 | P1 | ⏳ 待实现 |
| **高级搜索器 (Query Parser + Reasoner)** | 4 周 | P1 | ⏳ 待实现 |
| **插件系统** | 3 周 | P1 | ⏳ 待实现 |

**小计**: 13 周 ≈ 3 个月全职

---

### P2 - 扩展功能 (可选)

| 功能 | 工作量 | 优先级 | 状态 |
|------|--------|--------|------|
| **多模态记忆** | 6 周 | P2 | ⏳ 可选 |
| **互联网检索增强** | 2 周 | P2 | ⏳ 可选 |
| **完整类型系统** | 持续 | P2 | ⏳ 持续改进 |

---

## 💡 实施建议

### 阶段 1: 先做 MemCube (4 周)

**为什么**:
- ✅ 支持多用户隔离 (生产必需)
- ✅ 封装复杂度 (API 简洁)
- ✅ 为其他功能打基础

**怎么做**:
```python
# 第 1 周：设计 API
class BaseMemCube(ABC):
    @abstractmethod
    def search(self, query, top_k) -> list[MemoryItem]
    @abstractmethod
    def add(self, memory: MemoryItem) -> str
    @abstractmethod
    def load(self, dir: str)
    @abstractmethod
    def dump(self, dir: str)

# 第 2 周：实现 GeneralMemCube
class GeneralMemCube(BaseMemCube):
    def __init__(self, user_id: str, config: Config):
        self.user_id = user_id
        self.config = config
        # 初始化各种记忆...

# 第 3 周：集成到现有 API
@app.post("/api/v1/cubes")
def create_cube(user_id: str):
    cube = GeneralMemCube(user_id, config)
    return {"cube_id": user_id}

# 第 4 周：测试 + 文档
```

---

### 阶段 2: 树状组织 (5 周)

**为什么**:
- ✅ 支持大规模记忆 (10 万+)
- ✅ 提升检索精度
- ✅ 自动整理，防止爆炸

**怎么做**:
```python
# 借鉴 MemOS 的 TreeTextMemory
# 但简化实现:
# - Topic → Concept → Fact 三层
# - LLM 自动分类
# - 容量管理
```

---

### 阶段 3: 异步调度 (4 周)

**为什么**:
- ✅ 提升性能
- ✅ 支持后台任务
- ✅ 定期整理/备份

**怎么做**:
```python
# 使用 Celery 或 RQ
# 或者简单的 asyncio.Queue + 后台任务
```

---

## 🎯 总结

### MemOS 最值得借鉴的设计思想

1. **分层架构**: 存储层→记忆层→调度层→应用层
2. **三种记忆**: Textual/Activation/Parametric
3. **MemCube 封装**: 多记忆类型统一管理
4. **树状组织**: Topic→Concept→Fact
5. **容量管理**: 每层有限制，自动整理
6. **反馈修正**: 自然语言纠正记忆
7. **异步调度**: 不阻塞主线程
8. **多阶段搜索**: 召回→重排→推理

### memos-graph 的实施策略

**不要**:
- ❌ 一次性实现所有功能
- ❌ 追求大而全
- ❌ 过度工程化

**要**:
- ✅ 小步快跑，迭代开发
- ✅ 先做核心 (MemCube + 树状)
- ✅ 保持简单 (MemOS 的 1/3 复杂度即可)
- ✅ 中文优化 (pg_jieba 是优势)

### 最终目标

**memos-graph v2.0 = MemOS 的核心功能 × 1/3 复杂度 × 中文优化**

---

**分析生成**: Hermes Agent  
**日期**: 2026-07-22  
**版本**: v7.0 (功能借鉴版)
