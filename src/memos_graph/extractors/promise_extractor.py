"""Promise Extractor — LLM-based promise detection.

Extracts promises, commitments, and future intentions from text.
Supports batch processing and async execution.

v1.0.0-beta: Basic implementation with SiliconFlow API.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from datetime import datetime

from memos_graph.llm.client import LLMClient
from memos_graph.db.session import _async_session_factory
from memos_graph.db.models import Promise, Chunk
from sqlalchemy import select

logger = logging.getLogger(__name__)


class PromiseExtractionError(Exception):
    """Error extracting promises."""
    pass


class PromiseExtractor:
    """Extracts promises from text using LLM.

    Features:
    - LLM-based promise detection
    - Batch processing
    - Async execution
    - Commitment strength scoring
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        model: str = "minimax/minimax-m2.5",
    ) -> None:
        """Initialize promise extractor.

        Args:
            llm_client: Optional LLM client
            model: LLM model to use
        """
        self._llm_client = llm_client or LLMClient(
            base_url="https://api.siliconflow.cn/v1",
            api_key="",
            model=model,
        )
        self._model = model

    async def extract_from_chunk(
        self,
        chunk_id: int,
        content: str,
        user_id: str = "default",
    ) -> Optional[dict[str, Any]]:
        """Extract promise from a single chunk.

        Args:
            chunk_id: Source chunk ID
            content: Chunk content
            user_id: User ID for the promise

        Returns:
            Extracted promise dict or None if no promise found

        Raises:
            PromiseExtractionError: If extraction fails
        """
        prompt = f"""Identify any promises, commitments, or future intentions in the following text.
If no clear promise is found, return null.

Text: {content[:500]}

Return JSON with:
- type: promise type (e.g., "task", "commitment", "intention")
- description: what was promised (max 100 chars)
- deadline: inferred deadline (if any, else null)
- strength: commitment strength 0.0-1.0
- context: relevant context (optional)

Response:"""

        try:
            response = await self._llm_client.chat(
                messages=[
                    {"role": "system", "content": "Extract promises from text. Return JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=256,
            )

            import json
            try:
                result = json.loads(response.strip())
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse LLM response as JSON: {response[:100]}")
                return None

            if not result or result.get("type") is None:
                return None

            # Create promise record
            async with _async_session_factory() as session:
                promise = Promise(
                    user_id=user_id,
                    promise_type=result.get("type", "general"),
                    description=result.get("description", content[:100]),
                    content=content,
                    status="pending",
                    metadata={
                        "chunk_id": chunk_id,
                        "deadline": result.get("deadline"),
                        "strength": result.get("strength", 0.5),
                        "context": result.get("context"),
                        "extracted_at": datetime.utcnow().isoformat(),
                    },
                )
                session.add(promise)
                await session.commit()
                await session.refresh(promise)

                logger.info(f"Extracted promise {promise.id} from chunk {chunk_id}")

                return {
                    "id": promise.id,
                    "type": promise.promise_type,
                    "description": promise.description,
                    "status": promise.status,
                    "strength": result.get("strength", 0.5),
                }

        except Exception as e:
            logger.error(f"Failed to extract promise from chunk {chunk_id}: {e}")
            raise PromiseExtractionError(f"Promise extraction failed: {e}")

    async def extract_batch(
        self,
        chunks: list[dict[str, Any]],
        user_id: str = "default",
    ) -> list[Optional[dict[str, Any]]]:
        """Extract promises from multiple chunks.

        Args:
            chunks: List of chunk dicts with 'id' and 'content'
            user_id: User ID

        Returns:
            List of extracted promises (None for chunks with no promises)
        """
        results = []
        for chunk in chunks:
            try:
                result = await self.extract_from_chunk(
                    chunk_id=chunk["id"],
                    content=chunk["content"],
                    user_id=user_id,
                )
                results.append(result)
            except PromiseExtractionError as e:
                logger.error(f"Batch extraction error for chunk {chunk['id']}: {e}")
                results.append(None)

        return results

    async def extract_from_recent_chunks(
        self,
        user_id: str = "default",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Extract promises from recent chunks.

        Args:
            user_id: User ID
            limit: Number of recent chunks to process

        Returns:
            List of extracted promises
        """
        async with _async_session_factory() as session:
            result = await session.execute(
                select(Chunk)
                .where(Chunk.user_id == user_id)
                .order_by(Chunk.created_at.desc())
                .limit(limit)
            )
            chunks = result.scalars().all()

        chunk_dicts = [
            {"id": chunk.id, "content": chunk.content}
            for chunk in chunks
        ]

        results = await self.extract_batch(chunk_dicts, user_id)
        return [r for r in results if r is not None]


async def extract_promises(
    content: str,
    chunk_id: Optional[int] = None,
    user_id: str = "default",
) -> Optional[dict[str, Any]]:
    """Convenience function to extract promises from text.

    Args:
        content: Text content
        chunk_id: Optional chunk ID
        user_id: User ID

    Returns:
        Extracted promise dict or None
    """
    extractor = PromiseExtractor()
    if chunk_id is None:
        chunk_id = 0

    return await extractor.extract_from_chunk(chunk_id, content, user_id)


__all__ = [
    "PromiseExtractor",
    "PromiseExtractionError",
    "extract_promises",
]
