# AIRI 记忆架构深度分析

**分析日期**: 2026-07-28  
**项目**: flamingo15490/airi-nahida (1⭐, AIRI 定制分支)  
**原始项目**: moeru-ai/airi (AIRI 主项目)  
**核心焦点**: 外部记忆架构 (External Memory) + 情绪加权 + 遗忘曲线

---

## 📊 **项目概览**

### AIRI 是什么？

**AIRI** = 一个**桌面 AI 伴侣框架**，支持：
- ✅ 本地优先 (Local-first)
- ✅ 多模态 (语音/视觉/文本)
- ✅ 外部记忆集成
- ✅ 主动陪伴 (Proactive Companion)
- ✅ 角色定制 (Nahida 等)

**airi-nahida** = AIRI 的定制分支，专注于：
- Nahida 风格的角色定制
- 外部记忆集成 (`D:\AIRI-Memory`)
- 更稳定的桌面体验

---

## 🧠 **AIRI 的记忆架构：外部记忆模式**

### 核心设计

> **AIRI 的记忆不在代码内，而在代码外！**

```
AIRI 应用 (代码)
    ↓ (读写)
外部记忆目录 (D:\AIRI-Memory/)
    ├── 用户信息.md       # user-profile
    ├── 偏好设置.md       # preferences
    ├── 待跟进.md         # follow-ups
    ├── 最近总结.md       # recent-summary
    └── 角色知识.md       # character-knowledge
```

**关键洞察**:
- ✅ **记忆与应用分离**: 记忆是外部文件，不是数据库
- ✅ **人类可读**: Markdown 格式，可手动编辑
- ✅ **版本控制友好**: Git 可追踪变化
- ✅ **跨应用共享**: 多个 AI 应用可共享同一记忆目录

---

## 📁 **外部记忆的 5 种文档类型**

### 1. **user-profile (用户信息)**

```markdown
# 用户信息

- 姓名：XXX
- 职业：程序员
- 所在地：北京
- 生日：1990-01-01
```

**特点**:
- ✅ 稳定的用户事实
- ✅ 不常变化
- ✅ 高置信度

---

### 2. **preferences (偏好设置)**

```markdown
# 偏好设置

- 喜欢浅色主题
- 不喜欢深色模式
- 喜欢川菜
- 音乐偏好：摇滚
```

**特点**:
- ✅ 用户偏好
- ✅ 可随时间变化
- ✅ 中等置信度

---

### 3. **follow-ups (待跟进)**

```markdown
# 待跟进

- [ ] 下周提醒用户体检
- [ ] 用户说想看某部电影
- [ ] 用户生日快到了 (2026-08-15)
```

**特点**:
- ✅ 临时性任务
- ✅ 有生命周期 (完成后删除)
- ✅ 低置信度 (可能取消)

---

### 4. **recent-summary (最近总结)**

```markdown
# 最近总结 (2026-07-28)

- 今天讨论了晚餐吃什么
- 用户决定去朝阳区的川菜馆
- 聊得很开心
```

**特点**:
- ✅ 短期记忆
- ✅ 滚动更新 (保留最近 N 天)
- ✅ 用于上下文连续性

---

### 5. **character-knowledge (角色知识)**

```markdown
# Nahida 角色知识

- 喜欢甜食
- 害怕虫子
- 擅长烘焙
- 称呼用户为"旅行者"
```

**特点**:
- ✅ 角色特定知识
- ✅ 不同角色有不同的知识
- ✅ 用于角色一致性

---

## 🔄 **记忆读写流程**

### 读取流程 (Read Path)

