"""Retrieve Engine v3.0 - Integrated recall with all v3.0 features.

Usage:
    engine = RetrieveEngineV3(
        db_url="postgresql://...",
        embedding_service=embedding,
        llm_client=llm,
        router=MoERouter(embedding, llm),
        emotion_analyzer=EmotionAnalyzer(llm),
        forgetting=FSRSForgetting()
    )
    
    request = RetrieveRequestV3(
        query="work project",
        agent_id="user123",
        use_moe_routing=True,
        domains=[...],
        user_emotion=EmotionalState.happy(0.8),
        use_graph=True,
        top_k=20
    )
    
    results = await engine.retrieve(request)
"""

"""Retrieve Engine v3.0 - Integrated recall with MoE, emotion, FSRS, and graph."""

import time
import random
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from memos_graph.router.moe_router import MoERouter, Domain, RouteResult
from memos_graph.emotion.types import EmotionalState, EmotionType
from memos_graph.emotion.analyzer import EmotionAnalyzer
from memos_graph.forgetting.fsrs import FSRSForgetting, MemoryStability
from memos_graph.recall import RecallEngine, RecallRequest, RecallHit
from memos_graph.db.models import Chunk, EntityEdge
from memos_graph.db.session import create_session_factory
from sqlalchemy import select, func

logger = logging.getLogger(__name__)


@dataclass
class RetrieveRequestV3:
    """v3.0 retrieve request with all options.
    
    Attributes:
        query: User query string
        agent_id: Agent/user identifier
        use_moe_routing: Whether to use MoE routing
        domains: List of domains for MoE routing
        user_emotion: User's current emotional state
        emotion_weight: Weight for emotion scoring (0.0-1.0)
        emotion_filter: Filter hits by emotion (optional)
        use_graph: Whether to use graph traversal
        graph_hops: Number of graph hops (default: 1)
        graph_per_node: Number of neighbors per node (default: 5)
        apply_forgetting: Whether to apply FSRS forgetting
        forgetting_threshold: Stability threshold (R < threshold filtered)
        ptsd_flashback_prob: Probability of PTSD flashback (0.0-1.0)
        top_k: Number of results to return
        performance_mode: Use performance-optimized search
        use_rrf: Whether to use RRF fusion for multi-path recall
        rrf_k: RRF smoothing constant (default: 60)
        use_llm_rerank: Whether to use LLM rerank (v3.1)
        llm_rerank_top_k: Rerank top K results (v3.1)
        use_mmr: Whether to use MMR diversity rerank (v3.1)
        mmr_lambda: MMR lambda for balancing relevance/diversity (v3.1)
    """
    
    query: str
    agent_id: str
    
    # MoE routing
    use_moe_routing: bool = True
    domains: Optional[List[Domain]] = None
    
    # Emotion
    user_emotion: Optional[EmotionalState] = None
    emotion_filter: Optional[EmotionType] = None
    emotion_weight: float = 0.2
    
    # Graph
    use_graph: bool = True
    graph_hops: int = 2
    graph_per_node: int = 5
    
    # Forgetting
    apply_forgetting: bool = True
    forgetting_threshold: float = 0.1
    
    # Basic
    top_k: int = 20
    performance_mode: str = "standard"  # fast|standard|full
    
    # PTSD
    ptsd_flashback_prob: float = 0.01  # 1% probability


@dataclass
class RetrieveResultV3:
    """v3.0 retrieve result.
    
    Attributes:
        query: Original query
        hits: List of recall hits
        took_ms: Execution time in milliseconds
        moe_route: MoE routing result (if used)
        emotion_applied: Whether emotion weighting was applied
        graph_expanded: Number of nodes added by graph traversal
        forgotten_filtered: Number of memories filtered by forgetting
        ptsd_flashback_triggered: Whether PTSD flashback was triggered
    """
    
    query: str
    hits: List[RecallHit]
    took_ms: int
    moe_route: Optional[RouteResult] = None
    emotion_applied: bool = False
    graph_expanded: int = 0
    forgotten_filtered: int = 0
    ptsd_flashback_triggered: bool = False


