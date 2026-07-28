# AIRI 情感与召回功能深度分析

**分析日期**: 2026-07-28  
**项目**: flamingo15490/airi-nahida (AIRI 定制分支)  
**核心焦点**: 情感系统 (Emotion) + 召回功能 (Retrieval/Recall)

---

## 😊 **一、情感系统 (Emotion System)**

### 1.1 **情感定义 (9 种基础情感)**

```typescript
// packages/stage-ui-spine/src/constants/emotions.ts
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

**关键设计**:
- ✅ **9 种基础情感**: 覆盖主要情绪状态
- ✅ **Spine 动画映射**: 每种情感对应特定的 Live2D/Spine 动画
- ✅ **轨道分层**: 
  - Track 0: 基础状态 (Idle)
  - Track 1: 情感覆盖 (Emotion Override)

---

### 1.2 **情感动画映射**

```typescript
export const SpineAnimationName = {
  Idle: 'idle',
  Happy: 'celebrate',      // 开心 → 庆祝动画
  Sad: 'sad',              // 悲伤 → 悲伤动画
  Angry: 'angry',          // 愤怒 → 愤怒动画
  Awkward: 'awkward',      // 尴尬 → 尴尬动画
  Think: 'think',          // 思考 → 思考动画
  Surprise: 'surprise',    // 惊讶 → 惊讶动画
  Question: 'question',    // 疑问 → 疑问动画
  Curious: 'curious',      // 好奇 → 好奇动画
  Neutral: 'idle',         // 中性 → 待机动画
} as const

// 情感 → Spine 动画名称映射
export const EMOTION_SpineAnimationName_value: Record<Emotion, string> = {
  [Emotion.Happy]: SpineAnimationName.Happy,
  [Emotion.Sad]: SpineAnimationName.Sad,
  [Emotion.Angry]: SpineAnimationName.Angry,
  // ...
}
```

**动画层级**:
```
Track 1 (情感覆盖)
    ↓ 渲染在上层
Track 0 (基础待机)
    ↓ 始终运行
Skeleton (骨骼)
```

**优势**:
- ✅ **非破坏性**: 情感动画覆盖在基础动画上，不中断待机
- ✅ **可插拔**: 运行时可动态覆盖映射表
- ✅ **模型兼容**: 不同模型可自定义动画名称

---

### 1.3 **Nahida 角色情感表达风格**

```typescript
// packages/stage-ui/src/stores/nahida-persona.ts
export const nahidaPersonaAsset = {
  expressionStyle: {
    tone: [
      'Speak with warmth, patience, and light curiosity',
      'Observe first, then respond: notice the user\'s mood',
      'Carry a childlike observational angle without becoming babyish',
      'Explain difficult ideas clearly with one small natural metaphor',
    ],
    motifs: [
      'Use soft natural imagery: leaves, seeds, rain, dreams, moonlight',
      'Treat metaphors as occasional bridges, not mandatory decoration',
    ],
    sentencePatterns: [
      'Short openings: "Hmm...", "Do you know?", "Listen..."',
      'Gentle endings that leave room for the user to continue',
    ],
    proactiveTone: [
      'For reminders: observe first, then offer one brief, warm nudge',
      'Prefer short, grounded encouragement over dramatic speeches',
    ],
    antiPatterns: [
      'Do not recite wiki facts unless asked',
      'Do not turn every reply into a fairy tale',
      'Do not force catchphrases into every line',
    ],
  },
}
```

**关键洞察**:
- ✅ **情感表达有风格**: 不是简单的情感标签，而是有语言风格
- ✅ **隐喻使用**: 用自然意象 (叶子、种子、雨) 表达情感
- ✅ **反模式**: 明确定义"不应该做什么"

---

### 1.4 **情感与记忆的关联 (情绪加权)**

根据 DevLog 2025.04.14:

```typescript
// 情绪分数存储
interface EmotionalScore {
  joy: number       // 欢欣 (0-1)
  sadness: number   // 悲伤 (0-1)
  anger: number     // 愤怒 (0-1)
  fear: number      // 恐惧 (0-1)
  disgust: number   // 厌恶 (0-1)
}

