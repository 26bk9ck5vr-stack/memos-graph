"""RRF (Reciprocal Rank Fusion) - 多路召回融合算法

RRF 公式:
    RRF_score(d) = Σ (1 / (k + rank_i(d)))
    
其中:
    - k: 平滑常数 (默认 60)
    - rank_i(d): 文档 d 在第 i 路召回中的排名

Usage:
    rrf = RRFFusion(k=60)
    
    # 多路召回结果
    results = {
        "vector": [(doc1, 0.9), (doc2, 0.8), ...],
        "fts": [(doc2, 0.7), (doc1, 0.6), ...],
        "graph": [(doc3, 0.5), (doc1, 0.4), ...]
    }
    
    # 融合
    fused = rrf.fuse(results, top_k=10)
"""

import logging
from typing import List, Dict, Any, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class RRFFusion:
    """Reciprocal Rank Fusion - 多路召回结果融合"""
    
    def __init__(self, k: int = 60):
        """
        初始化 RRF 融合器
        
        Args:
            k: 平滑常数，控制排名对分数的影响
               - k 越大，排名影响越小
               - k 越小，排名影响越大
               - 经验值：60 (论文推荐)
        """
        self.k = k
        logger.info(f"RRFFusion 初始化完成 (k={k})")
    
    def fuse(
        self,
        result_lists: Dict[str, List[Any]],
        top_k: int = None
    ) -> List[Tuple[Any, float]]:
        """
        融合多路召回结果
        
        Args:
            result_lists: 多路召回结果字典
                         {
                           "vector": [(doc_id, score), ...],
                           "fts": [(doc_id, score), ...],
                           "graph": [(doc_id, score), ...]
                         }
            top_k: 返回前 K 个结果 (None 表示返回全部)
        
        Returns:
            融合后的结果列表 [(doc_id, rrf_score), ...]
        """
        if not result_lists:
            return []
        
        # 统计每个文档的 RRF 分数
        rrf_scores = defaultdict(float)
        
        for source, results in result_lists.items():
            if not results:
                continue
            
            # 为每个文档计算 RRF 贡献
            for rank, (doc_id, _) in enumerate(results, start=1):
                rrf_score = 1.0 / (self.k + rank)
                rrf_scores[doc_id] += rrf_score
        
        # 按 RRF 分数排序
        sorted_docs = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 截取 top_k
        if top_k is not None:
            sorted_docs = sorted_docs[:top_k]
        
        logger.debug(f"RRF 融合完成：{len(result_lists)} 路 → {len(sorted_docs)} 条结果")
        
        return sorted_docs
    
    def fuse_with_metadata(
        self,
        result_lists: Dict[str, List[Tuple[Any, float, Dict]]],
        top_k: int | None = None
    ) -> List[Tuple[Any, float, Dict]]:
        """
        融合多路召回结果 (保留元数据)
        
        Args:
            result_lists: 多路召回结果字典 (带元数据)
                         {
                           "vector": [(doc_id, score, metadata), ...],
                           ...
                         }
            top_k: 返回前 K 个结果
        
        Returns:
            融合后的结果列表 [(doc_id, rrf_score, metadata), ...]
        """
        if not result_lists:
            return []
        
        # 统计 RRF 分数和元数据
        rrf_scores = defaultdict(float)
        doc_metadata = {}  # 保存每个文档的元数据
        
        for source, results in result_lists.items():
            if not results:
                continue
            
            for rank, (doc_id, score, metadata) in enumerate(results, start=1):
                rrf_score = 1.0 / (self.k + rank)
                rrf_scores[doc_id] += rrf_score
                
                # 保存元数据 (如果已存在，合并)
                if doc_id not in doc_metadata:
                    doc_metadata[doc_id] = {
                        "sources": [],
                        "original_scores": {},
                        "ranks": {}
                    }
                
                doc_metadata[doc_id]["sources"].append(source)
                doc_metadata[doc_id]["original_scores"][source] = score
                doc_metadata[doc_id]["ranks"][source] = rank
                
                # 合并其他元数据
                for key, value in metadata.items():
                    if key not in ["sources", "original_scores", "ranks"]:
                        doc_metadata[doc_id][key] = value
        
        # 按 RRF 分数排序
        sorted_docs = []
        for doc_id, rrf_score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
            metadata = doc_metadata.get(doc_id, {})
            sorted_docs.append((doc_id, rrf_score, metadata))
        
        # 截取 top_k
        if top_k is not None:
            sorted_docs = sorted_docs[:top_k]
        
        logger.debug(f"RRF 融合 (带元数据) 完成：{len(result_lists)} 路 → {len(sorted_docs)} 条结果")
        
        return sorted_docs


class AdaptiveRRFFusion(RRFFusion):
    """自适应 RRF 融合 - 根据各召回源的质量动态调整权重"""
    
    def __init__(self, k: int = 60, weights: Dict[str, float] | None = None):
        """
        初始化自适应 RRF 融合器
        
        Args:
            k: 平滑常数
            weights: 各召回源的权重 (默认等权重)
                    {"vector": 1.0, "fts": 0.8, "graph": 0.6}
        """
        super().__init__(k)
        self.weights = weights or {}
        logger.info(f"AdaptiveRRFFusion 初始化完成 (k={k}, weights={weights})")
    
    def fuse(
        self,
        result_lists: Dict[str, List[Any]],
        top_k: int = None
    ) -> List[Tuple[Any, float]]:
        """融合时应用权重"""
        if not result_lists:
            return []
        
        rrf_scores = defaultdict(float)
        
        for source, results in result_lists.items():
            if not results:
                continue
            
            # 获取该召回源的权重 (默认 1.0)
            weight = self.weights.get(source, 1.0)
            
            for rank, (doc_id, _) in enumerate(results, start=1):
                rrf_score = (1.0 / (self.k + rank)) * weight
                rrf_scores[doc_id] += rrf_score
        
        sorted_docs = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        
        if top_k is not None:
            sorted_docs = sorted_docs[:top_k]
        
        logger.debug(f"自适应 RRF 融合完成：{len(result_lists)} 路 → {len(sorted_docs)} 条结果")
        
        return sorted_docs
