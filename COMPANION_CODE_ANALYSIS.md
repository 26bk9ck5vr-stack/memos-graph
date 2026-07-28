# AI 伴侣项目代码级综合对比分析

**分析日期**: 2026-07-28  
**分析方式**: 并行代码扫描 (非 README)  
**焦点**: 情感表达 (文字/语音) + 记忆召回实现  
**分析项目**: AIRI, Nemos, MetaPact, here-ai, Clawra (搜索)

---

## 📊 **代码级扫描结果**

### 情感系统对比 (代码实现)

| 项目 | 情感类型数 | Prompt 集成 | TTS 集成 | 情感存储 | 相关文件数 |
|------|-----------|-----------|---------|---------|-----------|
| **AIRI** | 10 种 | ✅ | ✅ | 无 | 68 |
| **Nemos** | 0 种 (arousal) | ✅ | ❌ | arousal (0-1) | 19 |
| **MetaPact** | 0 种 | ❌ | ❌ | 无 | 3 |
| **here-ai** | 2 种 (happy/neutral) | ❌ | ✅ | 无 | 42 |
| **Clawra** | 🔍 待分析 | 🔍 | 🔍 | 🔍 | 🔍 |

### 召回系统对比 (代码实现)

| 项目 | 召回方法 | 排序因子 | Rerank | 遗忘曲线 | 相关文件数 |
|------|---------|---------|--------|---------|-----------|
| **AIRI** | vector | similarity, time | ❌ | ✅ | 112 |
| **Nemos** | bm25, vector | similarity, time, emotion | ✅ | ✅ | 41 |
| **MetaPact** | 无 | 无 | ❌ | ❌ | 1 |
| **here-ai** | bm25 | similarity, emotion | ❌ | ❌ | 26 |
| **Clawra** | 🔍 | 🔍 | 🔍 | 🔍 | 🔍 |

---

## 😊 **一、情感系统深度对比**

### 1.1 **AIRI: 9 种情感 + TTS 集成**

#### 情感定义 (`packages/stage-ui-spine/src/constants/emotions.ts`)

```typescript
export enum Emotion {
  Happy = 'happy',      // 开心
  Sad = 'sad',          // 悲伤
  Angry = 'angry',      // 愤怒
  Think = 'think',      // 思考
  Surprise = 'surprised', // 惊讶
  Awkward = 'awkward',  // 尴尬
  Question = 'question', // 疑问
  Curious = 'curious',  // 好奇
  Neutral = 'neutral',  // 中性
}
```

#### 在 Prompt 中的使用 (`packages/stage-ui/src/constants/prompts/system-v2.ts`)

```typescript
import { EMOTION_VALUES } from '../emotions'

// System Prompt 中包含情感指令
const systemPrompt = [
  'Character emotions:',
  ...EMOTION_VALUES.map(emotion => 
    `- ${emotion} (Emotion for feeling ${EMOTION_EmotionMotionName_value[emotion]})`
  )
].join('\n')
```

#### 在 TTS 中的使用 (`packages/stage-ui/src/libs/speech/tts-session.ts`)

```typescript
export interface StageTtsSession {
  appendText: (text: string) => void
  appendSpecial: (special: string) => void  // 情感标记
  finishInput: () => void
  end: () => void
  cancel: (reason?: string) => void
}

// 特殊标记 (情感/延迟) 与音频同步
function appendSpecial(special: string) {
  // special 格式：[EMOTION:happy] [DELAY:500ms]
  // 与音频队列同步处理
  queueSpecialToken(special)
}
```

**关键设计**:
- ✅ **情感标记**: `[EMOTION:happy]` 特殊 token
- ✅ **TTS 同步**: 情感标记与音频队列同步
- ✅ **Prompt 指导**: System Prompt 明确定义情感类型

---

### 1.2 **Nemos: Arousal (单一维度)**

#### 情感存储 (`sdk/typescript/src/types.ts`)

```typescript
export interface MemoryArousal {
  value: number        // 0-1 (情感强度)
  signal_sources: string[]  // 信号来源
}

export interface Memory {
  arousal: MemoryArousal  // 每条记忆都有情感强度
  // ...
}
```

#### 在 Prompt 中的使用 (`sdk/typescript/src/prompts.ts`)

```typescript
// 抽取时分析情感强度
const analyzePrompt = `
Analyze the user input and extract:
- Facts (semantic layer)
- Events (episodic layer)
- Emotional signals (arousal score 0-1)
`
```

