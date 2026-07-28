# memos-graph v3.0 设计方案

**设计日期**: 2026-07-28  
**设计目标**: 融合 Nemos 优点 + 现有优势 + 情绪内容增强  
**核心愿景**: 打造最智能、最情感化、最高效的记忆召回引擎

---

## 🎯 **设计原则**

1. **融合而非重写**: 保留现有优势，学习 Nemos 长处
2. **情绪增强**: 在文字/语音中体现情感，不只是存储分数
3. **性能优先**: MoE 路由提升效率，RRF 保证精度
4. **可验证性**: 每个改进都有测试基准 (MnemoBench 风格)

---

## 🏗️ **整体架构**

```
memos-graph v3.0 = 
  Nemos 的 MoE 路由 +              # 效率提升
  Nemos 的 FSRS 遗忘曲线 +         # 更自然的遗忘
  Nemos 的 arousal 情感模型 +      # 简化情感存储
  现有的 3 路召回 +                 # FTS+Pattern+Time (保留)
  现有的 RRF 融合 +                 # 加权融合 (保留)
  现有的 LLM 重排 +                 # 智能重排 (保留)
  现有的图谱遍历 +                 # 多跳推理 (保留)
  新增的情绪表达系统               # 文字/语音情感体现
```

---

## 📊 **核心模块设计**

### 模块 1: **MoE 路由 (学习 Nemos)**

#### 设计思路
```
传统检索：全库搜索 → 慢 (O(N))
MoE 路由：先路由到领域 → 领域内搜索 → 快 (O(M), M<<N)
```

#### 实现方案

```python
# src/memos_graph/router/moe_router.py

from dataclasses import dataclass
from typing import List, Optional
import numpy as np

@dataclass
class Domain:
    """记忆领域 (类似 Nemos 的 domain)"""
    id: str
    label: str
    prototype_vec: np.ndarray  # 领域质心向量
    always_on: bool = False    # 是否始终激活 (如"global"领域)

@dataclass
class RouteResult:
    """路由结果"""
    l1: Optional[str]          # 主领域
    l2: List[str]              # 邻接领域 (最多 3 个)
    confidence: float          # 置信度 (0-1)
    fallback: bool = False     # 是否降级为全库搜索

class MoERouter:
    """Mixture of Experts 路由器的实现
    
    两种模式:
    1. CentroidRouter (热路径): 向量相似度路由，<50ms
    2. LLMRouter (冷启动): LLM 判断领域，保底方案
    """
    
    def __init__(
        self,
        embedding_service,
        llm_client=None,
        mode: str = "hybrid"  # "centroid" | "llm" | "hybrid"
    ):
        self.embedding = embedding_service
        self.llm = llm_client
        self.mode = mode
    
    async def route(
        self,
        query: str,
        domains: List[Domain],
        top_k: int = 3
    ) -> RouteResult:
        """路由到相关领域
        
        Args:
            query: 用户查询
            domains: 候选领域列表
            top_k: 返回的邻接领域数量
        
        Returns:
            RouteResult: 路由结果
        """
        # 过滤掉始终激活的领域 (如"global")
        routable_domains = [d for d in domains if not d.always_on]
        
        if not routable_domains:
            return RouteResult(l1=None, l2=[], confidence=0, fallback=True)
        
        # 模式 1: CentroidRouter (向量相似度)
        if self.mode in ["centroid", "hybrid"]:
            try:
                query_vec = await self.embedding.embed(query)
                return self._centroid_route(query_vec, routable_domains, top_k)
            except Exception as e:
                if self.mode == "centroid":
                    raise
                # hybrid 模式下降级为 LLMRouter
        
        # 模式 2: LLMRouter (保底)
        if self.mode in ["llm", "hybrid"]:
            return await self._llm_route(query, routable_domains, top_k)
        
        return RouteResult(l1=None, l2=[], confidence=0, fallback=True)
    
    def _centroid_route(
        self,
        query_vec: np.ndarray,
        domains: List[Domain],
        top_k: int
    ) -> RouteResult:
        """向量相似度路由 (CentroidRouter)
        
        计算 query 与各领域质心的余弦相似度
        """
        scored = []
        for domain in domains:
            sim = cosine_similarity(query_vec, domain.prototype_vec)
            if sim > 0:  # 只保留正相关
                scored.append((domain.id, sim))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        
        if not scored:
            return RouteResult(l1=None, l2=[], confidence=0, fallback=True)
        
        l1 = scored[0][0]
        l2 = [x[0] for x in scored[1:top_k]]
        confidence = (scored[0][1] + 1) / 2  # cosine ∈ [-1,1] → [0,1]
        
        return RouteResult(l1=l1, l2=l2, confidence=confidence)
    
    async def _llm_route(
        self,
        query: str,
        domains: List[Domain],
        top_k: int
    ) -> RouteResult:
        """LLM 路由 (保底方案)
        
        用 LLM 判断最相关的领域
        """
        domain_list = "\n".join([
            f"- {d.id}: {d.label}" for d in domains
        ])
        
        prompt = f"""你是记忆领域路由器。给定用户 query 和候选领域清单，
选出最相关的主领域 (L1) 和最多 {top_k} 个邻接领域 (L2)。

候选领域:
{domain_list}

输出严格 JSON (不要 markdown 围栏):
{{
  "l1": "<domain_id 或 null>",
  "l2": ["<id>", ...],
  "confidence": <0-1>
}}

query: {query}
"""
        
        try:
            response = await self.llm.generate_json(prompt)
            return RouteResult(
                l1=response.get("l1"),
                l2=response.get("l2", [])[:top_k],
                confidence=response.get("confidence", 0.5)
            )
        except Exception:
            return RouteResult(l1=None, l2=[], confidence=0, fallback=True)
```