// 情绪对记忆分数的影响
function applyEmotionalWeight(memory, emotionalScore) {
  // 开心的记忆强化
  if (emotionalScore.joy > 0.5) {
    memory.original_score *= 1.2  // +20%
  }
  
  // 难过的记忆抑制
  if (emotionalScore.sadness > 0.5) {
    memory.original_score *= 0.9  // -10%
  }
  
  // 创伤记忆 (PTSD)
  if (emotionalScore.fear > 0.7) {
    // 平时分数很低
    memory.original_score *= 0.5
    
    // 但 5% 概率"闪回"
    if (Math.random() < 0.05) {
      triggerFlashback(memory)
    }
  }
  
  return memory
}
```

**关键设计**:
- ✅ **情绪影响强度**: 开心的记忆更深刻，难过的记忆被抑制
- ✅ **PTSD 模拟**: 创伤记忆平时被压抑，但会随机"闪回"
- ✅ **符合心理学**: 情绪强烈的记忆更难忘

---

### 1.5 **情感触发器 (Director 系统)**

```typescript
// packages/stage-ui/src/stores/modules/artistry-autonomous.ts
async function runArtistTask(inputText: string, history: Message[] = []) {
  // 1. 定义"导演"提示词
  const systemPrompt = `You are the Cinematic Director for AIRI.
Your job is to analyze the character's response and decide if it warrants a visual manifestation.

Manifestation is warranted for:
- Descriptions of beautiful scenery or environment changes
- Expressive emotional reactions or body language
- Direct mentions of food, items, or gifts
- Narrative actions that would look stunning as a manga/anime scene

Output JSON:
{
  "reasoning": "Why this warrants/doesn't warrant a visual",
  "intensity": 0-100,  // 情感强度
  "prompt": "Image generation prompt",
  "title": "Scene title"
}`

  // 2. 分析上下文
  const analysisPrompt = `Consider the recent history...
  
LATEST INPUT: "${inputText}"`

  // 3. LLM 判断情感强度
  const result = await generateText({
    model: activeModel,
    messages: [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: analysisPrompt }
    ]
  })
  
  // 4. 如果强度超过阈值，触发动画
  if (result.intensity >= threshold) {
    triggerEmotionAnimation(result.emotion)
    generateImage(result.prompt)
  }
}
```

**关键设计**:
- ✅ **LLM 判断情感**: 用 LLM 分析上下文，判断是否需要情感表达
- ✅ **强度阈值**: 只有强度≥70 才触发 (避免过度表演)
- ✅ **多模态**: 情感触发 → 动画 + 图像生成

---

## 🔍 **二、召回功能 (Retrieval/Recall)**

### 2.1 **召回流程 (RAG Pipeline)**

根据 DevLog 2025.04.14:

```
用户 Query
    ↓
1. 分词 (Tokenization)
    ↓
2. 向量化 (Embedding)
    ↓
3. 粗排 (基础排序 - BM25 + 余弦相似度)
    ↓
4. 精排 (业务排序 - 多因子加权)
    ↓
5. Rerank (专家模型重新排序)
    ↓
6. 返回 TOP K
```

---

### 2.2 **粗排 (基础排序)**

```sql
-- 基础排序：海选 TOP N
SELECT 
  id,
  content,
  -- 1. 静态文本相关性 (BM25)
  static_bm25(query, content) AS bm25_score,
  
  -- 2. 精确匹配提升
  exact_match_boost(query, title) AS exact_boost,
  
  -- 3. 余弦相似度 (向量)
  1 - cosine_distance(query_vector, content_vector) AS similarity
  
FROM memories
WHERE ...  -- 基础过滤

ORDER BY 
  (1.0 * bm25_score) + 
  (0.5 * exact_boost) + 
  (1.2 * similarity) DESC

