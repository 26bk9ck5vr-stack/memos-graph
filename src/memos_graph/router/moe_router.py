"""MoE Router implementation for memos-graph v3.0.

Implements Mixture of Experts routing:
1. CentroidRouter (hot path): Vector similarity routing, <80ms
2. LLMRouter (cold start): LLM-based domain classification, fallback

Usage:
    router = MoERouter(embedding_service, llm_client, mode="hybrid")
    result = await router.route(query, domains, top_k=3)
    
    # Use result.l1 and result.l2 to filter search domains
    if not result.fallback:
        domains_to_search = [result.l1] + result.l2
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Domain:
    """Memory domain (similar to Nemos domain).
    
    Attributes:
        id: Unique domain identifier
        label: Human-readable label
        prototype_vec: Domain centroid vector (for CentroidRouter)
        always_on: If True, always include in search (e.g., "global" domain)
    """
    id: str
    label: str
    prototype_vec: Optional[np.ndarray] = None
    always_on: bool = False
    
    def __post_init__(self):
        """Validate prototype_vec if provided."""
        if self.prototype_vec is not None:
            if not isinstance(self.prototype_vec, np.ndarray):
                self.prototype_vec = np.array(self.prototype_vec)


@dataclass
class RouteResult:
    """Routing result.
    
    Attributes:
        l1: Primary domain (most relevant)
        l2: Adjacent domains (up to top_k-1)
        confidence: Confidence score (0-1)
        fallback: If True, fallback to full database search
    """
    l1: Optional[str]
    l2: List[str] = field(default_factory=list)
    confidence: float = 0.0
    fallback: bool = False


class MoERouter:
    """Mixture of Experts Router.
    
    Two modes:
    1. CentroidRouter (hot path): Vector similarity routing, <80ms
    2. LLMRouter (cold start): LLM-based domain classification, fallback
    
    Attributes:
        embedding: Embedding service for vector computation
        llm: LLM client for classification (optional, for LLMRouter)
        mode: Routing mode ("centroid" | "llm" | "hybrid")
    """
    
    def __init__(
        self,
        embedding_service: Any,
        llm_client: Optional[Any] = None,
        mode: str = "hybrid"
    ):
        """Initialize MoE Router.
        
        Args:
            embedding_service: Service with async embed(text) -> np.ndarray
            llm_client: Optional LLM client with async generate_json(prompt) -> dict
            mode: Routing mode
                - "centroid": Only CentroidRouter (fast, requires prototype_vec)
                - "llm": Only LLMRouter (slower, no prototype_vec needed)
                - "hybrid": CentroidRouter first, fallback to LLMRouter (recommended)
        """
        self.embedding = embedding_service
        self.llm = llm_client
        self.mode = mode
        
        if mode not in ["centroid", "llm", "hybrid"]:
            raise ValueError(f"Invalid mode: {mode}. Must be 'centroid', 'llm', or 'hybrid'")
    
    async def route(
        self,
        query: str,
        domains: List[Domain],
        top_k: int = 3
    ) -> RouteResult:
        """Route query to relevant domains.
        
        Args:
            query: User query string
            domains: List of candidate domains
            top_k: Number of adjacent domains to return (including l1)
        
        Returns:
            RouteResult with l1, l2, confidence, and fallback flag
        """
        # Filter out always_on domains (they're always included)
        routable_domains = [d for d in domains if not d.always_on]
        
        if not routable_domains:
            logger.debug("No routable domains, using fallback")
            return RouteResult(l1=None, l2=[], confidence=0.0, fallback=True)
        
        # Mode 1: CentroidRouter (vector similarity)
        if self.mode in ["centroid", "hybrid"]:
            try:
                query_vec = await self.embedding.embed(query)
                return self._centroid_route(query_vec, routable_domains, top_k)
            except Exception as e:
                logger.warning(f"CentroidRouter failed: {e}")
                if self.mode == "centroid":
                    raise
                # hybrid mode: fallback to LLMRouter
        
        # Mode 2: LLMRouter (fallback)
        if self.mode in ["llm", "hybrid"]:
            if self.llm is None:
                logger.warning("LLMRouter requested but no llm_client provided")
                return RouteResult(l1=None, l2=[], confidence=0.0, fallback=True)
            return await self._llm_route(query, routable_domains, top_k)
        
        # Should not reach here
        return RouteResult(l1=None, l2=[], confidence=0.0, fallback=True)
    
    def _centroid_route(
        self,
        query_vec: np.ndarray,
        domains: List[Domain],
        top_k: int
    ) -> RouteResult:
        """CentroidRouter: Vector similarity routing.
        
        Computes cosine similarity between query vector and domain prototype vectors.
        
        Args:
            query_vec: Query embedding vector
            domains: List of candidate domains
            top_k: Number of domains to return
        
        Returns:
            RouteResult with top-k domains
        """
        scored = []
        
        for domain in domains:
            # Handle cold start: domains without prototype_vec
            if domain.prototype_vec is None:
                logger.debug(f"Domain {domain.id} has no prototype_vec, skipping")
                continue
            
            # Compute cosine similarity
            sim = self._cosine_similarity(query_vec, domain.prototype_vec)
            
            # Only keep positive similarities
            if sim > 0:
                scored.append((domain.id, sim))
        
        # Sort by similarity (descending)
        scored.sort(key=lambda x: x[1], reverse=True)
        
        if not scored:
            logger.debug("No domains with positive similarity, using fallback")
            return RouteResult(l1=None, l2=[], confidence=0.0, fallback=True)
        
        # Extract top-k
        l1 = scored[0][0]
        l2 = [x[0] for x in scored[1:top_k]]
        
        # Normalize confidence: cosine ∈ [-1, 1] → [0, 1]
        confidence = (scored[0][1] + 1) / 2
        
        logger.debug(f"CentroidRouter: l1={l1}, l2={l2}, confidence={confidence:.3f}")
        
        return RouteResult(l1=l1, l2=l2, confidence=confidence, fallback=False)
    
    async def _llm_route(
        self,
        query: str,
        domains: List[Domain],
        top_k: int
    ) -> RouteResult:
        """LLMRouter: LLM-based domain classification (fallback).
        
        Uses LLM to classify query into domains.
        
        Args:
            query: User query string
            domains: List of candidate domains
            top_k: Number of domains to return
        
        Returns:
            RouteResult with classified domains
        """
        # Build domain list
        domain_list = "\n".join([
            f"- {d.id}: {d.label}"
            for d in domains
        ])
        
        # Build prompt
        prompt = f"""You are a memory domain router. Given a user query and a list of candidate domains,
