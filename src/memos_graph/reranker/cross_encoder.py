"""Cross-Encoder 重排器 - 替代 LLM 重排"""

from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

class CrossEncoderReranker:
    """使用 Cross-Encoder 进行文档重排"""
    
    def __init__(self, model_name: str = 'BAAI/bge-reranker-base'):
        """
        初始化 Cross-Encoder
        
        Args:
            model_name: 模型名称
                推荐选项:
                - BAAI/bge-reranker-base: 快速，中文支持好 (推荐)
                - BAAI/bge-reranker-large: 精度更高，但更慢
        """
        logger.info(f"Loading Cross-Encoder model: {model_name}")
        
        # 使用 transformers 直接加载（比 sentence-transformers 更可靠）
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.eval()  # 设置为评估模式
        
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
        
        # 使用 transformers 推理
        inputs = self.tokenizer(pairs, padding=True, truncation=True, return_tensors='pt', max_length=512)
        with torch.no_grad():
            scores = self.model(**inputs).logits.squeeze()
        
        # 处理单个文档的情况
        if len(documents) == 1:
            scores = [scores.item()]
        else:
            scores = scores.tolist()
        
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
        inputs = self.tokenizer(pairs, padding=True, truncation=True, return_tensors='pt', max_length=512)
        
        with torch.no_grad():
            scores = self.model(**inputs).logits.squeeze()
        
        if len(documents) == 1:
            scores = [scores.item()]
        else:
            scores = scores.tolist()
        
        indices_scores = list(enumerate(scores))
        indices_scores.sort(key=lambda x: x[1], reverse=True)
        
        if top_k:
            indices_scores = indices_scores[:top_k]
        
        return indices_scores
