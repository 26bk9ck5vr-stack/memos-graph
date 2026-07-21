"""memos-graph Context Engine — injects state/events/promises into prompts.

Note: Minimal implementation to pass contract tests (v0.9.0-beta).
Full implementation planned for v1.5.0.
"""

from memos_graph.db.models import AgentState, Event, Promise
from memos_graph.recall import RecallEngine, RecallRequest
from datetime import datetime
from typing import Any


class ContextEngineError(Exception):
    """Base error for context engine."""
    pass


class NotImplementedByDesignError(ContextEngineError):
    """Raised when a feature is intentionally not implemented."""
    pass


class ContextInjector:
    """Injects agent state, events, promises, and memories into context.

    T1.2 / T2.1 from DESIGN.md v2.0
    Note: Minimal implementation for contract tests.
    """

    def __init__(self, db_url: str | None = None) -> None:
        self._db_url = db_url
        self._recall = RecallEngine(db_url=db_url)

    async def build_context(
        self,
        agent_id: str,
        query: str = "",
        max_events: int = 10,
        max_promises: int = 5,
        max_memories: int = 5,
        include_graph: bool = False,
    ) -> dict[str, Any]:
        """Build full context for an agent.

        Returns:
            dict with keys: agent_state, events, promises, memories, injected_at
        """
        from memos_graph.db.session import _async_session_factory
        from sqlalchemy import select
        
        async with _async_session_factory() as session:
            # Load agent state
            result = await session.execute(
                select(AgentState).where(AgentState.agent_id == agent_id)
            )
            state = result.scalar_one_or_none()
            agent_state = self._state_to_dict(state) if state else None

            # Load recent events
            events_result = await session.execute(
                select(Event)
                .where(Event.agent_id == agent_id)
                .order_by(Event.created_at.desc())
                .limit(max_events)
            )
            events = [self._event_to_dict(e) for e in events_result.scalars().all()]

            # Load open promises
            promises_result = await session.execute(
                select(Promise)
                .where(Promise.agent_id == agent_id, Promise.status == "open")
                .order_by(Promise.due_at.asc().nullslast())
                .limit(max_promises)
            )
            promises = [self._promise_to_dict(p) for p in promises_result.scalars().all()]

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
                        "stage_source": h.stage_source,
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

    async def build_system_prompt(self, context: dict[str, Any]) -> str:
        """Build system prompt from context dict."""
        return await self.format_for_prompt(context)

    async def inject(self, context: dict[str, Any], messages: list[dict]) -> list[dict]:
        """Inject context into message list.

        Alias for inject_into_messages for API compatibility.
        """
        return await self.inject_into_messages(context, messages)

    async def format_for_prompt(self, context: dict[str, Any]) -> str:
        """Format context dict as a prompt injection string."""
        lines = ["[Agent Context]"]
        if context.get("agent_state"):
            lines.append(f"State: {context['agent_state']}")
        if context.get("events"):
            lines.append(f"Recent Events: {len(context['events'])}")
        if context.get("promises"):
            lines.append(f"Open Promises: {len(context['promises'])}")
        if context.get("memories"):
            lines.append(f"Memories: {len(context['memories'])}")
        return "\n".join(lines)

    async def inject_into_messages(self, context: dict[str, Any], messages: list[dict]) -> list[dict]:
        """Inject context as a system message into a message list."""
        system_content = await self.format_for_prompt(context)
        return [{"role": "system", "content": system_content}] + messages

    @staticmethod
    def _state_to_dict(state: AgentState) -> dict[str, Any]:
        """Convert AgentState to dict matching models.py field names."""
        if not state:
            return {}
        return {
            "agent_id": state.agent_id,
            "affinity": state.affinity,
            "mood": state.mood,
            "energy": state.energy,
            "stage": state.stage,
            "metadata": state.metadata or {},
            "version": state.version,
        }

    @staticmethod
    def _event_to_dict(event: Event) -> dict[str, Any]:
        """Convert Event to dict matching models.py: summary (Text), payload (JSONB)."""
        if not event:
            return {}
        return {
            "id": event.id,
            "agent_id": event.agent_id,
            "type": event.event_type,
            "summary": event.summary or "",
            "payload": event.payload or {},
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }

    @staticmethod
    def _promise_to_dict(promise: Promise) -> dict[str, Any]:
        """Convert Promise to dict matching models.py: due_at column."""
        if not promise:
            return {}
        return {
            "id": promise.id,
            "content": promise.content,
            "status": promise.status,
            "due_at": promise.due_at.isoformat() if promise.due_at else None,
            "created_at": promise.created_at.isoformat() if promise.created_at else None,
        }


__all__ = [
    "ContextInjector",
    "ContextEngineError",
    "NotImplementedByDesignError",
]