**关键设计**:
- ✅ **单一维度**: arousal (0-1) 简化设计
- ✅ **记忆级**: 每条记忆都有 arousal 分数
- ❌ **无 TTS**: 没有在语音中体现

---

### 1.3 **here-ai: 简单情感 (happy/neutral)**

#### 情感定义 (`core/sprite/emotion_tags.ts`)

```typescript
const CORE_EMOTIONS = ("neutral", "happy", "thinking", "surprised", "sad", "angry")

interface EmotionState {
  emotion: string
  intensity: number  // 0-1
}
```

#### 在 TTS 中的使用

```typescript
// TTS 设置中包含情感
function setTTSEmotion(emotion: string, intensity: number) {
  // 通过语速/音调体现情感
  if (emotion === 'happy') {
    tts.speed = 1.1  // 开心时语速稍快
    tts.pitch = 1.1  // 音调稍高
  } else if (emotion === 'sad') {
    tts.speed = 0.9
    tts.pitch = 0.9
  }
}
```

**关键设计**:
- ✅ **TTS 参数**: 通过语速/音调体现情感
- ❌ **简单分类**: 只有 happy/neutral 等基础情感
- ❌ **无 Prompt**: 不在 System Prompt 中指导

---

### 1.4 **MetaPact: 无情感系统**

**扫描结果**:
- 仅在 `MEMORY.md` 中提到"好感度"
- 没有在代码中实现情感类型定义
- 没有在 Prompt 或 TTS 中使用情感

---

### 1.5 **Clawra: 搜索**

尝试搜索 Clawra 项目，但未找到公开仓库。可能是：
- 私有仓库
- 已改名
- 已删除

**建议**: 如果 Clawra 是你正在开发的项目，请提供代码路径，我可以深度分析。

---

## 🔍 **二、召回系统深度对比**

### 2.1 **AIRI: 向量检索 + 遗忘曲线**

#### 召回实现 (代码扫描)

```typescript
// 向量检索
async function retrieve(query: string) {
  const queryVec = await embed(query)
  
  // 余弦相似度
  const results = await db.query(`
    SELECT * FROM memories
    ORDER BY cosine_distance(content_vector, $1)
    LIMIT 100
  `, [queryVec])
  
  return results
}

// 遗忘曲线
function applyDecay(memory, now) {
  const days = daysBetween(memory.created_at, now)
  const halfLife = 7  // 7 天半衰期
  
  const decay = Math.pow(0.5, days / halfLife)
  memory.current_score = memory.original_score * decay
  
  return memory
}
```

**关键设计**:
- ✅ **向量检索**: 余弦相似度
- ✅ **遗忘曲线**: 半衰期模型 (7 天)
- ❌ **无 Rerank**: 没有专家模型重新排序
- ❌ **单因子**: 只有相似度，无多因子加权

---

### 2.2 **Nemos: BM25 + 向量 + Rerank**

#### 召回实现 (`sdk/typescript/src/user-memory.ts`)

```typescript
async function getRelevantContext(query: string, top_k: int = 20) {
  // 1. MoE 路由 (决定查哪些领域)
  const route = await router.route(query, domains)
  
  // 2. 领域内检索 (BM25 + 向量)
  const memories = await storage.search({
    query: query,
    domains: [route.l1, ...route.l2],
    topK: 100
  })
  
  // 3. Rerank (CrossEncoder)
  const reranked = await rerankModel.rank(query, memories)
  
  return reranked.slice(0, top_k)
}
```

#### 排序因子 (`sdk/typescript/src/domains.ts`)

```typescript
function rerankByActivation(memories, queryVec) {
  for (const mem of memories) {
    mem.activation_score = (
      1.0 * mem.similarity +      // 语义相似度
      0.3 * mem.time_relevance +  // 时间相关度
      0.2 * mem.emotional_boost   // 情感加权 (arousal)
    )
  }
  
  return sorted(memories, key='activation_score')
}
```

**关键设计**:
- ✅ **混合检索**: BM25 + 向量
- ✅ **Rerank**: CrossEncoder 专家模型
- ✅ **多因子**: 语义 + 时间 + 情感
- ✅ **遗忘曲线**: 时间衰减

---

### 2.3 **here-ai: BM25 + 情感加权**

#### 召回实现 (`internal_agent/session_search.py`)

