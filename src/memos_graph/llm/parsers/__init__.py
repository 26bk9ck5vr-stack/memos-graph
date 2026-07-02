"""LLM parsers for parsing LLM output."""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def parse_entities(text: str) -> list[dict[str, Any]]:
    """Parse entity extraction output."""
    try:
        data = json.loads(text)
        return data.get("entities", [])
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse entities: {text[:100]}")
        return []


def parse_relations(text: str) -> list[dict[str, Any]]:
    """Parse relation extraction output."""
    try:
        data = json.loads(text)
        return data.get("relations", [])
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse relations: {text[:100]}")
        return []


def parse_promise(text: str) -> dict[str, Any] | None:
    """Parse promise extraction output."""
    try:
        data = json.loads(text)
        if data.get("has_promise") and data.get("promises"):
            return data["promises"][0]
        return None
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse promise: {text[:100]}")
        return None


def parse_event_summary(text: str) -> dict[str, Any]:
    """Parse event summarization output."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse event summary: {text[:100]}")
        return {
            "event_type": "message",
            "summary": text[:200],
            "actor": "user",
            "payload": {},
        }


def parse_heartbeat(text: str) -> str:
    """Parse heartbeat generation output (just return the text)."""
    return text.strip()


def parse_merged_profile(text: str) -> dict[str, Any]:
    """Parse profile merge output."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse merged profile: {text[:100]}")
        return {"attributes": {}}