LIMIT 100  -- 海选 100 条进入精排
```

**关键因子**:
- ✅ **BM25**: 传统文本相关性
- ✅ **Exact Match**: 精确匹配提升 (用户关键词完整出现)
- ✅ **Cosine Similarity**: 向量相似度

---

### 2.3 **精排 (业务排序)**

```sql
-- 精排：多因子加权
SELECT 
  id,
  content,
  
  -- 1. 语义相似度 (从粗排继承)
  similarity,
  
  -- 2. 时间相关度 (越新越相关)
  exp(-days_since_created / 7.0) AS time_relevance,
  
  -- 3. 召回次数 (常被召回的更重要)
  log10(retrieval_count + 1) AS retrieval_boost,
  
  -- 4. 情感加权
  (joy_score - sadness_score) * 0.2 AS emotional_boost,
  
  -- 5. 用户偏好匹配
  CASE 
    WHEN user_preferences MATCH content THEN 1.0
    ELSE 0.0
  END AS preference_match

FROM (
  -- 粗排结果 (TOP 100)
  SELECT ... FROM ... WHERE ... LIMIT 100
) AS coarse_results

ORDER BY 
  (1.2 * similarity) +           -- 语义 (1.2x)
  (0.2 * time_relevance) +       -- 时间 (0.2x)
  (0.1 * retrieval_boost) +      -- 频率 (0.1x)
  (0.2 * emotional_boost) +      -- 情感 (0.2x)
  (0.3 * preference_match)       -- 偏好 (0.3x)
DESC

LIMIT 20  -- 精排返回 20 条
```

**关键设计**:
- ✅ **多因子加权**: 综合考虑语义/时间/频率/情感/偏好
- ✅ **权重可调**: 1.2, 0.2 等参数可调
- ✅ **无状态**: 不需要实时更新分数，查询时计算

---

### 2.4 **Rerank (专家模型)**

```python
# 用专门的 Rerank 模型重新排序
def rerank(query, candidates):
    """
    candidates: 精排返回的 TOP 20
    
    使用 CrossEncoder 模型 (如 BGE-Reranker) 重新打分
    """
    from sentence_transformers import CrossEncoder
    
    model = CrossEncoder('BAAI/bge-reranker-base')
    
    # 构建 (query, document) 对
    pairs = [[query, doc.content] for doc in candidates]
    
    # 模型打分
    scores = model.predict(pairs)
    
    # 重新排序
    for doc, score in zip(candidates, scores):
        doc.rerank_score = score
    
    return sorted(candidates, key=lambda d: d.rerank_score, reverse=True)
```

**关键洞察**:
- ✅ **专家模型**: CrossEncoder 比向量相似度更精准
- ✅ **计算密集**: 只在小候选集 (TOP 20) 上用
- ✅ **最后把关**: 决定最终返回顺序

---

### 2.5 **遗忘曲线在召回中的应用**

```typescript
// 遗忘曲线影响召回分数
function applyForgettingCurve(memory, now) {
  const days = daysBetween(memory.created_at, now)
  const halfLife = memory.half_life_days || 7
  
  // 遗忘函数 (半衰期模型)
  const decay_factor = Math.pow(0.5, days / halfLife)
  
  // 当前分数
  const current_score = memory.original_score * decay_factor
  
  // 如果分数过低，标记为"已遗忘" (召回时排除)
  if (current_score < 0.1) {
    memory.is_forgotten = true
  }
  
  return {
    ...memory,
    current_score,
    decay_factor
  }
}

// 召回时应用遗忘
async function retrieve(query, top_k = 20) {
  // 1. 基础检索
  const candidates = await search(query)
  
  // 2. 应用遗忘曲线
  const now = new Date()
  const withDecay = candidates.map(m => applyForgettingCurve(m, now))
  
  // 3. 过滤已遗忘
  const active = withDecay.filter(m => !m.is_forgotten)
  
  // 4. 多因子排序
  const ranked = rerank(active, query)
  
  // 5. 返回 TOP K
  return ranked.slice(0, top_k)
}
```

**效果**:
```
第 0 天：分数 = 1.0  → 容易召回
第 7 天：分数 = 0.5  → 中等难度
第 14 天：分数 = 0.25 → 难以召回
第 21 天：分数 = 0.125 → 标记为"已遗忘"
```

---

### 2.6 **记忆强化机制**

```typescript
// 每次召回强化记忆
function reinforceMemory(memory) {
  // 1. 增加召回次数
  memory.retrieval_count += 1
  
  // 2. 强化原始分数
  memory.original_score *= 1.1  // +10%
  
  // 3. 延长半衰期
  memory.half_life_days *= 1.2  // +20%
  
  // 4. 如果情感强烈，额外强化
  if (memory.emotional_score > 0.7) {
    memory.original_score *= 1.2  // +20%
  }
  
  // 5. 持久化
  await db.update(memory)
}