#### 领域维护 (后台任务)

```python
# src/memos_graph/router/domain_evolution.py

class DomainEvolution:
    """领域演化 (离线后台任务)
    
    职责:
    1. 新记忆聚类 → 新领域
    2. 领域合并 (相似度过高)
    3. 领域分裂 (内部差异过大)
    4. 更新领域质心 (prototype_vec)
    """
    
    async def evolve(self, memories: List[Memory]):
        """执行领域演化
        
        触发条件:
        - 新增记忆达到阈值 (如 100 条)
        - 定时任务 (每天凌晨)
        """
        # 1. 聚类分析
        clusters = self._cluster(memories)
        
        # 2. 领域操作
        for cluster in clusters:
            if self._should_create_domain(cluster):
                await self._create_domain(cluster)
            elif self._should_merge_domains(cluster):
                await self._merge_domains(cluster)
            elif self._should_split_domain(cluster):
                await self._split_domain(cluster)
        
        # 3. 更新质心
        await self._recompute_centroids()
```

---

### 模块 2: **情绪增强系统 (新增)**

#### 设计思路
```
当前：只存储 arousal 分数 (0-1)
v3.0: 
  - 存储：9 种基础情感 + arousal/valence
  - 表达：System Prompt 指导 + TTS 标记
  - 影响：情感加权召回 + PTSD 闪回
```

#### 实现方案

