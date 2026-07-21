"""SiliconFlow Rerank API 重排器 - 使用 BAAI/bge-reranker-v2-m3"""

import httpx
import logging
from typing import List

logger = logging.getLogger(__name__)

class SiliconFlowReranker:
    """使用 SiliconFlow API 进行文档重排"""
    
    def __init__(
        self,
        api_key: str,
        model: str = "BAAI/bge-reranker-v2-m3",
        base_url: str = "https://api.siliconflow.cn/v1/rerank",
        timeout: float = 30.0
    ):
        """
        初始化 SiliconFlow Reranker
        
        Args:
            api_key: SiliconFlow API Key
            model: 模型名称 (默认：BAAI/bge-reranker-v2-m3)
            base_url: API 基础 URL
            timeout: 超时时间 (秒)
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        
        logger.info(f"SiliconFlow Reranker 初始化完成")
        logger.info(f"  模型：{model}")
        logger.info(f"  API URL: {base_url}")
    
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
        
        try:
            # 构建请求
            payload = {
                "model": self.model,
                "query": query,
                "documents": documents,
                "top_n": top_k or len(documents),
                "return_documents": False,
                "max_chunks_per_doc": 1
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # 调用 API
            response = httpx.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            # 解析结果
            # SiliconFlow 返回格式：
            # {
            #   "results": [
            #     {"index": 2, "score": 0.95, "document": "..."},
            #     {"index": 0, "score": 0.87, "document": "..."},
            #     {"index": 1, "score": 0.76, "document": "..."}
            #   ]
            # }
            
            reranked_indices = [r["index"] for r in result.get("results", [])]
            
            logger.debug(f"Rerank 完成：{len(documents)} 条 → {len(reranked_indices)} 条")
            
            return reranked_indices
            
        except httpx.HTTPError as e:
            logger.error(f"SiliconFlow Rerank API 调用失败：{e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"  响应：{e.response.text}")
            # 失败时返回原始顺序
            return list(range(len(documents)))
            
        except Exception as e:
            logger.error(f"Rerank 异常：{e}")
            # 异常时返回原始顺序
            return list(range(len(documents)))