```typescript
// external-memory.ts
function composeExternalMemorySupplement(params) {
  const context = params.context  // 从外部目录读取
  const usage = params.usage
  
  // 1. 检查记忆桥是否可用
  if (!context || context.usedKinds.length === 0) {
    return '[External Memory Guardrail]\n' +
           'Trusted external memory is not available for this turn.'
  }
  
  // 2. 构建记忆补充
  const sections = [
    '[External Memory Context]',
    'Use the following memory only when it is directly relevant.',
  ]
  
  // 3. 按类型追加
  if (context.sections.userProfile.length > 0) {
    sections.push('', 'Stable user profile:', 
                  quoteBullets(context.sections.userProfile))
  }
  
  if (context.sections.preferences.length > 0) {
    sections.push('', 'Known preferences:', 
                  quoteBullets(context.sections.preferences))
  }
  
  if (context.sections.followUps.length > 0) {
    sections.push('', 'Open follow-ups:', 
                  quoteBullets(context.sections.followUps))
  }
  
  if (context.sections.recentSummary.length > 0) {
    sections.push('', 'Recent continuity:', 
                  quoteBullets(context.sections.recentSummary))
  }
  
  return sections.join('\n')
}
```

**效果**:
```
[External Memory Context]
Use the following memory only when it is directly relevant.

Stable user profile:
- 姓名：XXX
- 职业：程序员

Known preferences and boundaries:
- 喜欢浅色主题
- 不喜欢深色模式

Open follow-ups:
- [ ] 下周提醒用户体检

Recent continuity:
- 今天讨论了晚餐吃什么
- 用户决定去朝阳区的川菜馆
```

---

### 写入流程 (Write Path)

```typescript
// external-memory-shared.ts
interface ExternalMemoryWriteRequest {
  source?: string           // 来源 (manual/automatic)
  characterName?: string    // 角色名
  summary?: string          // 最近总结
  facts?: string[]          // 用户事实
  preferences?: string[]    // 偏好
  items?: string[]          // 待跟进事项
  removeItems?: string[]    // 删除的事项
}

// 写入决策
type ExternalMemoryWriteDecision = 
  | 'written'               // 已写入
  | 'skipped-unavailable'   // 记忆不可用
  | 'skipped-empty'         // 空内容
  | 'skipped-duplicate'     // 重复内容
  | 'skipped-not-stable'    // 不够稳定 (不写入长期记忆)
```

**写入规则**:
- ✅ **去重**: 不写入重复内容
- ✅ **稳定性检查**: 不稳定的事实不写入长期记忆
- ✅ **合并**: 新内容与旧内容合并
- ✅ **滚动**: recent-summary 保留最近 N 条

---

## 📈 **记忆检索与排序 (AIRI 的核心创新)**

根据 AIRI 的开发日志 (DevLog 2025.04.14)，AIRI 实现了一个**复杂的记忆检索系统**：

### 两阶段排序

```
搜索引擎
├── 基础排序 (粗排) - 海选
│   └── 快速筛选 TOP N
└── 业务排序 (精排) - 精细算分
    └── 返回最优结果
```

### 排序因子

#### 1. **语义相似度 (Similarity)**

```sql
-- 余弦相似度 (cosine similarity)
similarity = cosine_distance(query_vector, memory_vector)
-- 取值 0-1，越高越相关
```

#### 2. **时间相关度 (Temporal Relevance)**

```sql
-- 越新越相关
time_relevance = exp(-days_since_created / decay_rate)
-- 半衰期：7 天 (7 天后分数减半)
```

#### 3. **召回次数 (Retrieval Count)**

```sql
-- 常被召回的记忆更重要
retrieval_boost = log10(retrieval_count + 1)
```

#### 4. **情感加权 (Emotional Weight)**

```sql
-- 情感强烈的记忆更难忘
emotional_boost = (joy_score - sadness_score) * 0.2
-- 开心的记忆强化，难过的记忆抑制
```

### 最终排序公式

```sql
final_score = 
  (1.2 * similarity) +           -- 语义相关 (1.2x)
  (0.2 * time_relevance) +       -- 时间相关 (0.2x)
  (0.1 * retrieval_boost) +      -- 召回次数 (0.1x)
  (0.2 * emotional_boost)        -- 情感加权 (0.2x)
```

