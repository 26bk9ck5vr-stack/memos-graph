"""memos-graph Ingest Pipeline — extracts entities, events, promises from raw text.

Uses the built-in LLMClient extraction methods (T3.1 / W9).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from memos_graph.db.models import Chunk, ChunkEntity, ChunkVector, Entity, Event, EventVector, Promise, UserProfile
from memos_graph.llm.client import LLMClient
from memos_graph.recall import EmbeddingService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def make_llm_client() -> LLMClient:
    from memos_graph.config import load_config
    cfg = load_config()
    return LLMClient(base_url=cfg.llm.base_url, api_key=cfg.llm.api_key, model=cfg.llm.model)


class EntityExtractor:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or make_llm_client()

    async def extract(self, text: str) -> list[dict[str, Any]]:
        try:
            data = await self._llm.extract_entities(text[:3000])
            entities = data.get("entities", [])
            seen = set()
            deduped = []
            for e in entities:
                if e.get("name") and e["name"] not in seen:
                    seen.add(e["name"])
                    deduped.append(e)
            return deduped
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            return []


class EventExtractor:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or make_llm_client()

    async def extract(self, text: str) -> list[dict[str, Any]]:
        try:
            data = await self._llm.summarize_event(text[:3000])
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return [data] if data else []
            return []
        except Exception as e:
            logger.warning(f"Event extraction failed: {e}")
            return []

    async def upsert(
        self,
        session: AsyncSession,
        text: str,
        agent_id: str,
        metadata: dict | None = None,
        embedding_service: EmbeddingService | None = None,
        related_chunk_id: int | None = None,
    ) -> list[int]:
        """Extract events, upsert to DB, generate and store vectors."""
        extracted = await self.extract(text)
        if not extracted:
            return []

        event_ids = []
        for e in extracted:
            summary = e.get("summary") or e.get("content") or str(e)[:500]
            event = Event(
                agent_id=agent_id,
                event_type=e.get("event_type", "other"),
                actor=e.get("actor", "agent"),
                related_chunk_id=related_chunk_id,
                payload={"raw": e, "source_metadata": metadata or {}},
                summary=summary,
            )
            session.add(event)
            await session.flush()
            event_ids.append(event.id)

            # Generate and store event vector
            if embedding_service:
                try:
                    vecs = await embedding_service.embed([summary])
                    if vecs:
                        ev = EventVector(
                            event_id=event.id,
                            embedding=vecs[0],
                            model=embedding_service.model,
                        )
                        session.add(ev)
                except Exception as ve:
                    logger.warning(f"Event vector generation failed: {ve}")

        return event_ids


class PromiseExtractor:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or make_llm_client()

    async def extract(self, text: str) -> list[dict[str, Any]]:
        try:
            data = await self._llm.extract_promise(text[:3000])
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                promises = data.get("promises", [])
                return promises if isinstance(promises, list) else [data]
            return []
        except Exception as e:
            logger.warning(f"Promise extraction failed: {e}")
            return []

    async def upsert(self, session: AsyncSession, text: str, agent_id: str) -> list[int]:
        extracted = await self.extract(text)
        if not extracted:
            return []

        promise_ids = []
        for p in extracted:
            due_at = None
            if p.get("deadline"):
                try:
                    due_at = datetime.fromisoformat(p["deadline"].replace("Z", "+00:00"))
                except ValueError:
                    pass

            promise = Promise(
                agent_id=agent_id,
                content=p.get("content", "")[:500],
                status=p.get("status", "open"),
                due_at=due_at,
            )
            session.add(promise)
            await session.flush()
            promise_ids.append(promise.id)
        return promise_ids


class ProfileMerger:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm = llm_client or make_llm_client()

    async def merge(self, session: AsyncSession, agent_id: str, new_info: str, user_id: str | None = None) -> dict[str, Any]:
        query = (
            select(UserProfile).where(UserProfile.user_id == user_id)
            if user_id
            else select(UserProfile).where(UserProfile.agent_id == agent_id)
        )
        result = await session.execute(query)
        profile = result.scalar_one_or_none()

        current_attrs = dict(profile.attributes) if profile and profile.attributes else {}

        try:
            data = await self._llm.merge_profiles([current_attrs, {"new": new_info[:1000]}])
            updated_attrs = data if isinstance(data, dict) else {}
        except Exception as e:
            logger.warning(f"Profile merge failed: {e}")
            updated_attrs = {}

        merged_attrs = dict(current_attrs)
        merged_attrs.update(updated_attrs)

        if profile:
            profile.attributes = merged_attrs
            profile.updated_by = f"agent:{agent_id}"
            profile.updated_at = datetime.utcnow()
        else:
            profile = UserProfile(
                agent_id=agent_id,
                user_id=user_id,
                display_name=updated_attrs.get("display_name"),
                attributes=merged_attrs,
                updated_by=f"agent:{agent_id}",
            )
            session.add(profile)

        await session.refresh(profile)
        return {"agent_id": profile.agent_id, "display_name": profile.display_name, "attributes": profile.attributes or {}}


class IngestPipeline:
    """Main ingest pipeline.

    Flow: text → Chunk → EntityExtractor → ChunkEntity associations
                            → EventExtractor + EventVector
                            → PromiseExtractor
                            → ProfileMerger
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        llm_client: LLMClient | None = None,
        config_path: str | None = None,
    ) -> None:
        from memos_graph.config import load_config
        
        # Use injected LLM client or create lazy-loaded one
        if llm_client is not None:
            self._entity = EntityExtractor(llm_client=llm_client)
            self._event = EventExtractor(llm_client=llm_client)
            self._promise = PromiseExtractor(llm_client=llm_client)
            self._profile = ProfileMerger(llm_client=llm_client)
        else:
            self._entity = EntityExtractor()
            self._event = EventExtractor()
            self._promise = PromiseExtractor()
            self._profile = ProfileMerger()
        
        if embedding_service is not None:
            self._embedding = embedding_service
        else:
            # Load config and create EmbeddingService with proper settings
            cfg = load_config(Path(config_path) if config_path else None)
            self._embedding = EmbeddingService(
                provider=cfg.embedding.provider,
                model=cfg.embedding.model,
                base_url=cfg.embedding.base_url,
                api_key=cfg.embedding.api_key,
                timeout=float(cfg.embedding.timeout_seconds),
            )

    async def ingest(
        self,
        text: str,
        agent_id: str,
        session: AsyncSession | None = None,  # NEW: optional external session
        user_id: str | None = None,
        scope: str = "private",
        extract_entities: bool = True,
        extract_events: bool = True,
        extract_promises: bool = True,
        merge_profile: bool = False,
    ) -> dict[str, Any]:
        """Run full ingest pipeline.

        Args:
            text: Input text to ingest
            agent_id: Agent identifier
            session: Optional external session (if None, creates own session)
            user_id: Optional user identifier
            scope: Chunk scope (default: "private")
            extract_entities: Whether to extract entities (default: True)
            extract_events: Whether to extract events (default: True)
            extract_promises: Whether to extract promises (default: True)
            merge_profile: Whether to merge user profile (default: False)

        Returns:
            Dict with chunk_id, entity_count, event_count, promise_count, profile
        """
        results: dict[str, Any] = {
            "chunk_id": None,
            "entity_count": 0,
            "event_count": 0,
            "promise_count": 0,
            "profile": None,
        }

        # Determine whether to use external session or create own
        own_session = session is None
        
        if own_session:
            from memos_graph.db.session import _async_session_factory
            async with _async_session_factory() as session:
                await self._ingest_with_session(session, text, agent_id, user_id, scope, extract_entities, extract_events, extract_promises, merge_profile, results)
        else:
            await self._ingest_with_session(session, text, agent_id, user_id, scope, extract_entities, extract_events, extract_promises, merge_profile, results)
        
        return results
    
    async def _ingest_with_session(
        self,
        session: AsyncSession,
        text: str,
        agent_id: str,
        user_id: str | None,
        scope: str,
        extract_entities: bool,
        extract_events: bool,
        extract_promises: bool,
        merge_profile: bool,
        results: dict[str, Any],
    ) -> None:
        """Internal ingest logic using provided session."""
        # 1. Create Chunk
        chunk = Chunk(
            agent_id=agent_id,
            scope=scope,
            content=text,
            metadata_={"source": "ingest", "user_id": user_id},
        )
        session.add(chunk)
        await session.flush()
        chunk_id: int = int(chunk.id)
        results["chunk_id"] = chunk_id

        # 2. Extract and link entities
        if extract_entities:
            extracted = await self._entity.extract(text)
            for e in extracted:
                name = e.get("name", "")
                if not name:
                    continue

                result = await session.execute(
                    select(Entity).where(Entity.name == name, Entity.agent_id == agent_id)
                )
                existing = result.scalar_one_or_none()
                if existing:
                    entity_id = existing.id
                else:
                    entity = Entity(name=name, type=e.get("type", "other"), agent_id=agent_id)
                    session.add(entity)
                    await session.flush()
                    entity_id = entity.id

                assoc = ChunkEntity(chunk_id=chunk_id, entity_id=entity_id, confidence=e.get("confidence", 1.0))
                session.add(assoc)
                results["entity_count"] += 1

        # 3. Generate and store chunk vector
        try:
            vec = await self._embedding.embed(text)  # Returns list[float]
            if vec:
                cv = ChunkVector(chunk_id=chunk_id, embedding=vec, model=self._embedding._model)
                session.add(cv)
        except Exception as ve:
            logger.warning(f"Chunk vector generation failed: {ve}")

        await session.commit()

        # 4. Extract events with vector generation
        if extract_events:
            ids = await self._event.upsert(session, text, agent_id, embedding_service=self._embedding, related_chunk_id=chunk_id)
            results["event_count"] = len(ids)

        # 5. Extract promises
        if extract_promises:
            ids = await self._promise.upsert(session, text, agent_id)
            results["promise_count"] = len(ids)

        # 6. Merge profile
        if merge_profile:
            results["profile"] = await self._profile.merge(session, agent_id, text, user_id)

        return results


__all__ = [
    "IngestPipeline",
    "EntityExtractor",
    "EventExtractor",
    "PromiseExtractor",
    "ProfileMerger",
    "make_llm_client",
]