select the most relevant primary domain (L1) and up to {top_k - 1} adjacent domains (L2).

Candidate domains:
{domain_list}

Output strict JSON (no markdown fences):
{{
  "l1": "<domain_id or null>",
  "l2": ["<id>", ...],
  "confidence": <0-1>
}}

Query: {query}
"""
        
        try:
            # Call LLM
            response = await self.llm.generate_json(prompt)
            
            # Parse response
            l1 = response.get("l1")
            l2 = response.get("l2", [])[:top_k - 1] if l1 else []
            confidence = response.get("confidence", 0.5)
            
            # Validate l1
            if l1 and l1 not in [d.id for d in domains]:
                logger.warning(f"LLM returned invalid domain: {l1}")
                l1 = None
            
            logger.debug(f"LLMRouter: l1={l1}, l2={l2}, confidence={confidence:.3f}")
            
            return RouteResult(l1=l1, l2=l2, confidence=confidence, fallback=(l1 is None))
        
        except Exception as e:
            logger.error(f"LLMRouter failed: {e}")
            return RouteResult(l1=None, l2=[], confidence=0.0, fallback=True)
    
    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
        
        Returns:
            Cosine similarity in [-1, 1]
        """
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(np.dot(vec1, vec2) / (norm1 * norm2))
    
    def add_domain(self, domain: Domain):
        """Add a new domain dynamically.
        
        Args:
            domain: Domain to add
        """
        # This is a placeholder - in v3.0, domains are static
        # v3.1 will implement DomainEvolution for automatic domain management
        logger.info(f"Added domain: {domain.id}")
    
    def remove_domain(self, domain_id: str):
        """Remove a domain dynamically.
        
        Args:
            domain_id: ID of domain to remove
        """
        # Placeholder for v3.1
        logger.info(f"Removed domain: {domain_id}")


# Convenience function for creating router
def create_router(
    embedding_service: Any,
    llm_client: Optional[Any] = None,
    mode: str = "hybrid"
) -> MoERouter:
    """Create a MoE Router.
    
    Args:
        embedding_service: Embedding service
        llm_client: Optional LLM client
        mode: Routing mode
    
    Returns:
        Configured MoERouter instance
    """
    return MoERouter(embedding_service, llm_client, mode)
