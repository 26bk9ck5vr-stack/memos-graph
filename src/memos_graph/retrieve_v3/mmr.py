"""MMR (Maximal Marginal Relevance) - 多样性重排序"""

import numpy as np
import logging
from typing import List, Tuple, Any

logger = logging.getLogger(__name__)


class MMRReranker:
    """MMR 多样性重排序器"""
    
    def __init__(self, lambda_param: float = 0.7):
        if not 0 <= lambda_param <= 1:
            raise ValueError("lambda_param 必须在 0-1 之间")
        self.lambda_param = lambda_param
        logger.info(f"MMRReranker 初始化 (lambda={lambda_param})")
    
    def select(self, documents: List[Tuple[Any, np.ndarray]], query_embedding: np.ndarray, top_k: int) -> List[Any]:
        """使用 MMR 选择多样性文档"""
        if not documents or top_k <= 0:
            return []
        
        n_docs = len(documents)
        top_k = min(top_k, n_docs)
        
        # 计算相关性
        doc_embeddings = np.array([doc[1] for doc in documents])
        similarities = self._cosine_similarity(doc_embeddings, query_embedding)
        
        # MMR 选择
        selected = []
        remaining = list(range(n_docs))
        
        while len(selected) < top_k and remaining:
            best_idx = None
            best_score = float('-inf')
            
            for idx in remaining:
                rel = similarities[idx]
                redundancy = max([self._cosine_similarity(documents[idx][1], documents[s][1]) for s in selected], default=0)
                score = self.lambda_param * rel - (1 - self.lambda_param) * redundancy
                
                if score > best_score:
                    best_score = score
                    best_idx = idx
            
            if best_idx is not None:
                selected.append(best_idx)
                remaining.remove(best_idx)
        
        return [documents[i][0] for i in selected]
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a, axis=-1) if a.ndim > 1 else np.linalg.norm(a)
        norm_b = np.linalg.norm(b, axis=-1) if b.ndim > 1 else np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))


if __name__ == "__main__":
    print("MMR Reranker 模块加载成功")