**关键设计**:
- ✅ **无状态**: 不需要实时更新分数，查询时计算
- ✅ **可调节**: 权重参数 (1.2, 0.2) 可调
- ✅ **多因子**: 综合考虑语义/时间/频率/情感

---

## 😊 **情绪模型 (Emotional Model)**

AIRI 实现了一个**情绪加权记忆系统**：

### 情绪分数

```typescript
interface EmotionalScore {
  joy: number       // 欢欣 (0-1)
  sadness: number   // 悲伤 (0-1)
  anger: number     // 愤怒 (0-1)
  fear: number      // 恐惧 (0-1)
  disgust: number   // 厌恶 (0-1)
}
```

### 情绪对记忆的影响

```
开心记忆 (joy > 0.5):
  → 强化 (分数 +0.2)
  → 更容易召回

难过记忆 (sadness > 0.5):
  → 抑制 (分数 -0.1)
  → 不容易主动想起

创伤记忆 (fear > 0.7):
  → 压抑 (平时分数很低)
  → 但可能"闪回"(随机触发)
```

### PTSD 模拟

```typescript
// 创伤记忆的随机闪回
if (memory.fear > 0.7 && Math.random() < 0.05) {
  // 5% 概率突然想起创伤记忆
  triggerFlashback(memory)
}
```

**关键洞察**:
- ✅ 情绪影响记忆强度
- ✅ 创伤记忆会"闪回"
- ✅ 符合心理学研究

---

## 📉 **遗忘曲线 (Forgetting Curve)**

AIRI 实现了**艾宾浩斯遗忘曲线**的简化版：

### 半衰期模型

```typescript
// 记忆分数随时间衰减
function applyDecay(memory, now) {
  const days = daysBetween(memory.created_at, now)
  const halfLife = 7  // 7 天半衰期
  
  // 遗忘函数
  const decayFactor = Math.pow(0.5, days / halfLife)
  
  // 当前分数
  memory.current_score = memory.original_score * decayFactor
  
  return memory
}
```

**效果**:
```
第 0 天：分数 = 1.0
第 7 天：分数 = 0.5 (半衰期)
第 14 天：分数 = 0.25
第 21 天：分数 = 0.125
```

### 记忆强化

```typescript
// 每次召回强化记忆
function reinforce(memory) {
  memory.retrieval_count += 1
  
  // 强化原始分数
  memory.original_score *= 1.1
  
  // 延长半衰期
  memory.half_life *= 1.2
}
```

**关键设计**:
- ✅ **无状态**: 不需要定时任务更新分数
- ✅ **查询时计算**: 根据当前时间求遗忘函数
- ✅ **强化机制**: 常被召回的记忆更难忘

---

## 🆚 **AIRI vs Nemos vs memos-graph**

| 维度 | AIRI (外部记忆) | Nemos (5 层引擎) | memos-graph (图谱) |
|------|----------------|-----------------|-------------------|
| **存储位置** | 外部 Markdown 文件 | 内部数据库 (SQLite) | 内部数据库 (PostgreSQL) |
| **记忆结构** | 5 种文档类型 | 5 层分层模型 | 图谱 (节点 + 关系) |
| **人类可读** | ✅ 完全可读 | ⚠️ 需工具查看 | ⚠️ 需工具查看 |
| **手动编辑** | ✅ 可直接编辑 | ❌ 需 API | ❌ 需 API |
| **版本控制** | ✅ Git 友好 | ⚠️ 数据库导出 | ⚠️ 数据库导出 |
| **跨应用共享** | ✅ 共享目录 | ❌ 应用独占 | ❌ 应用独占 |
| **检索方式** | 向量 + 多因子排序 | MoE 路由 + 向量 | 图谱遍历 + 向量 |
| **情感加权** | ✅ 5 种情绪分数 | ✅ arousal (0-1) | ✅ 情感节点 |
| **遗忘曲线** | ✅ 半衰期模型 | ✅ FSRS 简化版 | ⏳ 时间衰减 |
| **矛盾失效** | ❌ 未明确 | ✅ 双时间轴 | ⏳ 可学习 |
| **防污染** | ⚠️ 稳定性检查 | ✅ 硬约束 | ⏳ 可学习 |
| **多跳推理** | ❌ 无 | ⚠️ 一跳跨域 | ✅ 多跳 |
| **指代消解** | ❌ 无 | ⏳ 未明确 | ✅ 关系定位 |

