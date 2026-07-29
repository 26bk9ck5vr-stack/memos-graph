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
        
        # 计算所有文档与查询的相关性
        doc_embeddings = np.array([doc[1] for doc in documents])
        if doc_embeddings.ndim == 1:
            doc_embeddings = doc_embeddings.reshape(1, -1)
        
        similarities = self._cosine_similarity_batch(doc_embeddings, query_embedding)
        
        # MMR 选择
        selected = []
        remaining = list(range(n_docs))
        
        while len(selected) < top_k and remaining:
            best_idx = None
            best_score = float('-inf')
            
            for idx in remaining:
                rel = similarities[idx]
                
                # 计算与已选文档的最大冗余度
                if selected:
                    redundancies = [
                        self._cosine_similarity(documents[idx][1], documents[s][1])
                        for s in selected
                    ]
                    max_redundancy = max(redundancies)
                else:
                    max_redundancy = 0
                
                # MMR 分数
                score = self.lambda_param * rel - (1 - self.lambda_param) * max_redundancy
                
                if score > best_score:
                    best_score = score
                    best_idx = idx
            
            if best_idx is not None:
                selected.append(best_idx)
                remaining.remove(best_idx)
        
        return [documents[i][0] for i in selected]
    
    def _cosine_similarity_batch(self, vectors: np.ndarray, query: np.ndarray) -> np.ndarray:
        """计算一批向量与查询的余弦相似度"""
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        
        norm_vectors = np.linalg.norm(vectors, axis=1, keepdims=True)
        norm_query = np.linalg.norm(query)
        
        if norm_query == 0:
            return np.zeros(len(vectors))
        
        # 避免除以零
        norm_vectors = np.where(norm_vectors == 0, 1e-8, norm_vectors)
        
        similarities = np.dot(vectors, query) / (norm_vectors.flatten() * norm_query)
        return similarities
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """计算两个向量的余弦相似度"""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(np.dot(a, b) / (norm_a * norm_b))


if __name__ == "__main__":
    print("MMR Reranker loaded")
