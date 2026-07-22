"""Event Extractor — LLM-based event summarization.

Extracts structured events from raw text using LLM.
Supports batch processing and async execution.

v1.0.0-beta: Basic implementation with SiliconFlow API.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from datetime import datetime

from memos_graph.llm.client import LLMClient
from memos_graph.db.session import _async_session_factory
from memos_graph.db.models import Event, Chunk
from sqlalchemy import select

logger = logging.getLogger(__name__)


class EventExtractionError(Exception):
    """Error extracting events."""
    pass


class EventExtractor:
    """Extracts events from text using LLM.

    Features:
    - LLM-based event extraction
    - Batch processing
    - Async execution
    - Configurable extraction rules
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        model: str = "minimax/minimax-m2.5",
    ) -> None:
        """Initialize event extractor.

        Args:
            llm_client: Optional LLM client (creates default if None)
            model: LLM model to use
        """
        self._llm_client = llm_client or LLMClient(
            base_url="https://api.siliconflow.cn/v1",
            api_key="",  # Will use env var or config
            model=model,
        )
        self._model = model

    async def extract_from_chunk(
        self,
        chunk_id: int,
        content: str,
        user_id: str = "default",
    ) -> Optional[dict[str, Any]]:
        """Extract event from a single chunk.

        Args:
            chunk_id: Source chunk ID
            content: Chunk content
            user_id: User ID for the event

        Returns:
            Extracted event dict or None if no event found

        Raises:
            EventExtractionError: If extraction fails
        """
        prompt = f"""Extract any events, activities, or actions from the following text.
If no clear event is found, return null.

Text: {content[:500]}

Return JSON with:
- type: event type (e.g., "meeting", "task", "conversation")
- summary: brief summary (max 50 chars)
- participants: list of people involved (if any)
- timestamp: inferred time (if any, else null)
- confidence: 0.0-1.0

Response:"""

        try:
            response = await self._llm_client.chat(
                messages=[
                    {"role": "system", "content": "Extract events from text. Return JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
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

            # Create event record
            async with _async_session_factory() as session:
                event = Event(
                    user_id=user_id,
                    event_type=result.get("type", "general"),
                    summary=result.get("summary", content[:100]),
                    content=content,
                    metadata={
                        "chunk_id": chunk_id,
                        "participants": result.get("participants", []),
                        "confidence": result.get("confidence", 0.5),
                        "extracted_at": datetime.utcnow().isoformat(),
                    },
                )
                session.add(event)
                await session.commit()
                await session.refresh(event)

                logger.info(f"Extracted event {event.id} from chunk {chunk_id}")

                return {
                    "id": event.id,
                    "type": event.event_type,
                    "summary": event.summary,
                    "participants": result.get("participants", []),
                    "confidence": result.get("confidence", 0.5),
                }

        except Exception as e:
            logger.error(f"Failed to extract event from chunk {chunk_id}: {e}")
            raise EventExtractionError(f"Event extraction failed: {e}")

    async def extract_batch(
        self,
        chunks: list[dict[str, Any]],
        user_id: str = "default",
    ) -> list[Optional[dict[str, Any]]]:
        """Extract events from multiple chunks.

        Args:
            chunks: List of chunk dicts with 'id' and 'content'
            user_id: User ID

        Returns:
            List of extracted events (None for chunks with no events)
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
            except EventExtractionError as e:
                logger.error(f"Batch extraction error for chunk {chunk['id']}: {e}")
                results.append(None)

        return results

    async def extract_from_recent_chunks(
        self,
        user_id: str = "default",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Extract events from recent chunks.

        Args:
            user_id: User ID
            limit: Number of recent chunks to process

        Returns:
            List of extracted events
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


async def extract_events(
    content: str,
    chunk_id: Optional[int] = None,
    user_id: str = "default",
) -> Optional[dict[str, Any]]:
    """Convenience function to extract events from text.

    Args:
        content: Text content
        chunk_id: Optional chunk ID
        user_id: User ID

    Returns:
        Extracted event dict or None
    """
    extractor = EventExtractor()
    if chunk_id is None:
        chunk_id = 0  # Dummy ID for standalone extraction

    return await extractor.extract_from_chunk(chunk_id, content, user_id)


__all__ = [
    "EventExtractor",
    "EventExtractionError",
    "extract_events",
]