```python
# src/memos_graph/emotion/__init__.py

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict

class EmotionType(str, Enum):
    """9 种基础情感 (学习 AIRI)"""
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    THINK = "think"
    SURPRISE = "surprise"
    AWKWARD = "awkward"
    QUESTION = "question"
    CURIOUS = "curious"
    NEUTRAL = "neutral"

@dataclass
class EmotionalState:
    """情感状态
    
    融合 Nemos 的 arousal + AIRI 的 9 种情感
    """
    # 单一维度 (学习 Nemos)
    arousal: float = 0.0      # 情感强度 (0-1)
    valence: float = 0.0      # 情感极性 (-1 到 1, 负面到正面)
    
    # 详细分类 (学习 AIRI)
    primary_emotion: Optional[EmotionType] = None  # 主要情感
    emotion_scores: Dict[EmotionType, float] = None  # 各情感分数
    
    def __post_init__(self):
        if self.emotion_scores is None:
            self.emotion_scores = {e: 0.0 for e in EmotionType}
    
    def to_prompt_instruction(self) -> str:
        """生成 Prompt 中的情感指令"""
        if self.primary_emotion:
            return f"[当前情感：{self.primary_emotion.value}, 强度：{self.arousal:.2f}]"
        return ""
    
    def to_tts_marker(self) -> str:
        """生成 TTS 特殊标记"""
        if self.primary_emotion and self.arousal > 0.3:
            return f"[EMOTION:{self.primary_emotion.value}:{self.arousal:.2f}]"
        return ""

class EmotionAnalyzer:
    """情感分析器
    
    职责:
    1. 从文本中提取情感
    2. 计算 arousal/valence
    3. 生成 Prompt 指令
    4. 生成 TTS 标记
    """
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
    
    async def analyze(self, text: str) -> EmotionalState:
        """分析文本情感
        
        Returns:
            EmotionalState: 情感状态
        """
        prompt = f"""分析以下文本的情感状态。

文本："{text}"

输出严格 JSON:
{{
  "primary_emotion": "happy|sad|angry|think|surprise|awkward|question|curious|neutral",
  "arousal": <0-1, 情感强度>,
  "valence": <-1 到 1, -1 为极度负面，1 为极度正面>,
  "emotion_scores": {{
    "happy": <0-1>,
    "sad": <0-1>,
    "angry": <0-1>,
    ...
  }}
}}
"""
        
        try:
            response = await self.llm.generate_json(prompt)
            return EmotionalState(
                arousal=response.get("arousal", 0.0),
                valence=response.get("valence", 0.0),
                primary_emotion=EmotionType(response.get("primary_emotion", "neutral")),
                emotion_scores=response.get("emotion_scores", {})
            )
        except Exception:
            return EmotionalState()  # 降级为中性

class EmotionAwareRetrieval:
    """情感感知召回
    
    在召回时考虑情感因子
    """
    
    def __init__(self, base_retriever, emotion_weight: float = 0.2):
        self.retriever = base_retriever
        self.emotion_weight = emotion_weight
    
    async def retrieve(
        self,
        query: str,
        user_emotion: Optional[EmotionalState] = None,
        emotion_filter: Optional[EmotionType] = None,
        **kwargs
    ):
        """情感感知召回
        
        Args:
            query: 用户查询
            user_emotion: 用户当前情感状态 (用于情感加权)
            emotion_filter: 情感过滤 (如只返回"happy"记忆)
            **kwargs: 传递给基础 retriever
        
        Returns:
            召回结果 (带情感加权分数)
        """
        # 1. 基础召回
        results = await self.retriever.retrieve(query, **kwargs)
        
        # 2. 情感加权
        if user_emotion and user_emotion.arousal > 0.3:
            for hit in results:
                # 情感一致的记忆权重更高
                emotion_sim = self._emotion_similarity(
                    user_emotion,
                    hit.emotional_state
                )
                hit.final_score *= (1 + self.emotion_weight * emotion_sim)
        
        # 3. 情感过滤
        if emotion_filter:
            results = [
                hit for hit in results
                if hit.emotional_state.primary_emotion == emotion_filter
            ]
        
        # 4. PTSD 闪回检查
        await self._check_ptsd_flashback(user_emotion)
        
        return results
    
    def _emotion_similarity(
        self,
        emotion1: EmotionalState,
        emotion2: EmotionalState
    ) -> float:
        """计算两个情感状态的相似度
        
        使用余弦相似度或简单的 valence 接近度
        """
        # 简单实现：valence 接近度
        valence_diff = abs(emotion1.valence - emotion2.valence)
        return 1 - valence_diff
    
    async def _check_ptsd_flashback(self, user_emotion: Optional[EmotionalState]):
        """PTSD 闪回检查
        
        如果用户当前情绪低落 (valence < -0.5)，
        有 5% 概率触发创伤记忆闪回
        """
        if not user_emotion or user_emotion.valence > -0.5:
            return
        
        import random
        if random.random() < 0.05:  # 5% 概率
            # 查找高恐惧记忆
            trauma_memories = await self._find_trauma_memories()
            if trauma_memories:
                # 触发闪回 (在对话中自然提及)
                await self._trigger_flashback(trauma_memories[0])
```