// 召回时自动强化
async function retrieve(query, top_k = 20) {
  const results = await search(query)
  
  // 异步强化 (不阻塞返回)
  for (const memory of results.slice(0, 5)) {
    reinforceMemory(memory)  // 只强化 TOP 5
  }
  
  return results
}
```

**关键设计**:
- ✅ **正向循环**: 常被召回的记忆更难忘
- ✅ **情感加权**: 情感强烈的记忆强化更多
- ✅ **异步执行**: 不阻塞召回返回

---

### 2.7 **PTSD 闪回机制**

```typescript
// 创伤记忆的随机闪回
async function checkPTSDFlashback(userId) {
  // 查找高恐惧记忆
  const traumaMemories = await db.query(`
    SELECT * FROM memories
    WHERE user_id = $1
      AND fear_score > 0.7
      AND is_forgotten = false
  `, [userId])
  
  // 每条创伤记忆 5% 概率闪回
  for (const memory of traumaMemories) {
    if (Math.random() < 0.05) {
      // 触发闪回
      await triggerFlashback(memory)
      
      // 记录日志
      console.log(`[PTSD Flashback] ${memory.id}: ${memory.content}`)
    }
  }
}

// 闪回触发器
async function triggerFlashback(memory) {
  // 1. 推送通知 (可选)
  await notifyUser({
    type: 'flashback',
    memory: memory.content,
    emotion: 'fear'
  })
  
  // 2. 在对话中自然提及 (可选)
  await insertIntoContext({
    type: 'intrusive_thought',
    content: `突然想起了${memory.content}...`,
    emotion: memory.emotional_score
  })
}
```

**心理学依据**:
- ✅ **创伤记忆被压抑**: `fear_score > 0.7` 的记忆平时分数很低
- ✅ **随机闪回**: 5% 概率突然想起 (符合 PTSD 症状)
- ✅ **侵入性思维**: 在对话中自然提及 (模拟真实闪回)

---

## 🆚 **AIRI vs Nemos vs memos-graph**

### 情感系统对比

| 维度 | AIRI | Nemos | memos-graph (提案) |
|------|------|-------|-------------------|
| **情感类型** | 9 种 (Happy/Sad/Angry...) | arousal (0-1) | 5 种 (joy/sadness/anger/fear/disgust) |
| **情感表达** | ✅ Spine 动画 | ❌ 无 | ⏳ Live2D/表情 |
| **情感加权** | ✅ 影响记忆分数 | ✅ arousal 加权 | ✅ 情感节点权重 |
| **PTSD 模拟** | ✅ 随机闪回 (5%) | ❌ 无 | ⏳ 可学习 |
| **LLM 判断** | ✅ Director 系统 | ❌ 无 | ⏳ 可学习 |
| **风格定义** | ✅ 语言风格/隐喻 | ❌ 无 | ⏳ 可学习 |

### 召回功能对比

| 维度 | AIRI | Nemos | memos-graph (提案) |
|------|------|-------|-------------------|
| **检索方式** | BM25 + 向量 + Rerank | MoE 路由 + 向量 | 图谱遍历 + 向量 |
| **排序因子** | 5 因子 (语义/时间/频率/情感/偏好) | 3 因子 (MoE/向量/时间) | 多因子 (可自定义) |
| **遗忘曲线** | ✅ 半衰期模型 | ✅ FSRS 简化版 | ⏳ 时间衰减 |
| **记忆强化** | ✅ 召回次数 + 情感加权 | ✅ 访问次数 | ⏳ 访问次数 |
| **PTSD 闪回** | ✅ 随机触发 | ❌ 无 | ⏳ 可学习 |
| **Rerank** | ✅ CrossEncoder | ❌ 无 | ⏳ 可学习 |
| **多跳推理** | ❌ 无 | ⚠️ 一跳跨域 | ✅ 多跳 |

---

## 💡 **AIRI 给 memos-graph 的启发**

### ✅ 学习 AIRI 的优点

#### 1. **情感动画系统**

```python
# memos-graph 可以学习的情感表达
class EmotionAnimation:
    emotions = {
        'happy': 'celebrate_animation',
        'sad': 'sad_animation',
        'angry': 'angry_animation',
        # ...
    }
    
    def trigger(self, emotion, intensity):
        if intensity >= threshold:
            play_animation(self.emotions[emotion])