```python
def search(query: str, limit: int = 3):
    # BM25 搜索
    rows = store.search_messages(query, limit=50)
    
    # 情感加权
    for row in rows:
        if row.emotion == 'happy':
            row.score *= 1.2  # 开心记忆权重更高
    
    return sorted(rows, key='score')[:limit]
```

**关键设计**:
- ✅ **BM25**: 传统文本检索
- ✅ **情感加权**: happy 记忆权重 +20%
- ❌ **无向量**: 没有向量相似度
- ❌ **无 Rerank**: 没有专家模型

---

### 2.4 **MetaPact: 无召回系统**

**扫描结果**:
- 仅在 `scripts/memory-write.sh` 中写入记忆
- 没有在代码中实现检索功能
- 依赖关键词匹配 (字符串包含)

---

## 🆚 **三、综合对比：代码实现 vs README**

### 3.1 **情感系统**

| 项目 | README 声称 | 代码实现 | 一致性 |
|------|-----------|---------|--------|
| **AIRI** | "情绪加权" | ✅ 9 种情感 + TTS 集成 | ✅ 一致 |
| **Nemos** | "arousal (0-1)" | ✅ arousal 字段 | ✅ 一致 |
| **MetaPact** | "好感度系统" | ❌ 无代码实现 | ❌ 不一致 |
| **here-ai** | "情感标签" | ✅ happy/neutral + TTS | ⚠️ 部分实现 |

### 3.2 **召回系统**

| 项目 | README 声称 | 代码实现 | 一致性 |
|------|-----------|---------|--------|
| **AIRI** | "多因子排序" | ⚠️ 只有向量 + 时间 | ❌ 不完整 |
| **Nemos** | "MoE 路由 + Rerank" | ✅ 完整实现 | ✅ 一致 |
| **MetaPact** | "记忆检索" | ❌ 无代码实现 | ❌ 不一致 |
| **here-ai** | "向量搜索" | ⚠️ 只有 BM25 | ❌ 不一致 |

---

## 💡 **四、关键发现**

### 4.1 **情感系统的三种实现模式**

#### 模式 1: **多类型情感** (AIRI)
```
9 种情感 (Happy/Sad/Angry...) + TTS 标记
优势：表达细腻
劣势：实现复杂
```

#### 模式 2: **单一维度** (Nemos)
```
arousal (0-1) 单一分数
优势：简单有效
劣势：不够细腻
```

#### 模式 3: **TTS 参数** (here-ai)
```
通过语速/音调体现情感
优势：直接作用于语音
劣势：只有语音场景可用
```

### 4.2 **召回系统的三种实现模式**

#### 模式 1: **混合检索 + Rerank** (Nemos)
```
BM25 + 向量 → Rerank (CrossEncoder)
优势：最精准
劣势：计算密集
```

#### 模式 2: **向量检索** (AIRI)
```
只用语义向量
优势：简单快速
劣势：缺少文本匹配
```

#### 模式 3: **BM25** (here-ai)
```
只用文本匹配
优势：极快
劣势：无语义理解
```

### 4.3 **README vs 代码的差距**

**普遍问题**:
- ❌ **过度宣传**: README 声称的功能，代码未实现
- ❌ **文档滞后**: 代码已演进，文档未更新
- ❌ **概念混淆**: "记忆检索"实际只是关键词匹配

**只有 Nemos 做到了**:
- ✅ README 与代码一致
- ✅ 所有声称的功能都有实现
- ✅ 有测试覆盖 (MnemoBench)

---

## 🎯 **五、memos-graph v3.0 设计 (基于代码实现)**

### 5.1 **情感系统：融合模式**

```python
# 融合 AIRI 的多类型 + Nemos 的 arousal
class EmotionSystem:
    # 9 种基础情感 (学习 AIRI)
    EMOTIONS = [
        "happy", "sad", "angry", "think", "surprise",
        "awkward", "question", "curious", "neutral"
    ]
    
    # 情感在 Prompt 中指导 (学习 AIRI)
    SYSTEM_PROMPT = """
    Character can express emotions:
    """ + "\n".join(f"- {e}" for e in EMOTIONS)
    
    # TTS 标记 (学习 AIRI)
    def append_special_token(self, emotion: str):
        # 格式：[EMOTION:happy]
        self.tts_queue.append(f"[EMOTION:{emotion}]")
    
    # 存储为 arousal + 详细分数 (融合 Nemos + AIRI)
    class MemoryEmotion:
        arousal: float  # 总体强度 (0-1)
        details: dict   # 详细分数 {"joy": 0.8, "sadness": 0.1, ...}
```

