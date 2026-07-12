"""memos-graph Context Engine — injects state/events/promises into prompts."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from memos_graph.db.session import get_session
from memos_graph.db.models import AgentState, Event, Promise
from memos_graph.recall import RecallEngine, RecallRequest
from sqlalchemy import select

logger = logging.getLogger(__name__)


class ContextInjector:
    """Injects agent state, events, promises, and memories into context.

    T1.2 / T2.1 from DESIGN.md v2.0
    """

    def __init__(self, db_url: str | None = None) -> None:
        self._db_url = db_url
        self._recall = RecallEngine(db_url=db_url)

    async def build_context(
        self,
        agent_id: str,
        query: str | None = None,
        max_events: int = 10,
        max_promises: int = 5,
        max_memories: int = 5,
        include_graph: bool = True,
    ) -> dict[str, Any]:
        """Build full context for an agent.

        Returns:
            dict with keys: agent_state, events, promises, memories, injected_at
        """
        async with get_session() as session:
            # Load agent state
            result = await session.execute(
                select(AgentState).where(AgentState.agent_id == agent_id)
            )
            state = result.scalar_one_or_none()
            agent_state = _state_to_dict(state) if state else None

            # Load recent events
            events_result = await session.execute(
                select(Event)
                .where(Event.agent_id == agent_id)
                .order_by(Event.created_at.desc())
                .limit(max_events)
            )
            events = [_event_to_dict(e) for e in events_result.scalars().all()]

            # Load open promises
            promises_result = await session.execute(
                select(Promise)
                .where(Promise.agent_id == agent_id, Promise.status == "open")
                .order_by(Promise.deadline.asc().nullslast())
                .limit(max_promises)
            )
            promises = [_promise_to_dict(p) for p in promises_result.scalars().all()]

            # Recall relevant memories
            memories = []
            if query:
                req = RecallRequest(
                    query=query,
                    agent_id=agent_id,
                    max_results=max_memories,
                    use_graph=include_graph,
                )
                recall_result = await self._recall.search(req)
                memories = [
                    {
                        "chunk_id": h.chunk_id,
                        "content": h.content[:200],
                        "score": h.score,
                        "stage": h.stage_source,
                    }
                    for h in recall_result.hits
                ]

            return {
                "agent_id": agent_id,
                "agent_state": agent_state,
                "events": events,
                "promises": promises,
                "memories": memories,
                "injected_at": datetime.utcnow().isoformat(),
            }

    async def format_for_prompt(self, context: dict[str, Any]) -> str:
        """Format context dict as a prompt injection string."""
        lines = ["[Agent Context]"]

        if context.get("agent_state"):
            lines.append("\n## Agent State")
            state = context["agent_state"]
            lines.append(f"- stage: {state.get('stage', 1)}")
            lines.append(f"- affinity: {state.get('affinity', 0)}")
            lines.append(f"- mood: {state.get('mood', 50)}")
            lines.append(f"- energy: {state.get('energy', 50)}")
            lines.append(f"- pending_heartbeat: {state.get('pending_heartbeat', False)}")
            if state.get("last_interaction"):
                lines.append(f"- last_interaction: {state['last_interaction']}")

        if context.get("events"):
            lines.append("\n## Recent Events")
            for evt in context["events"][:5]:
                lines.append(f"- [{evt['type']}] {evt.get('summary', '')[:100]}")

        if context.get("promises"):
            lines.append("\n## Open Promises")
            for p in context["promises"]:
                deadline = p.get("due_at", "no deadline")
                lines.append(f"- [{p['status']}] {p.get('content', '')} (due: {deadline})")

        if context.get("memories"):
            lines.append("\n## Relevant Memories")
            for mem in context["memories"]:
                lines.append(f"- [{mem['stage']}] {mem['content'][:80]}...")

        return "\n".join(lines)

    async def inject_into_messages(
        self,
        agent_id: str,
        messages: list[dict[str, str]],
        query: str | None = None,
    ) -> list[dict[str, str]]:
        """Inject context as a system message into a message list."""
        context = await self.build_context(agent_id, query=query)
        context_str = await self.format_for_prompt(context)

        system_msg = {"role": "system", "content": context_str}

        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = messages[0]["content"] + "\n\n" + context_str
        else:
            messages.insert(0, system_msg)

        return messages


def _state_to_dict(state: AgentState) -> dict[str, Any]:
    """Convert AgentState to dict matching models.py field names."""
    return {
        "agent_id": state.agent_id,
        "pack_id": state.pack_id,
        "stage": state.stage,
        "affinity": state.affinity,
        "mood": state.mood,
        "energy": state.energy,
        "pending_heartbeat": state.pending_heartbeat,
        "last_interaction": state.last_interaction.isoformat() if state.last_interaction else None,
        "last_heartbeat": state.last_heartbeat.isoformat() if state.last_heartbeat else None,
        "version": state.version,
    }


def _event_to_dict(event: Event) -> dict[str, Any]:
    """Convert Event to dict matching models.py: summary (Text), payload (JSONB)."""
    return {
        "id": event.id,
        "type": event.event_type,
        "actor": event.actor,
        "summary": event.summary or "",
        "payload": event.payload or {},
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def _promise_to_dict(promise: Promise) -> dict[str, Any]:
    """Convert Promise to dict matching models.py: due_at column."""
    return {
        "id": promise.id,
        "content": promise.content,
        "status": promise.status,
        "due_at": promise.due_at.isoformat() if promise.due_at else None,
        "created_at": promise.created_at.isoformat() if promise.created_at else None,
    }


__all__ = [
    "ContextInjector",
]