```

#### 2. **Director 系统 (LLM 判断情感)**

```python
async def analyze_emotion(context: str) -> EmotionResult:
    prompt = f"""You are the Emotion Director.
Analyze the context and decide the character's emotion.

Output JSON:
{{
  "emotion": "happy|sad|angry|...",
  "intensity": 0-100,
  "reasoning": "Why this emotion"
}}"""
    
    result = await llm(prompt, context)
    
    if result.intensity >= 70:
        trigger_animation(result.emotion)
    
    return result
```

#### 3. **多因子排序 (5 因子)**

```python
def rerank(query, candidates):
    for doc in candidates:
        doc.final_score = (
            1.2 * doc.similarity +           # 语义
            0.2 * doc.time_relevance +       # 时间
            0.1 * log(doc.retrieval_count) + # 频率
            0.2 * doc.emotional_boost +      # 情感
            0.3 * doc.preference_match       # 偏好
        )
    
    return sorted(candidates, key=lambda d: d.final_score, reverse=True)
```

#### 4. **PTSD 闪回机制**

```python
async def check_flashbacks(user_id):
    trauma = await db.query("""
        SELECT * FROM memories
        WHERE user_id = $1 AND fear_score > 0.7
    """, [user_id])
    
    for mem in trauma:
        if random.random() < 0.05:  # 5% 概率
            await trigger_flashback(mem)
```

#### 5. **Rerank 模型**

```python
from sentence_transformers import CrossEncoder

model = CrossEncoder('BAAI/bge-reranker-base')

def rerank(query, candidates):
    pairs = [[query, doc.content] for doc in candidates]
    scores = model.predict(pairs)
    
    for doc, score in zip(candidates, scores):
        doc.rerank_score = score
    
    return sorted(candidates, key=lambda d: d.rerank_score, reverse=True)
```

---

## 🚀 **memos-graph v3.0 设计 (融合 AIRI)**

```python
class MemoryNode:
    # Nemos 5 层
    layer: Literal["archival", "episodic", "semantic", "personal_semantic", "procedural"]
    
    # memos-graph 图谱
    id: str
    relations: List[Edge]
    
    # AIRI 情感 (9 种 + 5 种深度)
    emotion: Literal["happy", "sad", "angry", "think", "surprise", "awkward", "question", "curious", "neutral"]
    emotional_scores: {
        "joy": 0.8,
        "sadness": 0.1,
        "anger": 0.0,
        "fear": 0.0,
        "disgust": 0.0
    }
    
    # AIRI 遗忘曲线
    original_score: float = 1.0
    half_life_days: int = 7
    retrieval_count: int = 0
    
    # AIRI PTSD 闪回
    is_trauma: bool = False
    flashback_probability: float = 0.05
    
    # Nemos 双时间轴
    valid_at: datetime
    invalidated_at: Optional[datetime]
    
    # Nemos 防污染
    authoritative: bool
    chain_depth: int


