"""Hermes sync worker — reads Hermes state.db and syncs messages to memos-graph."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from memos_graph.db.session import create_session_factory, _async_session_factory
from memos_graph.ingest import IngestPipeline
from memos_graph.config import load_config
from memos_graph.ingest import IngestPipeline
from typing import Any

LOG = logging.getLogger(__name__)
logger = LOG

HERMES_DB_PATH = Path.home() / ".hermes" / "state.db"
SYNC_INTERVAL_SECONDS = 60
LOOKBACK_HOURS = 24
AGENT_ID = "hermes"


def _hermes_messages_since(
    db_path: Path,
    lookback: datetime,
) -> list[dict[str, Any]]:
    """Query Hermes state.db for messages since `lookback`.

    Returns:
        List of dicts with keys: id, session_id, role, content, created_at
    """
    if not db_path.exists():
        logger.warning(f"Hermes state.db not found at {db_path}")
        return []

    rows = []
    try:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, session_id, role, content, timestamp
            FROM messages
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
            """,
            (lookback.timestamp(),),
        )

        for row in cursor.fetchall():
            rows.append({
                "id": row["id"],
                "session_id": row["session_id"],
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["timestamp"],
                "created_at": datetime.fromtimestamp(row["timestamp"], tz=timezone.utc).isoformat()
                    if row["timestamp"] else None,
            })

        conn.close()
    except Exception as e:
        logger.error(f"Failed to read Hermes state.db: {e}")

    return rows


def _group_by_session(
    messages: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Group messages by session_id."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for msg in messages:
        grouped[msg["session_id"]].append(msg)
    return grouped


async def run_sync_once() -> dict[str, Any]:
    """Perform one sync cycle.

    Returns:
        Dict with keys: messages_read, sessions_synced, errors
    """
    # Ensure session factory is initialized (worker process doesn't go through FastAPI startup)
    global _async_session_factory
    if _async_session_factory is None:
        config = load_config()
        create_session_factory(config.database.url)

    lookback = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)

    messages = _hermes_messages_since(HERMES_DB_PATH, lookback)

    if not messages:
        logger.debug("No new Hermes messages in lookback window")
        return {"messages_read": 0, "sessions_synced": 0, "errors": []}

    logger.info(f"Read {len(messages)} Hermes messages from last {LOOKBACK_HOURS}h")

    grouped = _group_by_session(messages)

    # Create shared LLM client and embedding service
    from memos_graph.llm.client import LLMClient
    from memos_graph.embedding import EmbeddingService
    
    cfg = load_config()
    llm_client = LLMClient(
        base_url=cfg.llm.base_url,
        api_key=cfg.llm.api_key,
        model=cfg.llm.model,
        timeout=cfg.llm.timeout_seconds,
    )
    embedding_service = EmbeddingService(
        provider=cfg.embedding.provider,
        model=cfg.embedding.model,
        base_url=cfg.embedding.base_url,
        api_key=cfg.embedding.api_key,
        timeout=float(cfg.embedding.timeout_seconds),
    )
    
    # Create pipeline with shared services
    pipeline = IngestPipeline(
        embedding_service=embedding_service,
        llm_client=llm_client,
    )
    synced_sessions = 0
    errors = []

    # Create external session and reuse for all ingests
    from memos_graph.db.session import _async_session_factory
    async with _async_session_factory() as session:
        for session_id, session_messages in grouped.items():
            try:
                # Concatenate messages into a single text block per session
                lines = []
                for msg in session_messages:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    created = msg.get("created_at", "")
                    lines.append(f"[{created}] {role}: {content}")

                text = "\n".join(lines)

                result = await pipeline.ingest(
                    text=text,
                    agent_id=AGENT_ID,
                    session=session,  # Pass external session
                    scope="private",
                    extract_entities=True,
                    extract_events=True,
                    extract_promises=True,
                    merge_profile=False,
                )

                logger.info(
                    f"Synced session {session_id}: "
                    f"chunk_id={result.get('chunk_id')}, "
                    f"entities={result.get('entity_count')}, "
                    f"events={result.get('event_count')}, "
                    f"promises={result.get('promise_count')}"
                )
                synced_sessions += 1

            except Exception as e:
                logger.error(f"Failed to sync session {session_id}: {e}")
                errors.append({"session_id": session_id, "error": str(e)})

    return {
        "messages_read": len(messages),
        "sessions_synced": synced_sessions,
        "errors": errors,
    }


class HermesSyncWorker:
    """Background worker that periodically syncs Hermes messages to memos-graph.

    Runs every SYNC_INTERVAL_SECONDS (default 60s), reading messages from the
    last LOOKBACK_HOURS (default 24h) and ingesting them via IngestPipeline.
    """

    def __init__(
        self,
        interval_seconds: int = SYNC_INTERVAL_SECONDS,
        lookback_hours: int = LOOKBACK_HOURS,
    ) -> None:
        self._interval = interval_seconds
        self._lookback = lookback_hours
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the background sync loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(
            f"HermesSyncWorker started "
            f"(interval={self._interval}s, lookback={self._lookback}h)"
        )

    async def stop(self) -> None:
        """Stop the background sync loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("HermesSyncWorker stopped")

    async def _loop(self) -> None:
        """Main loop — run sync, sleep, repeat."""
        while self._running:
            try:
                # Run one sync cycle (non-blocking for the loop)
                result = await run_sync_once()
                if result.get("messages_read", 0) > 0:
                    logger.info(
                        f"Hermes sync cycle: "
                        f"read={result['messages_read']}, "
                        f"synced={result['sessions_synced']}, "
                        f"errors={len(result['errors'])}"
                    )
            except Exception as e:
                logger.error(f"Hermes sync cycle error: {e}")

            try:
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break
