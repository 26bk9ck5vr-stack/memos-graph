"""LLM Rerank - 使用 LLM 进行智能重排序"""

import httpx
import logging
import re
from typing import List

logger = logging.getLogger(__name__)


class LLMSimpleReranker:
    """简单的 LLM 重排序器"""
    
    def __init__(
        self,
        api_key: str,
        model: str = "Qwen/Qwen3-8B",
        base_url: str = "https://api.siliconflow.cn/v1",
        timeout: float = 60.0
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        logger.info(f"LLMSimpleReranker 初始化 (model={model})")
    
    def rerank(self, query: str, documents: List[str], top_k: int = None) -> List[int]:
        """使用 LLM 重排文档"""
        if not documents:
            return []
        
        prompt = self._build_prompt(query, documents)
        
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                    "temperature": 0.1
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            llm_output = result["choices"][0]["message"]["content"]
            indices = self._parse_output(llm_output, len(documents))
            return indices[:top_k] if top_k else indices
        except Exception as e:
            logger.error(f"LLM Rerank 失败：{e}")
            return list(range(len(documents)))
    
    def _build_prompt(self, query: str, documents: List[str]) -> str:
        doc_list = "\n".join([f"[{i}] {doc[:100]}..." for i, doc in enumerate(documents)])
        return f"""根据查询的相关性对文档排序。

查询：{query}

文档:
{doc_list}

输出索引列表，格式：[2, 0, 1]
"""
    
    def _parse_output(self, output: str, num_docs: int) -> List[int]:
        match = re.search(r'\[([\d,\s]+)\]', output)
        if match:
            indices = [int(x.strip()) for x in match.group(1).split(',') if x.strip().isdigit()]
            valid = [i for i in indices if 0 <= i < num_docs]
            if valid:
                return valid
        return list(range(num_docs))


if __name__ == "__main__":
    print("LLM Reranker 模块加载成功")
