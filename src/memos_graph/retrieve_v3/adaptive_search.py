"""Adaptive Hybrid Search - 自适应混合检索优化"""

import logging
from typing import Dict, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class QueryIntent:
    """Query intent"""
    intent_type: str
    confidence: float
    keywords: List[str]


class AdaptiveHybridSearch:
    """Adaptive hybrid search optimizer"""
    
    def __init__(self):
        self.default_weights = {"vector": 0.6, "fts": 0.3, "time": 0.1}
        self.intent_weights = {
            "semantic": {"vector": 0.7, "fts": 0.2, "time": 0.1},
            "factual": {"vector": 0.2, "fts": 0.7, "time": 0.1},
            "temporal": {"vector": 0.3, "fts": 0.2, "time": 0.5},
            "mixed": self.default_weights
        }
        logger.info("AdaptiveHybridSearch initialized")
    
    def classify(self, query: str) -> QueryIntent:
        """Classify query intent"""
        q = query.lower()
        
        temporal_kw = ["什么时候", "何时", "最近", "最新", "今天", "时间"]
        factual_kw = ["什么是", "定义", "谁", "哪里"]
        semantic_kw = ["如何", "怎么", "为什么", "分析"]
        
        t_count = sum(1 for kw in temporal_kw if kw in q)
        f_count = sum(1 for kw in factual_kw if kw in q)
        s_count = sum(1 for kw in semantic_kw if kw in q)
        
        counts = {"temporal": t_count, "factual": f_count, "semantic": s_count}
        max_count = max(counts.values())
        
        if max_count == 0:
            intent_type = "mixed"
            confidence = 0.5
        else:
            intent_type = max(counts, key=counts.get)
            confidence = min(1.0, max_count / 3.0)
        
        matched = [kw for kw in temporal_kw + factual_kw + semantic_kw if kw in q]
        
        return QueryIntent(intent_type=intent_type, confidence=confidence, keywords=matched)
    
    def get_weights(self, query: str) -> Dict[str, float]:
        """Get adaptive weights"""
        intent = self.classify(query)
        return self.intent_weights.get(intent.intent_type, self.default_weights)
    
    def get_top_k(self, query: str, base_k: int = 20) -> int:
        """Get dynamic top_k"""
        intent = self.classify(query)
        
        if intent.intent_type == "factual":
            return max(5, int(base_k * 0.5))
        elif intent.intent_type == "temporal":
            return max(10, int(base_k * 0.8))
        elif intent.intent_type == "semantic":
            return int(base_k * 1.2)
        
        return base_k


if __name__ == "__main__":
    print("Adaptive Hybrid Search loaded")
    
    adaptive = AdaptiveHybridSearch()
    for q in ["什么是 AI", "最近新闻", "如何学习"]:
        intent = adaptive.classify(q)
        print(f"{q}: {intent.intent_type} (conf={intent.confidence:.2f})")
