"""memos-graph LLM client for 35B infinite calls."""

import httpx
import logging
from typing import Any

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM client for 35B infinite calls."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        # Create httpx client (no proxy needed for direct connection)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=httpx.Timeout(timeout),
            trust_env=False,  # Don't use proxy from environment
        )

    async def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        """Send chat completion request."""
        try:
            resp = await self._client.post(
                "/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    **kwargs,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPError as e:
            logger.error(f"LLM request failed: {e}")
            raise

    async def extract_entities(self, text: str) -> dict[str, Any]:
        """Extract entities and relations from text."""
        from .prompts.entity_extract import ENTITY_EXTRACT_PROMPT

        messages = [
            {"role": "system", "content": ENTITY_EXTRACT_PROMPT},
            {"role": "user", "content": text},
        ]
        result = await self.chat(messages, temperature=0.1)
        return self._parse_json(result)

    async def extract_promise(self, text: str) -> dict[str, Any] | None:
        """Extract promise from text."""
        from .prompts.promise_extract import PROMISE_EXTRACT_PROMPT

        messages = [
            {"role": "system", "content": PROMISE_EXTRACT_PROMPT},
            {"role": "user", "content": text},
        ]
        result = await self.chat(messages, temperature=0.1)
        return self._parse_json(result)

    async def summarize_event(self, text: str) -> dict[str, Any]:
        """Summarize event from text."""
        from .prompts.event_summarize import EVENT_SUMMARIZE_PROMPT

        messages = [
            {"role": "system", "content": EVENT_SUMMARIZE_PROMPT},
            {"role": "user", "content": text},
        ]
        result = await self.chat(messages, temperature=0.3)
        return self._parse_json(result)

    async def generate_heartbeat(
        self,
        agent_state: dict[str, Any],
        recent_events: list[dict[str, Any]],
    ) -> str:
        """Generate heartbeat message."""
        from .prompts.heartbeat_generate import HEARTBEAT_GENERATE_PROMPT

        messages = [
            {"role": "system", "content": HEARTBEAT_GENERATE_PROMPT},
            {"role": "user", "content": f"State: {agent_state}\nRecent: {recent_events}"},
        ]
        return await self.chat(messages, temperature=0.7)

    async def merge_profiles(
        self,
        profiles: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Merge multiple user profiles."""
        from .prompts.profile_merge import PROFILE_MERGE_PROMPT

        messages = [
            {"role": "system", "content": PROFILE_MERGE_PROMPT},
            {"role": "user", "content": str(profiles)},
        ]
        result = await self.chat(messages, temperature=0.3)
        return self._parse_json(result)

    async def expand_query(self, query: str) -> list[str]:
        """Expand query for better recall."""
        from .prompts.query_expand import QUERY_EXPAND_PROMPT

        messages = [
            {"role": "system", "content": QUERY_EXPAND_PROMPT},
            {"role": "user", "content": query},
        ]
        result = await self.chat(messages, temperature=0.5)
        return [q.strip() for q in result.split("\n") if q.strip()]

    async def rerank_documents(self, query: str, contents: list[str], top_k: int) -> list[int]:
        """LLM 重排文档，返回排序后的索引列表。
        
        Args:
            query: 查询文本
            contents: 文档内容列表（每条已截断）
            top_k: 返回前 K 个结果
            
        Returns:
            排序后的索引列表
        """
        # 构建重排 prompt
        docs_text = "\n\n".join([f"[{i}] {content}" for i, content in enumerate(contents)])
        prompt = f"""你是一个智能排序助手。请根据查询的相关性和文档质量，对以下文档进行排序。

查询：{query}

文档列表：
{docs_text}

请返回排序后的文档索引列表（从最相关到最不相关），只返回 JSON 数组格式，例如：[2, 0, 1, 3]

排序标准：
1. 与查询的相关性
2. 信息完整性
3. 内容质量

返回格式：[索引 1, 索引 2, 索引 3, ...]"""

        messages = [
            {"role": "system", "content": "你是一个智能文档排序助手。返回 JSON 数组格式的排序结果。"},
            {"role": "user", "content": prompt},
        ]
        
        try:
            result = await self.chat(messages, temperature=0.1)
            # 解析 JSON 数组
            import json
            import re
            match = re.search(r"\[.*\]", result, re.DOTALL)
            if match:
                indices = json.loads(match.group())
                if isinstance(indices, list) and len(indices) == len(contents):
                    return indices
        except Exception as e:
            logger.warning(f"LLM rerank failed: {e}")
        
        # Fallback: 返回原始顺序
        return list(range(len(contents)))

    def _parse_json(self, text: str) -> dict[str, Any]:
        """Parse JSON from LLM response."""
        import json
        import re

        # Try to extract JSON from text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # Fallback: try to parse the whole text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON: {text[:100]}...")
            return {}

    async def close(self):
        """Close the client."""
        await self._client.aclose()