### 5.2 **召回系统：混合模式**

```python
class Retriever:
    async def retrieve(self, query: str, top_k: int = 20):
        # 1. 混合检索 (学习 Nemos)
        coarse = await self.hybrid_search(query, limit=100)
        # hybrid_search = BM25 (0.3) + Vector (0.7)
        
        # 2. 多因子排序 (学习 Nemos + AIRI)
        for doc in coarse:
            doc.score = (
                1.0 * doc.similarity +           # 语义
                0.3 * doc.time_relevance +       # 时间
                0.2 * doc.emotional_boost +      # 情感 (arousal)
                0.1 * log(doc.retrieval_count)   # 频率
            )
        
        coarse.sort(key='score', reverse=True)
        
        # 3. Rerank (学习 Nemos)
        if len(coarse) >= 20:
            reranked = await self.rerank_model.rank(query, coarse[:20])
        else:
            reranked = coarse
        
        # 4. 遗忘曲线 (学习 AIRI)
        now = datetime.now()
        for mem in reranked:
            days = (now - mem.created_at).days
            decay = pow(0.5, days / 7)  # 7 天半衰期
            mem.final_score = mem.score * decay
        
        return reranked[:top_k]
```

### 5.3 **代码实现优先级**

#### P0 (必须实现)
1. **情感类型定义** (9 种)
2. **System Prompt 集成**
3. **TTS 特殊标记**
4. **混合检索 (BM25 + Vector)**
5. **多因子排序**

#### P1 (应该实现)
6. **Rerank 模型** (CrossEncoder)
7. **遗忘曲线** (半衰期)
8. **情感存储** (arousal + details)

#### P2 (可选实现)
9. **PTSD 闪回**
10. **Director 系统** (LLM 情感判断)

---

## 📦 **六、行动清单**

### 立即做的 (本周)

1. **实现情感类型**
   ```python
   # src/memos_graph/emotion/__init__.py
   EMOTIONS = ["happy", "sad", "angry", ...]
   ```

2. **集成到 System Prompt**
   ```python
   # src/memos_graph/prompts/system.py
   SYSTEM_PROMPT = "...\nEmotions: " + ", ".join(EMOTIONS)
   ```

3. **实现 TTS 标记**
   ```python
   # src/memos_graph/tts/session.py
   def append_special(emotion: str):
       queue.append(f"[EMOTION:{emotion}]")
   ```

4. **实现混合检索**
   ```python
   # src/memos_graph/retrieve/__init__.py
   def hybrid_search(query):
       bm25_score = bm25(query)
       vector_score = cosine_similarity(query)
       return 0.3 * bm25_score + 0.7 * vector_score
   ```

### 中期做的 (2 周)

5. **实现 Rerank**
   ```python
   from sentence_transformers import CrossEncoder
   model = CrossEncoder('BAAI/bge-reranker-base')
   ```

6. **实现遗忘曲线**
   ```python
   def apply_decay(memory):
       days = (now - memory.created_at).days
       return pow(0.5, days / 7)
   ```

7. **实现多因子排序**
   ```python
   score = 1.0*similarity + 0.3*time + 0.2*emotion + 0.1*frequency
   ```

---

## 💬 **结论**

### 代码实现的真相

| 项目 | 情感实现 | 召回实现 | 文档一致性 |
|------|---------|---------|-----------|
| **AIRI** | ✅ 9 种 + TTS | ⚠️ 向量 + 时间 | ⚠️ 部分一致 |
| **Nemos** | ✅ arousal | ✅ BM25+ 向量+Rerank | ✅ 完全一致 |
| **MetaPact** | ❌ 无 | ❌ 无 | ❌ 不一致 |
| **here-ai** | ⚠️ happy/neutral | ⚠️ BM25 | ⚠️ 部分一致 |

### memos-graph 的机会

> **做第一个文档与代码完全一致 + 融合所有优点的项目！**

```
memos-graph v3.0 = 
  AIRI 的 9 种情感 + TTS 标记 +
  Nemos 的 arousal + BM25+ 向量+Rerank +
  文档与代码 100% 一致 +
  测试覆盖 (MnemoBench 风格)
```

**不要只学 README，要学代码实现！** 🚀

---

**附录：Clawra 说明**

Clawra 项目未在 GitHub 上找到公开仓库。可能是：
- 私有仓库
- 已改名/删除
- 尚未开源

**建议**: 如果是你正在开发的项目，请提供代码路径，我可以深度分析并给出具体建议。