class RetrieveEngineV3:
    """v3.0 Retrieve Engine with all advanced features.
    
    Integration flow:
    1. MoE routing (optional)
    2. Base recall (3-path: FTS + Pattern + Time)
    3. RRF fusion
    4. LLM reranking + MMR
    5. Graph traversal
    6. Emotion weighting
    7. FSRS forgetting
    8. PTSD flashback check
    """
    
    def __init__(
        self,
        db_url: str,
        embedding_service: Any,
        llm_client: Optional[Any] = None,
        router: Optional[MoERouter] = None,
        emotion_analyzer: Optional[EmotionAnalyzer] = None,
        forgetting: Optional[FSRSForgetting] = None,
        base_retriever: Optional[RecallEngine] = None
    ):
        """Initialize v3.0 Retrieve Engine.
        
        Args:
            db_url: Database URL
            embedding_service: Embedding service for vectors
            llm_client: Optional LLM client for reranking
            router: Optional MoE router (created if None)
            emotion_analyzer: Optional emotion analyzer (created if None)
            forgetting: Optional FSRS forgetting manager (created if None)
            base_retriever: Optional base recall engine (created if None)
        """
        self.db_url = db_url
        self.embedding = embedding_service
        self.llm = llm_client
        
        # Initialize session factory
        from memos_graph.db.session import create_session_factory
        _, session_factory = create_session_factory(db_url)
        self._async_session = session_factory
        
        # Initialize components
        self.router = router or MoERouter(embedding_service, llm_client, mode="hybrid")
        self.emotion_analyzer = emotion_analyzer or EmotionAnalyzer(llm_client)
        self.forgetting = forgetting or FSRSForgetting()
        
        # Base retriever (existing recall engine)
        if base_retriever:
            self.base_retriever = base_retriever
        else:
            self.base_retriever = RecallEngine(
                db_url=db_url,
                embedding_service=embedding_service,
                llm_base_url=llm_client.base_url if llm_client else "",
                llm_api_key=llm_client.api_key if llm_client else ""
            )
        
        logger.info("RetrieveEngineV3 initialized")
    
    async def retrieve(self, request: RetrieveRequestV3) -> RetrieveResultV3:
        """Execute v3.0 retrieve with all features.
        
        Args:
            request: Retrieve request with all options
        
        Returns:
            Retrieve result with hits and metadata
        """
        start_time = datetime.now()
        
        # Initialize result metadata
        moe_route: Optional[RouteResult] = None
        emotion_applied = False
        graph_expanded = 0
        forgotten_filtered = 0
        ptsd_flashback_triggered = False
        
        # Step 1: MoE routing (optional)
        if request.use_moe_routing and request.domains:
            try:
                moe_route = await self.router.route(
                    request.query,
                    request.domains,
                    top_k=3
                )
                logger.debug(f"MoE route: l1={moe_route.l1}, l2={moe_route.l2}")
            except Exception as e:
                logger.warning(f"MoE routing failed: {e}, using fallback")
                moe_route = RouteResult(l1=None, l2=[], confidence=0.0, fallback=True)
        
        # Determine domains to search
        domains_to_search = None
        if moe_route and not moe_route.fallback:
            # Include always_on domains + routed domains
            always_on = [d.id for d in (request.domains or []) if d.always_on]
            routed = ([moe_route.l1] if moe_route.l1 else []) + moe_route.l2
            domains_to_search = always_on + routed
            logger.debug(f"Searching domains: {domains_to_search}")
        
        # Step 2: Base recall (3-path: FTS + Pattern + Time)
        base_request = RecallRequest(
            query=request.query,
            agent_id=request.agent_id,
            scope=",".join(domains_to_search) if domains_to_search else "all",
            use_vector=True,
            use_graph=False,  # We'll do graph traversal separately
            performance_mode=request.performance_mode,
            max_results=request.top_k * 5  # Get more for filtering
        )
        
        # Use search method instead of recall
        base_result = await self.base_retriever.search(base_request)
        hits = base_result.hits
        logger.debug(f"Base recall: {len(hits)} hits")
        
        # Step 4: Graph traversal (if enabled)
        if request.use_graph and hits:
            start = time.time()
            initial_count = len(hits)
            hits = await self._graph_traversal(
                hits,
                hops=request.graph_hops,
                per_node=request.graph_per_node
            )
            graph_expanded = len(hits) - initial_count
            logger.debug(f"Graph traversal: +{graph_expanded} nodes")
        
        # Step 4: Emotion weighting (optional)
        if request.user_emotion and request.user_emotion.arousal > 0.3:
            hits = self._apply_emotion_weight(
                hits,
                request.user_emotion,
                weight=request.emotion_weight
            )
            emotion_applied = True
            logger.debug(f"Emotion weighting applied: {request.user_emotion.primary_emotion.value}")
        
        # Step 5: Emotion filtering (optional)
        if request.emotion_filter:
            initial_count = len(hits)
            hits = [
                hit for hit in hits
                if self._matches_emotion_filter(hit, request.emotion_filter)
            ]
            logger.debug(f"Emotion filtering: {initial_count} → {len(hits)} hits")
        
        # Step 6: FSRS forgetting (optional)
        if request.apply_forgetting:
            initial_count = len(hits)
            hits = self._apply_forgetting_curve(
                hits,
                threshold=request.forgetting_threshold
            )
            forgotten_filtered = initial_count - len(hits)
            logger.debug(f"Forgetting filter: {initial_count} → {len(hits)} hits")
        
        # Step 7: Sort and truncate
        hits.sort(key=lambda h: h.final_score, reverse=True)
        hits = hits[:request.top_k]
        
        # Step 8: PTSD flashback check (if user emotion is very negative)
        if (request.user_emotion and 
            request.user_emotion.valence < -0.5 and 
            random.random() < request.ptsd_flashback_prob):
            ptsd_flashback_triggered = True
            logger.info("PTSD flashback triggered")
            # In v3.0, we just flag it; actual flashback handling is in the API layer
        
        # Compute execution time
        end_time = datetime.now()
        took_ms = int((end_time - start_time).total_seconds() * 1000)
        
        result = RetrieveResultV3(
            query=request.query,
            hits=hits,
            took_ms=took_ms,
            moe_route=moe_route,
            emotion_applied=emotion_applied,
            graph_expanded=graph_expanded,
            forgotten_filtered=forgotten_filtered,
            ptsd_flashback_triggered=ptsd_flashback_triggered
        )
        
        logger.info(
            f"Retrieve completed in {took_ms}ms: {len(hits)} hits, "
            f"graph_expanded={graph_expanded}, forgotten_filtered={forgotten_filtered}"
        )
        
        return result
    
    async def _graph_traversal(
        self,
        seeds: List[RecallHit],
        hops: int = 2,
        per_node: int = 5
    ) -> List[RecallHit]:
        """Graph traversal from seed hits using entity_edges table.
        
        Args:
            seeds: Seed hits to start traversal from
            hops: Number of hops
            per_node: Nodes to retrieve per hop
        
        Returns:
            Expanded list of hits with graph neighbors
        """
        if not seeds:
            return []
        
        async with self._async_session() as session:
            # Collect unique chunk_ids from seeds
            chunk_ids = list(set(hit.chunk_id for hit in seeds if hit.chunk_id))
            
            if not chunk_ids:
                logger.debug("Graph traversal: No chunk IDs in seeds")
                return seeds
            
            # Query entity_edges connected to these chunks
            # Join with chunks to get the actual content
            from memos_graph.db.models import Chunk, EntityEdge, Entity
            
            query = (
                select(Chunk, EntityEdge)
                .join(EntityEdge, EntityEdge.chunk_id == Chunk.id)
                .where(Chunk.id.in_(chunk_ids))
                .limit(hops * per_node * len(chunk_ids))
            )
            
            result = await session.execute(query)
            rows = result.all()
            
            if not rows:
                logger.debug(f"Graph traversal: No entity edges found for {len(chunk_ids)} chunks")
                return seeds
            
            # Create RecallHit from graph neighbors
            expanded_hits = []
            seen_chunk_ids = set(chunk_ids)  # Already have these
            
            for chunk, edge in rows:
                if chunk.id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk.id)
                    
                    # Create a minimal RecallHit for the neighbor
                    neighbor_hit = RecallHit(
                        chunk_id=chunk.id,
                        content=chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                        score=edge.weight if edge.weight else 0.5,
                        final_score=edge.weight if edge.weight else 0.5,
                        metadata={
                            "edge_type": edge.edge_type,
                            "entity_id_1": edge.entity_id_1,
                            "entity_id_2": edge.entity_id_2,
                            "graph_hops": hops,
                        }
                    )
                    expanded_hits.append(neighbor_hit)
            
            logger.info(f"Graph traversal: {len(seeds)} seeds → {len(expanded_hits)} neighbors ({hops} hops)")
            
            # Return original seeds + expanded neighbors
            return seeds + expanded_hits
    
    def _apply_emotion_weight(
        self,
        hits: List[RecallHit],
        user_emotion: EmotionalState,
        weight: float = 0.2
    ) -> List[RecallHit]:
        """Apply emotion weighting to hits.
        
        Args:
            hits: List of recall hits
            user_emotion: User's current emotional state
            weight: Weight for emotion scoring
        
        Returns:
            Hits with updated final_score
        """
        for hit in hits:
            # Compute emotion similarity
            emotion_sim = self._emotion_similarity(user_emotion, hit)
            
            # Boost score for similar emotions
            hit.final_score *= (1.0 + weight * emotion_sim)
        
        return hits
    
    def _emotion_similarity(
        self,
        user_emotion: EmotionalState,
        hit: RecallHit
    ) -> float:
        """Compute emotion similarity between user and hit.
        
        Args:
            user_emotion: User's emotional state
            hit: Recall hit
        
        Returns:
            Similarity score in [0, 1]
        """
        # Extract hit emotion (if available in metadata)
        hit_emotion_str = hit.metadata.get("emotion") if hit.metadata else None
        
        if not hit_emotion_str:
            return 0.5  # Neutral similarity
        
        try:
            hit_emotion = EmotionType.from_string(hit_emotion_str)
        except ValueError:
            return 0.5
        
        # Same emotion → high similarity
        if user_emotion.primary_emotion == hit_emotion:
            return 1.0
        
        # Valence-based similarity
        valence_diff = abs(user_emotion.valence - self._emotion_valence(hit_emotion))
        return 1.0 - valence_diff
    
    def _emotion_valence(self, emotion: EmotionType) -> float:
        """Get default valence for an emotion type."""
        valence_map = {
            EmotionType.HAPPY: 0.8,
            EmotionType.SAD: -0.7,
            EmotionType.ANGRY: -0.6,
            EmotionType.SURPRISE: 0.2,
            EmotionType.THINK: 0.0,
            EmotionType.NEUTRAL: 0.0,
        }
        return valence_map.get(emotion, 0.0)
    
    def _matches_emotion_filter(
        self,
        hit: RecallHit,
        filter_emotion: EmotionType
    ) -> bool:
        """Check if hit matches emotion filter.
        
        Args:
            hit: Recall hit
            filter_emotion: Emotion to filter by
        
        Returns:
            True if hit matches filter
        """
        hit_emotion_str = hit.metadata.get("emotion")
        if not hit_emotion_str:
            return False
        
        try:
            hit_emotion = EmotionType.from_string(hit_emotion_str)
            return hit_emotion == filter_emotion
        except ValueError:
            return False
    
    def _apply_forgetting_curve(
        self,
        hits: List[RecallHit],
        threshold: float = 0.1
    ) -> List[RecallHit]:
        """Apply FSRS forgetting curve to hits.
        
        Args:
            hits: List of recall hits
            threshold: Retrievability threshold
        
        Returns:
            Filtered hits (forgotten removed)
        """
        now = datetime.now()
        filtered = []
        
        for hit in hits:
            # Extract stability from metadata (if available)
            stability_data = hit.metadata.get("stability")
            
            if stability_data:
                # Reconstruct MemoryStability
                stability = MemoryStability(
                    stability=stability_data.get("stability", 7.0),
                    retrievability=stability_data.get("retrievability", 1.0),
                    access_count=stability_data.get("access_count", 0),
                    emotional_arousal=stability_data.get("emotional_arousal", 0.0)
                )
                
                # Apply decay
                stability = self.forgetting.apply_decay(stability, now)
                
                # Check if forgotten
                if not self.forgetting.should_forget(stability):
                    # Update hit score with retrievability
                    hit.final_score *= stability.retrievability
                    filtered.append(hit)
            else:
                # No stability data, keep hit
                filtered.append(hit)
        
        return filtered


# Convenience function
def create_retrieve_engine_v3(
    db_url: str,
    embedding_service: Any,
    llm_client: Optional[Any] = None,
    **kwargs
) -> RetrieveEngineV3:
    """Create v3.0 Retrieve Engine.
    
    Args:
        db_url: Database URL
        embedding_service: Embedding service
        llm_client: Optional LLM client
        **kwargs: Additional arguments for RetrieveEngineV3
    
    Returns:
        Configured RetrieveEngineV3 instance
    """
    return RetrieveEngineV3(
        db_url=db_url,
        embedding_service=embedding_service,
        llm_client=llm_client,
        **kwargs
    )