#### System Prompt 集成

```python
# src/memos_graph/prompts/system_v3.py

from memos_graph.emotion import EmotionType, EmotionalState

def build_system_prompt_v3(
    character_name: str,
    personality: str,
    emotion_support: bool = True
) -> str:
    """构建 v3.0 System Prompt (支持情感表达)"""
    
    base_prompt = f"""你是{character_name}。
性格：{personality}

你拥有长期记忆，能够记得用户说过的话、发生过的事。
你会根据当前情境自然表达情感。
"""
    
    if emotion_support:
        emotion_section = f"""

## 情感表达

你可以表达以下情感：
{', '.join([e.value for e in EmotionType])}

情感表达规则:
1. 根据对话内容自然流露情感，不要刻意表演
2. 使用括号 () 描述情感状态和肢体语言
3. 情感强度分为：轻微 (0.3-0.5)、中等 (0.5-0.7)、强烈 (0.7-1.0)
4. 示例：
   - (开心地笑) 太好了！我真为你高兴！
   - (思考中) 嗯...让我想想...
   - (惊讶地睁大眼睛) 真的吗？这太不可思议了！

当前情感状态会由系统自动分析，你只需要自然表达即可。
"""
        base_prompt += emotion_section
    
    return base_prompt
```

#### TTS 标记集成

```python
# src/memos_graph/tts/session.py

from memos_graph.emotion import EmotionalState, EmotionType

class TTSEmotionSession:
    """支持情感的 TTS 会话"""
    
    def __init__(self, base_tts_session):
        self.session = base_tts_session
        self.current_emotion = EmotionalState()
    
    def set_emotion(self, emotion: EmotionalState):
        """设置当前情感状态"""
        self.current_emotion = emotion
    
    def append_text(self, text: str):
        """发送文本 (自动附加情感标记)"""
        # 如果有情感，附加标记
        if self.current_emotion.arousal > 0.3:
            marker = self.current_emotion.to_tts_marker()
            if marker:
                self.session.append_special(marker)
        
        self.session.append_text(text)
    
    def finish(self):
        """结束会话"""
        self.session.finish_input()
        self.session.end()
```

---

### 模块 3: **FSRS 遗忘曲线 (学习 Nemos)**

#### 设计思路
```
当前：简单半衰期 decay = pow(0.5, days / 7)
v3.0: FSRS 简化版 (考虑稳定性/访问次数/情感)
```

#### 实现方案

