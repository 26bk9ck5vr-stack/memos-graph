"""Cross-Encoder 重排器 - 替代 LLM 重排"""

from sentence_transformers import CrossEncoder
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

class CrossEncoderReranker:
    """使用 Cross-Encoder 进行文档重排"""
    
    def __init__(self, model_name: str = 'BAAI/bge-reranker-large'):
        """
        初始化 Cross-Encoder
        
        Args:
            model_name: 模型名称
                推荐选项:
                - BAAI/bge-reranker-large: 中文支持好，CPU 友好
                - BAAI/bge-reranker-base: 更快，精度略低
                - cross-encoder/ms-marco-MiniLM-L-6-v2: 英文最优
        """
        logger.info(f"Loading Cross-Encoder model: {model_name}")
        self.model = CrossEncoder(model_name)
        self.model_name = model_name
        logger.info(f"Model loaded successfully")
    
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = None
    ) -> List[int]:
        """
        重排文档
        
        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回前 K 个结果 (None 表示返回全部)
            
        Returns:
            重排后的索引列表
        """
        if not documents:
            return []
        
        # 构建 (query, doc) 对
        pairs = [[query, doc[:512]] for doc in documents]  # 截断避免过长
        
        # 预测分数
        scores = self.model.predict(pairs)
        
        # 排序
        indices = list(range(len(scores)))
        indices.sort(key=lambda i: scores[i], reverse=True)
        
        if top_k:
            indices = indices[:top_k]
        
        return indices
    
    def rerank_with_scores(
        self,
        query: str,
        documents: List[str],
        top_k: int = None
    ) -> List[Tuple[int, float]]:
        """
        重排文档并返回分数
        
        Returns:
            [(索引，分数), ...] 列表
        """
        if not documents:
            return []
        
        pairs = [[query, doc[:512]] for doc in documents]
        scores = self.model.predict(pairs)
        
        indices_scores = list(enumerate(scores))
        indices_scores.sort(key=lambda x: x[1], reverse=True)
        
        if top_k:
            indices_scores = indices_scores[:top_k]
        
        return indices_scores
