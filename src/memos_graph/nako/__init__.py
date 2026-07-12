"""memos-graph Nako migration tool — migrate data from Memos to memos-graph.

Nako (ナ行) = "to migrate/enter" in Japanese — the import pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from memos_graph.db.session import get_session
from memos_graph.db.models import Chunk, Entity, Event
from memos_graph.config import load_config
from sqlalchemy import select, func

logger = logging.getLogger(__name__)


# === Memos API Client ===

class MemosClient:
    """Client for Memos Open API (https://www.memos.org/)."""

    def __init__(self, host: str, api_key: str) -> None:
        self.host = host.rstrip("/")
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=self.host,
            timeout=30.0,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_memos(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """Fetch memos from Memos Open API."""
        try:
            resp = await self._client.get(
                "/api/v1/memo",
                params={"limit": limit, "offset": offset},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", []) if isinstance(data, dict) else data
        except Exception as e:
            logger.error(f"Failed to fetch memos: {e}")
            return []

    async def get_memo_by_id(self, memo_id: str) -> dict[str, Any] | None:
        """Fetch single memo."""
        try:
            resp = await self._client.get(f"/api/v1/memo/{memo_id}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to fetch memo {memo_id}: {e}")
            return None


# === Markdown Parser ===

class MarkdownParser:
    """Parse Memos markdown content into structured data."""

    # Regex patterns for common structures
    TAG_PATTERN = re.compile(r"#(\w+)")
    LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    CODE_BLOCK_PATTERN = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
    INLINE_CODE_PATTERN = re.compile(r"`([^`]+)`")
    DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
    NUMBER_PATTERN = re.compile(r"^\d+\.\s+(.+)$", re.MULTILINE)

    def parse(self, content: str) -> dict[str, Any]:
        """Parse markdown content into structured data."""
        tags = self.TAG_PATTERN.findall(content)
        links = self.LINK_PATTERN.findall(content)
        code_blocks = self.CODE_BLOCK_PATTERN.findall(content)
        inline_codes = self.INLINE_CODE_PATTERN.findall(content)

        # Detect list items
        list_items = self.NUMBER_PATTERN.findall(content)

        # Extract dates mentioned in content
        dates = self.DATE_PATTERN.findall(content)

        # Strip tags and links for clean content
        clean_content = self.TAG_PATTERN.sub("", content)
        clean_content = self.LINK_PATTERN.sub(r"\1", clean_content)

        return {
            "tags": list(set(tags)),
            "links": [{"text": t, "url": u} for t, u in links],
            "code_blocks": [{"lang": lang, "code": code} for lang, code in code_blocks],
            "inline_codes": inline_codes,
            "list_items": list_items,
            "mentioned_dates": list(set(dates)),
            "content": clean_content.strip(),
            "has_code": len(code_blocks) > 0,
            "has_links": len(links) > 0,
        }


# === Entity Extractor ===

class NakoEntityExtractor:
    """Extract entities from migrated content."""

    KNOWN_TYPES = {
        "person": re.compile(r"@(\w+)"),
        "url": re.compile(r"https?://[^\s]+"),
        "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
        "date": re.compile(r"\d{4}-\d{2}-\d{2}"),
    }

    def extract(self, content: str) -> list[dict[str, str]]:
        entities = []
        for etype, pattern in self.KNOWN_TYPES.items():
            for match in pattern.finditer(content):
                name = match.group(0)[:100]
                if name not in [e["name"] for e in entities]:
                    entities.append({"name": name, "type": etype})
        return entities


# === Main Migration Pipeline ===

class NakoMigrationPipeline:
    """Main migration pipeline from Memos to memos-graph (T8 from DESIGN.md)."""

    def __init__(
        self,
        memos_host: str = "https://demo.memos.run",
        memos_api_key: str = "",
    ) -> None:
        self._memos = MemosClient(memos_host, memos_api_key)
        self._parser = MarkdownParser()
        self._entity_extractor = NakoEntityExtractor()
        self._stats = {
            "memos_fetched": 0,
            "chunks_created": 0,
            "entities_created": 0,
            "events_created": 0,
            "errors": 0,
        }

    async def close(self) -> None:
        await self._memos.close()

    async def run(
        self,
        agent_id: str,
        limit: int = 100,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Run full migration.

        Args:
            agent_id: Target agent ID in memos-graph
            limit: Max memos to migrate
            dry_run: If True, fetch but don't write to DB

        Returns:
            Migration statistics
        """
        logger.info(f"Starting Nako migration for agent={agent_id}, limit={limit}")

        memos = await self._memos.get_memos(limit=limit)
        self._stats["memos_fetched"] = len(memos)

        if not memos:
            logger.warning("No memos fetched from Memos API")
            return self._stats

        for memo in memos:
            try:
                await self._migrate_memo(memo, agent_id, dry_run)
            except Exception as e:
                logger.error(f"Failed to migrate memo: {e}")
                self._stats["errors"] += 1

        logger.info(f"Migration complete: {self._stats}")
        return self._stats

    async def _migrate_memo(
        self,
        memo: dict[str, Any],
        agent_id: str,
        dry_run: bool,
    ) -> None:
        """Migrate a single memo."""
        # Extract content
        content = memo.get("content", "") or memo.get("text", "") or ""
        if not content:
            return

        # Parse content
        parsed = self._parser.parse(content)

        # Build metadata
        metadata = {
            "memos_id": str(memo.get("id", "")),
            "creator": memo.get("creator", ""),
            "tags": parsed["tags"],
            "visibility": memo.get("visibility", "PRIVATE"),
            "parsed": {
                "has_code": parsed["has_code"],
                "has_links": parsed["has_links"],
                "link_count": len(parsed["links"]),
                "code_lang": [b["lang"] for b in parsed["code_blocks"] if b["lang"]],
            },
            "urls": [
                {"text": t, "url": u} for t, u in parsed["links"]
            ],
        }

        # Create chunk
        if not dry_run:
            async with get_session() as session:
                chunk = Chunk(
                    agent_id=agent_id,
                    scope="private",
                    content=parsed["content"],
                    metadata_=metadata,
                )
                session.add(chunk)
                await session.flush()
                chunk_id = chunk.id

                # Extract and create entities
                entities = self._entity_extractor.extract(content)
                for ent in entities:
                    entity = Entity(
                        name=ent["name"],
                        type=ent["type"],
                        agent_id=agent_id,
                        metadata_={"source": "nako_migration", "memo_id": metadata["memos_id"]},
                    )
                    session.add(entity)
                    await session.flush()
                    self._stats["entities_created"] += 1

                # Create migration event
                event = Event(
                    agent_id=agent_id,
                    event_type="migration",
                    actor="system",
                    payload={
                        "memo_id": metadata["memos_id"],
                        "tags": parsed["tags"],
                        "content_preview": content[:200],
                    },
                    summary=f"Migrated from Memos: {', '.join(parsed['tags'][:3]) or 'untagged'}",
                    related_chunk_id=chunk_id,
                )
                session.add(event)
                await session.commit()

                self._stats["chunks_created"] += 1
                self._stats["events_created"] += 1
        else:
            logger.info(f"[DRY RUN] Would migrate: {content[:100]}...")

    def get_stats(self) -> dict[str, Any]:
        return self._stats.copy()


# === CLI Commands ===

async def migrate_cmd(
    host: str,
    api_key: str,
    agent_id: str,
    limit: int = 100,
    dry_run: bool = False,
) -> dict[str, Any]:
    """CLI entry point for migration."""
    pipeline = NakoMigrationPipeline(memos_host=host, memos_api_key=api_key)
    try:
        stats = await pipeline.run(agent_id=agent_id, limit=limit, dry_run=dry_run)
        return stats
    finally:
        await pipeline.close()


# === JSONL Import ===

class JSONLImporter:
    """Import memories from JSONL file (one JSON object per line)."""

    @staticmethod
    async def import_file(
        file_path: str,
        agent_id: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Import from JSONL file.

        Expected format per line:
        {"content": "...", "tags": [...], "metadata": {...}}

        or simply:
        {"content": "..."}
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        stats = {"lines_processed": 0, "chunks_created": 0, "errors": 0}

        async with get_session() as session:
            with open(path) as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        obj = json.loads(line)
                        content = obj.get("content", "")
                        if not content:
                            continue

                        if not dry_run:
                            chunk = Chunk(
                                agent_id=agent_id,
                                scope=obj.get("scope", "private"),
                                content=content,
                                metadata_={
                                    "imported_from": str(path),
                                    "line": line_num,
                                    "tags": obj.get("tags", []),
                                    **obj.get("metadata", {}),
                                },
                            )
                            session.add(chunk)
                            stats["chunks_created"] += 1

                        stats["lines_processed"] += 1
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON parse error at line {line_num}: {e}")
                        stats["errors"] += 1

            if not dry_run:
                await session.commit()

        return stats


__all__ = [
    "NakoMigrationPipeline",
    "MemosClient",
    "MarkdownParser",
    "JSONLImporter",
    "migrate_cmd",
]