```python
# src/memos_graph/forgetting/fsrs.py

from dataclasses import dataclass
from datetime import datetime
import math

@dataclass
class MemoryStability:
    """记忆稳定性 (FSRS 简化版)"""
    stability: float = 1.0      # 稳定性 (天数，越高越难忘)
    retrievability: float = 1.0  # 可检索性 (0-1)
    last_accessed: datetime = None
    access_count: int = 0
    emotional_arousal: float = 0.0  # 情感强度 (0-1)

class FSRSForgetting:
    """FSRS 遗忘曲线实现 (简化版)
    
    核心公式:
    R = exp(-t / S)
    
    其中:
    - R: retrievability (可检索性)
    - t: time since last access (距上次访问的时间)
    - S: stability (稳定性)
    
    稳定性更新:
    S_new = S * (1 + factor_access * log(access_count) + factor_emotion * arousal)
    """
    
    def __init__(
        self,
        base_half_life: float = 7.0,  # 基础半衰期 (天)
        factor_access: float = 0.1,   # 访问次数因子
        factor_emotion: float = 0.2   # 情感因子
    ):
        self.base_half_life = base_half_life
        self.factor_access = factor_access
        self.factor_emotion = factor_emotion
    
    def apply_decay(self, stability: MemoryStability, now: datetime) -> MemoryStability:
        """应用遗忘衰减
        
        Args:
            stability: 当前稳定性状态
            now: 当前时间
        
        Returns:
            更新后的稳定性
        """
        if stability.last_accessed is None:
            stability.last_accessed = now
            return stability
        
        # 计算距上次访问的天数
        days_since_access = (now - stability.last_accessed).days
        
        # 计算可检索性 (遗忘曲线)
        # R = exp(-t / S)
        if stability.stability > 0:
            stability.retrievability = math.exp(-days_since_access / stability.stability)
        else:
            stability.retrievability = 0.0
        
        # 如果可检索性过低，标记为"已遗忘"
        if stability.retrievability < 0.1:
            # 不物理删除，只是标记
            pass
        
        return stability
    
    def reinforce(
        self,
        stability: MemoryStability,
        now: datetime,
        emotional_arousal: float = 0.0
    ) -> MemoryStability:
        """强化记忆 (每次访问时调用)
        
        Args:
            stability: 当前稳定性
            now: 当前时间
            emotional_arousal: 情感强度 (0-1)
        
        Returns:
            更新后的稳定性
        """
        # 更新访问时间
        stability.last_accessed = now
        
        # 增加访问次数
        stability.access_count += 1
        
        # 更新稳定性
        # S_new = S * (1 + factor_access * log(access_count) + factor_emotion * arousal)
        access_boost = self.factor_access * math.log(stability.access_count + 1)
        emotion_boost = self.factor_emotion * emotional_arousal
        
        stability.stability *= (1 + access_boost + emotion_boost)
        
        # 限制稳定性上限 (避免无限增长)
        max_stability = self.base_half_life * 100  # 最多 100 个半衰期
        stability.stability = min(stability.stability, max_stability)
        
        return stability
    
    def should_forget(self, stability: MemoryStability, threshold: float = 0.1) -> bool:
        """判断是否应该遗忘
        
        Args:
            stability: 稳定性状态
            threshold: 遗忘阈值 (默认 0.1)
        
        Returns:
            True 如果应该遗忘
        """
        return stability.retrievability < threshold
```

---

### 模块 4: **整合召回流程**