---

## 💡 **AIRI 的优缺点**

### ✅ 优点

1. **简单优雅**: 外部 Markdown 文件，人类可读
2. **解耦设计**: 记忆与应用分离，可独立演进
3. **跨应用共享**: 多个 AI 应用可共享同一记忆目录
4. **版本控制**: Git 可追踪记忆变化
5. **手动编辑**: 用户可直接编辑记忆文件
6. **情绪加权**: 5 种情绪分数，符合心理学
7. **遗忘曲线**: 半衰期模型，简单有效
8. **多因子排序**: 语义 + 时间 + 频率 + 情感

### ❌ 缺点

1. **扁平结构**: 5 种文档类型是独立的，没有关联
2. **无图谱**: 无法多跳推理 (从 A→B→C)
3. **无矛盾处理**: 新旧事实冲突时无法自动失效
4. **无防污染**: 依赖"稳定性检查"，不是硬约束
5. **无分层**: 没有 archival/episodic/semantic 分层
6. **检索简单**: 只有向量相似度，没有 MoE 路由
7. **无指代消解**: "那家餐厅"无法定位

---

## 🎯 **AIRI 给 memos-graph 的启发**

### ✅ 学习 AIRI 的优点

1. **外部记忆目录**
   ```
   memos-graph/
   └── memory/
       ├── user-profile.md
       ├── preferences.md
       ├── follow-ups.md
       └── recent-summaries/
   ```

2. **情绪加权**
   ```python
   class EmotionalScore:
       joy: float      # 欢欣
       sadness: float  # 悲伤
       anger: float    # 愤怒
       fear: float     # 恐惧
       disgust: float  # 厌恶
   ```

3. **多因子排序**
   ```python
   final_score = (
       1.2 * similarity +      # 语义
       0.2 * time_relevance +  # 时间
       0.1 * retrieval_boost + # 频率
       0.2 * emotional_boost   # 情感
   )
   ```

4. **半衰期遗忘**
   ```python
   decay_factor = pow(0.5, days / half_life)
   current_score = original_score * decay_factor
   ```

### ❌ 避免 AIRI 的缺点

1. **不要扁平结构** → 坚持图谱 (节点 + 关系)
2. **不要无分层** → 采用 Nemos 的 5 层模型
3. **不要无矛盾处理** → 采用 Nemos 的双时间轴
4. **不要无防污染** → 采用 Nemos 的硬约束

---

## 🚀 **memos-graph v3.0 设计**

```
memos-graph v3.0 = Nemos 5 层 + 图谱 + AIRI 情绪加权

具体:
✅ 采用 Nemos 的 LAYERS (archival/episodic/semantic/personal/procedural)
✅ 采用 Nemos 的矛盾失效 (双时间轴)
✅ 采用 Nemos 的防污染 (authoritative 硬约束)
✅ 保留 memos-graph 的图谱 (多跳推理/指代消解)
✅ 采用 AIRI 的情绪加权 (5 种情绪分数)
✅ 采用 AIRI 的多因子排序 (语义 + 时间 + 频率 + 情感)
✅ 采用 AIRI 的半衰期遗忘 (简单有效)
✅ 新增外部记忆目录 (人类可读，Git 友好)
```

### Schema 设计

