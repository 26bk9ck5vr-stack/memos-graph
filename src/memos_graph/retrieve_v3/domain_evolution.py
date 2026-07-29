"""Domain Evolution - 领域自动演化系统"""

import numpy as np
from typing import List, Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Domain:
    """领域定义"""
    id: str
    label: str
    prototype_vec: np.ndarray
    always_on: bool = False
    memory_count: int = 0


class DomainEvolution:
    """领域自动演化系统"""
    
    def __init__(self, min_samples: int = 5, eps: float = 0.3):
        self.min_samples = min_samples
        self.eps = eps
        logger.info(f"DomainEvolution initialized")
    
    def discover(self, memories: List[Dict], existing_domains: List[Domain] = None) -> List[Domain]:
        """从记忆中自动发现领域"""
        if not memories or len(memories) < self.min_samples:
            return existing_domains or []
        
        try:
            from sklearn.cluster import DBSCAN
        except ImportError:
            logger.warning("sklearn not available")
            return existing_domains or []
        
        embeddings = np.array([m["embedding"] for m in memories])
        clustering = DBSCAN(eps=self.eps, min_samples=self.min_samples, metric="cosine")
        labels = clustering.fit_predict(embeddings)
        
        unique_labels = set(labels) - {-1}
        new_domains = []
        
        for label in unique_labels:
            mask = labels == label
            cluster_embeddings = embeddings[mask]
            prototype = np.mean(cluster_embeddings, axis=0)
            
            domain = Domain(
                id=f"auto_{label}",
                label=f"Auto Domain {label}",
                prototype_vec=prototype,
                memory_count=int(mask.sum())
            )
            new_domains.append(domain)
        
        return (existing_domains or []) + new_domains
    
    def merge_similar(self, domains: List[Domain], threshold: float = 0.85) -> List[Domain]:
        """合并相似领域"""
        if len(domains) <= 1:
            return domains
        
        merged = []
        used = [False] * len(domains)
        
        for i, d1 in enumerate(domains):
            if used[i]:
                continue
            
            similar = [d1]
            used[i] = True
            
            for j, d2 in enumerate(domains[i+1:], i+1):
                if used[j]:
                    continue
                
                sim = np.dot(d1.prototype_vec, d2.prototype_vec) / (
                    np.linalg.norm(d1.prototype_vec) * np.linalg.norm(d2.prototype_vec) + 1e-8
                )
                
                if sim > threshold:
                    similar.append(d2)
                    used[j] = True
            
            if len(similar) > 1:
                merged_proto = np.mean([d.prototype_vec for d in similar], axis=0)
                merged_label = "/".join([d.label for d in similar[:3]])
                merged_count = sum(d.memory_count for d in similar)
                
                merged.append(Domain(
                    id=f"merged_{similar[0].id}",
                    label=merged_label,
                    prototype_vec=merged_proto,
                    memory_count=merged_count
                ))
            else:
                merged.append(d1)
        
        return merged


if __name__ == "__main__":
    print("Domain Evolution loaded")