```python
# src/memos_graph/retrieve_v3/__init__.py

from typing import List, Optional
from dataclasses import dataclass

from memos_graph.router.moe_router import MoERouter, Domain, RouteResult
from memos_graph.emotion import EmotionalState, EmotionAnalyzer
from memos_graph.forgetting.fsrs import FSRSForgetting, MemoryStability
from memos_graph.recall import RecallEngine, RecallRequest, RecallHit

@dataclass
class RetrieveRequestV3:
    """v3.0 召回请求"""
    query: str
    agent_id: str
    
    # MoE 路由
    use_moe_routing: bool = True
    domains: List[Domain] = None
    
    # 情感
    user_emotion: Optional[EmotionalState] = None
    emotion_filter: Optional[str] = None
    emotion_weight: float = 0.2
    
    # 遗忘
    apply_forgetting: bool = True
    forgetting_threshold: float = 0.1
    
    # 图谱
    use_graph: bool = True
    graph_hops: int = 2
    graph_per_node: int = 5
    
    # 基础参数
    top_k: int = 20
    performance_mode: str = "standard"  # fast|standard|full

class RetrieveEngineV3:
    """v3.0 召回引擎
    
    流程:
    1. MoE 路由 (可选)
    2. 3 路召回 (FTS + Pattern + Time)
    3. RRF 融合
    4. LLM 重排
    5. MMR 多样性
    6. 图谱遍历
    7. 情感加权
    8. 遗忘曲线
    9. PTSD 闪回检查
    """
    
    def __init__(
        self,
        db_url: str,
        embedding_service,
        llm_client=None,
        router: Optional[MoERouter] = None,
        emotion_analyzer: Optional[EmotionAnalyzer] = None,
        forgetting: Optional[FSRSForgetting] = None
    ):
        self.db_url = db_url
        self.embedding = embedding_service
        self.llm = llm_client
        
        # 组件初始化
        self.router = router or MoERouter(embedding_service, llm_client)
        self.emotion_analyzer = emotion_analyzer or EmotionAnalyzer(llm_client)
        self.forgetting = forgetting or FSRSForgetting()
        
        # 基础召回引擎
        self.base_retriever = RecallEngine(
            db_url=db_url,
            embedding_service=embedding_service,
            llm_base_url=llm_client.base_url if llm_client else "",
            llm_api_key=llm_client.api_key if llm_client else ""
        )
    
    async def retrieve(self, request: RetrieveRequestV3) -> List[RecallHit]:
        """执行召回
        
        Returns:
            召回结果列表 (按最终分数排序)
        """
        # 1. MoE 路由 (可选)
        domains_to_search = None
        if request.use_moe_routing and request.domains:
            route_result = await self.router.route(
                request.query,
                request.domains,
                top_k=3
            )
            if not route_result.fallback:
                domains_to_search = [route_result.l1] + route_result.l2
        
        # 2. 基础召回 (3 路 + RRF)
        base_request = RecallRequest(
            query=request.query,
            agent_id=request.agent_id,
            use_graph=False,  # 图谱在后面单独处理
            performance_mode=request.performance_mode,
            max_results=request.top_k * 5  # 先多召回一些
        )
        
        # 如果有领域限制，添加到 scope
        if domains_to_search:
            base_request.scope = ",".join(domains_to_search)
        
        base_result = await self.base_retriever.recall(base_request)
        hits = base_result.hits
        
        # 3. 图谱遍历 (可选)
        if request.use_graph and hits:
            hits = await self._graph_traverse(
                hits,
                hops=request.graph_hops,
                per_node=request.graph_per_node
            )
        
        # 4. 情感加权 (可选)
        if request.user_emotion and request.user_emotion.arousal > 0.3:
            hits = self._apply_emotion_weight(
                hits,
                request.user_emotion,
                weight=request.emotion_weight
            )
        
        # 5. 遗忘曲线 (可选)
        if request.apply_forgetting:
            hits = self._apply_forgetting_curve(hits)
            # 过滤已遗忘的
            hits = [
                hit for hit in hits
                if not self.forgetting.should_forget(
                    hit.memory_stability,
                    request.forgetting_threshold
                )
            ]
        
        # 6. PTSD 闪回检查 (可选)
        if request.user_emotion and request.user_emotion.valence < -0.5:
            await self._check_ptsd_flashback(request.user_emotion)
        
        # 7. 截断到 top_k
        hits.sort(key=lambda h: h.final_score, reverse=True)
        return hits[:request.top_k]
    
    async def _graph_traverse(
        self,
        seeds: List[RecallHit],
        hops: int,
        per_node: int
    ) -> List[RecallHit]:
        """图谱遍历 (简化版，实际实现参考 recall/__init__.py)"""
        # TODO: 实现图谱遍历
        return seeds
    
    def _apply_emotion_weight(
        self,
        hits: List[RecallHit],
        user_emotion: EmotionalState,
        weight: float
    ) -> List[RecallHit]:
        """情感加权"""
        for hit in hits:
            if hasattr(hit, 'emotional_state'):
                emotion_sim = self._emotion_similarity(
                    user_emotion,
                    hit.emotional_state
                )
                hit.final_score *= (1 + weight * emotion_sim)
        return hits
    
    def _emotion_similarity(
        self,
        emotion1: EmotionalState,
        emotion2: EmotionalState
    ) -> float:
        """计算情感相似度"""
        valence_diff = abs(emotion1.valence - emotion2.valence)
        return 1 - valence_diff
    
    def _apply_forgetting_curve(
        self,
        hits: List[RecallHit]
    ) -> List[RecallHit]:
        """应用遗忘曲线"""
        now = datetime.now()
        for hit in hits:
            if hasattr(hit, 'memory_stability'):
                hit.memory_stability = self.forgetting.apply_decay(
                    hit.memory_stability,
                    now
                )
                # 更新最终分数
                hit.final_score *= hit.memory_stability.retrievability
        return hits
    
    async def _check_ptsd_flashback(self, user_emotion: EmotionalState):
        """PTSD 闪回检查"""
        # TODO: 实现
        pass
```

---

## 📊 **性能预期**