```sql
-- 记忆节点
CREATE TABLE memory_nodes (
    id UUID PRIMARY KEY,
    layer TEXT CHECK (layer IN ('archival', 'episodic', 'semantic', 'personal_semantic', 'procedural')),
    content TEXT,
    
    -- 情感加权 (AIRI)
    joy FLOAT DEFAULT 0,
    sadness FLOAT DEFAULT 0,
    anger FLOAT DEFAULT 0,
    fear FLOAT DEFAULT 0,
    disgust FLOAT DEFAULT 0,
    
    -- 遗忘曲线 (AIRI)
    original_score FLOAT DEFAULT 1.0,
    half_life_days INT DEFAULT 7,
    retrieval_count INT DEFAULT 0,
    
    -- 双时间轴 (Nemos)
    valid_at TIMESTAMP,
    invalidated_at TIMESTAMP,
    invalidation_reason TEXT,
    
    -- 防污染 (Nemos)
    authoritative BOOLEAN DEFAULT FALSE,
    chain_depth INT DEFAULT 0
);

-- 记忆关系 (图谱)
CREATE TABLE memory_edges (
    from_node UUID REFERENCES memory_nodes(id),
    to_node UUID REFERENCES memory_nodes(id),
    relation_type TEXT,
    strength FLOAT
);

-- 外部记忆目录 (AIRI)
-- memory/user-profile.md
-- memory/preferences.md
-- memory/follow-ups.md
```

### 检索流程

```python
async def retrieve(query: str, top_k: int = 20):
    # 1. MoE 路由 (Nemos)
    route = router.route(query)
    
    # 2. 层内检索
    memories = search_in_layers(route.layers, query)
    
    # 3. 图谱多跳 (memos-graph)
    expanded = graph_traverse(memories, max_hops=3)
    
    # 4. 多因子排序 (AIRI)
    for mem in expanded:
        mem.final_score = (
            1.2 * mem.similarity +
            0.2 * mem.time_relevance +
            0.1 * log(mem.retrieval_count + 1) +
            0.2 * mem.emotional_boost
        )
    
    # 5. 遗忘衰减 (AIRI)
    for mem in expanded:
        days = days_between(mem.created_at, now)
        decay = pow(0.5, days / mem.half_life_days)
        mem.final_score *= decay
    
    # 6. 过滤失效 (Nemos)
    valid = [m for m in expanded if not m.invalidated_at]
    
    # 7. 返回 TOP K
    return sorted(valid, key=lambda m: m.final_score, reverse=True)[:top_k]
```

---

## 💬 **结论**

### AIRI 是什么？

> **AIRI = 外部记忆架构 + 情绪加权 + 遗忘曲线**

- ✅ **外部记忆**: Markdown 文件，人类可读
- ✅ **情绪加权**: 5 种情绪分数
- ✅ **遗忘曲线**: 半衰期模型
- ✅ **多因子排序**: 语义 + 时间 + 频率 + 情感

### memos-graph 的机会？

**融合三家之长**:

```
memos-graph v3.0 = 
  Nemos 的 5 层模型 +          # 结构化
  Nemos 的矛盾失效 +          # 可靠性
  Nemos 的防污染 +            # 权威性
  memos-graph 的图谱 +        # 多跳推理
  AIRI 的情绪加权 +           # 情感
  AIRI 的多因子排序 +         # 精准检索
  AIRI 的半衰期遗忘 +         # 自然遗忘
  AIRI 的外部记忆目录         # 人类可读
```

**这样做出来的记忆引擎，将超越所有现有项目！** 🚀

---

**下一步行动**:

1. **设计 v3.0 Schema** (融合三家之长)
2. **实现情绪加权** (5 种情绪分数)
3. **实现多因子排序** (语义 + 时间 + 频率 + 情感)
4. **实现半衰期遗忘** (简单有效)
5. **创建外部记忆目录** (人类可读)
6. **测试 MnemoBench** (验证效果)

**站在巨人的肩膀上，做得更深、更远！** 🚀