class Retriever:
    async def retrieve(self, query: str, top_k: int = 20):
        # 1. MoE 路由 (Nemos)
        route = await self.router.route(query)
        
        # 2. 粗排 (AIRI: BM25 + 向量)
        coarse = await self.coarse_search(query, route.layers, limit=100)
        
        # 3. 精排 (AIRI: 5 因子)
        fine = []
        for doc in coarse:
            doc.final_score = (
                1.2 * doc.similarity +
                0.2 * doc.time_relevance +
                0.1 * log(doc.retrieval_count + 1) +
                0.2 * doc.emotional_boost +
                0.3 * doc.preference_match
            )
            fine.append(doc)
        
        fine.sort(key=lambda d: d.final_score, reverse=True)
        fine = fine[:20]
        
        # 4. Rerank (AIRI: CrossEncoder)
        reranked = self.rerank_model.predict(query, fine)
        
        # 5. 图谱多跳 (memos-graph)
        expanded = self.graph_traverse(reranked, max_hops=3)
        
        # 6. 遗忘曲线 (AIRI: 半衰期)
        now = datetime.now()
        for mem in expanded:
            days = (now - mem.created_at).days
            decay = pow(0.5, days / mem.half_life_days)
            mem.current_score = mem.original_score * decay
        
        # 7. 过滤失效 (Nemos)
        valid = [m for m in expanded if not m.invalidated_at]
        
        # 8. 检查 PTSD 闪回 (AIRI)
        await self.check_flashbacks(self.user_id)
        
        # 9. 强化 TOP 5 (AIRI)
        for mem in valid[:5]:
            await self.reinforce(mem)
        
        # 10. 返回 TOP K
        return sorted(valid, key=lambda m: m.current_score, reverse=True)[:top_k]
    
    async def check_flashbacks(self, user_id):
        trauma = await self.db.query("""
            SELECT * FROM memories
            WHERE user_id = $1 AND fear_score > 0.7
        """, [user_id])
        
        for mem in trauma:
            if random.random() < mem.flashback_probability:
                await self.trigger_flashback(mem)
    
    async def reinforce(self, memory):
        memory.retrieval_count += 1
        memory.original_score *= 1.1
        memory.half_life_days *= 1.2
        
        if memory.emotional_scores.get('joy', 0) > 0.7:
            memory.original_score *= 1.2
        
        await self.db.update(memory)
```

---

## 💬 **结论**

### AIRI 的核心贡献

| 模块 | 核心创新 | memos-graph 应学习 |
|------|----------|-------------------|
| **情感系统** | 9 种情感 + Spine 动画 | ✅ 情感类型 + 动画表达 |
| **情感加权** | 影响记忆分数 | ✅ 5 因子排序之一 |
| **Director** | LLM 判断情感强度 | ✅ 智能情感触发 |
| **PTSD 闪回** | 随机触发 (5%) | ✅ 创伤记忆模拟 |
| **召回流程** | 粗排 + 精排 + Rerank | ✅ 三阶段排序 |
| **多因子排序** | 5 因子 (语义/时间/频率/情感/偏好) | ✅ 完全采用 |
| **遗忘曲线** | 半衰期模型 | ✅ 简单有效 |
| **记忆强化** | 召回次数 + 情感加权 | ✅ 正向循环 |
| **Rerank** | CrossEncoder 专家模型 | ✅ 最后把关 |

### memos-graph v3.0 的愿景

> **融合所有优点的终极记忆引擎！**

```
memos-graph v3.0 = 
  Nemos 的 5 层模型 +          # 结构化
  Nemos 的矛盾失效 +          # 可靠性
  Nemos 的防污染 +            # 权威性
  memos-graph 的图谱 +        # 多跳推理
  AIRI 的情感系统 +           # 9 种情感 + 动画
  AIRI 的多因子排序 +         # 5 因子精排
  AIRI 的半衰期遗忘 +         # 简单有效
  AIRI 的 PTSD 闪回 +         # 创伤模拟
  AIRI 的 Rerank 模型 +       # 专家排序
  AIRI 的 Director 系统       # LLM 情感判断
```

**站在巨人的肩膀上，做得更深、更远！** 🚀

---

**下一步行动**:

1. **实现情感系统** (9 种情感 + 动画映射)
2. **实现多因子排序** (5 因子：语义/时间/频率/情感/偏好)
3. **实现 Rerank 模型** (CrossEncoder)
4. **实现 PTSD 闪回** (随机触发机制)
5. **实现 Director 系统** (LLM 情感判断)
6. **实现记忆强化** (召回次数 + 情感加权)

**融合三家之长，打造终极记忆引擎！** 🚀