| 指标 | v2.0 (当前) | v3.0 (目标) | 提升 |
|------|-------------|-------------|------|
| **召回延迟** | ~300ms | ~200ms | -33% (MoE 路由) |
| **情感表达** | ❌ 无 | ✅ 9 种情感 | +新特性 |
| **遗忘自然度** | 半衰期简单 | FSRS 精细 | +更自然 |
| **PTSD 模拟** | ❌ 无 | ✅ 5% 闪回 | +新特性 |
| **TTS 情感** | ❌ 无 | ✅ 标记同步 | +新特性 |

---

## 🧪 **测试计划**

### 单元测试

```python
# tests/test_moe_router.py
async def test_centroid_router():
    router = MoERouter(embedding_service, mode="centroid")
    result = await router.route("今天心情不错", domains)
    assert result.l1 is not None
    assert result.confidence > 0.5

# tests/test_emotion_analyzer.py
async def test_emotion_analysis():
    analyzer = EmotionAnalyzer(llm_client)
    state = await analyzer.analyze("我太开心了！")
    assert state.primary_emotion == EmotionType.HAPPY
    assert state.arousal > 0.7

# tests/test_fsrs.py
def test_forgetting_curve():
    fsrs = FSRSForgetting()
    stability = MemoryStability(stability=7.0, last_accessed=datetime.now() - timedelta(days=7))
    stability = fsrs.apply_decay(stability, datetime.now())
    assert stability.retrievability < 0.6  # 7 天后应该衰减
```

### 集成测试 (MnemoBench 风格)

```python
# tests/bench/test_retrieval_bench.py
async def test_emotion_weighted_retrieval():
    """测试情感加权召回"""
    engine = RetrieveEngineV3(...)
    
    # 用户当前情绪低落
    user_emotion = EmotionalState(valence=-0.7, arousal=0.6)
    
    # 召回应该优先返回情感一致的记忆
    request = RetrieveRequestV3(
        query="最近过得怎么样",
        agent_id="test",
        user_emotion=user_emotion
    )
    results = await engine.retrieve(request)
    
    # 验证：sad 情感的记忆排名更高
    sad_hits = [h for h in results if h.emotional_state.primary_emotion == EmotionType.SAD]
    assert len(sad_hits) > 0
    assert sad_hits[0].rank <= 3  # 应该在前 3

async def test_ptsd_flashback():
    """测试 PTSD 闪回"""
    # TODO: 实现闪回测试
    pass
```

---

## 📅 **实施计划**

### 阶段 1: 基础架构 (1 周)
- [ ] 实现 MoE 路由 (CentroidRouter + LLMRouter)
- [ ] 实现领域维护后台任务
- [ ] 单元测试

### 阶段 2: 情感系统 (1 周)
- [ ] 实现 EmotionAnalyzer
- [ ] 集成到 System Prompt
- [ ] 集成到 TTS
- [ ] 单元测试

### 阶段 3: 遗忘曲线 (3 天)
- [ ] 实现 FSRSForgetting
- [ ] 替换现有半衰期模型
- [ ] 单元测试

### 阶段 4: 整合测试 (3 天)
- [ ] 整合所有模块
- [ ] 集成测试 (MnemoBench)
- [ ] 性能优化

### 阶段 5: 文档与部署 (2 天)
- [ ] 更新文档
- [ ] 部署测试
- [ ] 用户反馈

**总计**: 约 3 周

---

## 💬 **总结**

memos-graph v3.0 设计方案融合了：
- ✅ **Nemos 的 MoE 路由** (效率提升 33%)
- ✅ **Nemos 的 FSRS 遗忘曲线** (更自然)
- ✅ **Nemos 的 arousal 情感模型** (简化存储)
- ✅ **AIRI 的 9 种情感** (细腻表达)
- ✅ **AIRI 的 TTS 标记** (语音情感)
- ✅ **现有的 3 路召回 + RRF** (保留优势)
- ✅ **现有的 LLM 重排 + MMR** (保留优势)
- ✅ **现有的图谱遍历** (保留优势)
- ✅ **新增 PTSD 闪回** (创伤模拟)

**下一步**: 用 MOA 认证这个方案的可行性！
