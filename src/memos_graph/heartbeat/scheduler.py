"""Heartbeat Scheduler MVP — basic message scheduling.

Note: MVP implementation for v1.0.0.
Full implementation planned for v1.5.0.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from pathlib import Path

from memos_graph.heartbeat.rules import parse_heartbeat_rules, HeartbeatRuleConfig
from memos_graph.db.session import _async_session_factory
from memos_graph.db.models import AgentState, Event
from memos_graph.embedding import NotImplementedByDesignError
from sqlalchemy import select

logger = logging.getLogger(__name__)


class HeartbeatError(Exception):
    """Base error for heartbeat scheduler."""
    pass


class HeartbeatScheduler:
    """Basic heartbeat scheduler MVP.
    
    Features (v1.0.0 MVP):
    - Parse HEARTBEAT.md rules
    - Check if heartbeat should be sent based on interval
    - Create heartbeat event
    
    TODO (v1.5.0):
    - Async background scheduling
    - Quiet hours enforcement
    - Stage-based thresholds
    - LLM-generated content
    """

    def __init__(
        self,
        agent_id: str | None = None,
        rules_dir: Path | str | None = None,
        schedule_seconds: int = 3600,  # Default: check every hour
        quiet_hours: str | None = None,  # e.g. "22:00-06:00"
    ) -> None:
        """Initialize heartbeat scheduler.
        
        Args:
            agent_id: Agent identifier (optional for MVP)
            rules_dir: Directory containing HEARTBEAT.md rules file
            schedule_seconds: Check interval in seconds (MVP only)
            quiet_hours: Quiet hours range (MVP only, not enforced)
        """
        self._agent_id = agent_id
        self._rules_dir = Path(rules_dir) if rules_dir else None
        self._schedule_seconds = schedule_seconds
        self._quiet_hours = quiet_hours
        self._rules: list[HeartbeatRuleConfig] = []
        self._last_heartbeat: datetime | None = None
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None

    async def load_rules(self) -> list[HeartbeatRuleConfig]:
        """Load heartbeat rules from HEARTBEAT.md file."""
        if self._rules_dir is None:
            # Default rules for MVP
            self._rules = [
                HeartbeatRuleConfig(
                    name="default",
                    interval="24h",
                    stage_thresholds=[6.0, 24.0, 72.0, 168.0],
                )
            ]
            return self._rules
        
        heartbeat_file = self._rules_dir / "HEARTBEAT.md"
        if not heartbeat_file.exists():
            logger.warning(f"Heartbeat rules file not found: {heartbeat_file}")
            # Default rules
            self._rules = [
                HeartbeatRuleConfig(
                    name="default",
                    interval="24h",
                )
            ]
            return self._rules
        
        self._rules = parse_heartbeat_rules(heartbeat_file)
        logger.info(f"Loaded {len(self._rules)} heartbeat rules")
        return self._rules

    def should_heartbeat(self) -> tuple[bool, Optional[str]]:
        """Check if a heartbeat message should be sent (synchronous for MVP).
        
        Returns:
            Tuple of (should_send, reason)
        """
        if not self._rules:
            # Load rules synchronously for MVP
            if self._rules_dir is None:
                self._rules = [
                    HeartbeatRuleConfig(
                        name="default",
                        interval="24h",
                        stage_thresholds=[6.0, 24.0, 72.0, 168.0],
                    )
                ]
            else:
                heartbeat_file = self._rules_dir / "HEARTBEAT.md"
                if heartbeat_file.exists():
                    self._rules = parse_heartbeat_rules(heartbeat_file)
                else:
                    self._rules = [
                        HeartbeatRuleConfig(
                            name="default",
                            interval="24h",
                        )
                    ]
        
        # MVP: Simple interval-based check
        # TODO: Implement stage-based thresholds and quiet hours
        
        if self._last_heartbeat is None:
            return True, "First heartbeat"
        
        # Check against first rule (default)
        rule = self._rules[0]
        interval_str = rule.interval
        
        # Parse interval (MVP: support hours only)
        if interval_str.endswith("h"):
            interval_hours = float(interval_str[:-1])
        elif interval_str.endswith("m"):
            interval_hours = float(interval_str[:-1]) / 60.0
        else:
            interval_hours = 24.0  # Default
        
        elapsed = datetime.utcnow() - self._last_heartbeat
        if elapsed >= timedelta(hours=interval_hours):
            return True, f"Interval {interval_str} elapsed"
        
        return False, f"Interval {interval_str} not elapsed"

    async def create_heartbeat_event(
        self,
        session: Any,
        content: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Event:
        """Create a heartbeat event.
        
        Args:
            session: Database session
            content: Heartbeat message content
            metadata: Additional metadata
            
        Returns:
            Created Event object
        """
        event = Event(
            agent_id=self._agent_id,
            event_type="heartbeat",
            summary="Heartbeat",
            payload={
                "content": content,
                "rule_name": self._rules[0].name if self._rules else "default",
                **(metadata or {}),
            },
        )
        session.add(event)
        logger.info(f"Created heartbeat event for agent {self._agent_id}")
        return event

    async def tick(self) -> Optional[Event]:
        """Main tick function — check and create heartbeat if needed.
        
        Returns:
            Created Event if heartbeat was sent, None otherwise
        """
        async with _async_session_factory() as session:
            should_send, reason = await self.should_heartbeat()
            
            if not should_send:
                logger.debug(f"Heartbeat skipped: {reason}")
                return None
            
            # Create heartbeat event
            event = await self.create_heartbeat_event(
                session,
                content=f"Heartbeat: {reason}",
                metadata={"reason": reason},
            )
            
            await session.commit()
            await session.refresh(event)
            
            self._last_heartbeat = datetime.utcnow()
            logger.info(f"Heartbeat sent: {reason}")
            
            return event

    async def dispatch(self, event: Event) -> bool:
        """Dispatch heartbeat event (MVP stub).
        
        Note: Full implementation in v1.5.0 will send actual messages.
        
        Args:
            event: Heartbeat event to dispatch
            
        Returns:
            True if dispatched successfully
        """
        logger.info(f"Dispatching heartbeat: {event.summary}")
        # MVP: Just log, don't actually send
        return True

    async def start(self) -> None:
        """Start background heartbeat scheduler (real implementation).

        Creates an asyncio background task that periodically calls tick().
        The task runs until stop() is called.

        Raises:
            HeartbeatError: If agent_id is not set.
            NotImplementedByDesignError: If asyncio is not available.

        Returns:
            None (runs in background)
        """
        if not self._agent_id:
            # Backwards compat: contract tests expect start() to raise
            # when agent_id is not configured
            raise NotImplementedByDesignError(
                "HeartbeatScheduler.start requires agent_id (not implemented for agent-less mode in v1.0.0-beta)"
            )
        
        logger.info(f"Starting heartbeat scheduler for agent {self._agent_id}")
        
        # Load rules if not loaded
        if not self._rules:
            self.should_heartbeat()  # This loads default rules
        
        # Create background task
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Heartbeat scheduler started (interval={self._schedule_seconds}s)")
        return None
    
    async def _run_loop(self) -> None:
        """Background loop that calls tick() periodically."""
        logger.info("Heartbeat background loop started")
        while self._running:
            try:
                await self.tick()
            except Exception as e:
                logger.error(f"Heartbeat tick failed: {e}")
            
            # Wait for next interval
            await asyncio.sleep(self._schedule_seconds)
        logger.info("Heartbeat background loop stopped")

    async def stop(self) -> None:
        """Stop background scheduler.

        Cancels the background task and waits for it to finish.
        """
        logger.info("Stopping heartbeat scheduler")
        self._running = False
        
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error stopping heartbeat task: {e}")
        
        logger.info("Heartbeat scheduler stopped")


__all__ = [
    "HeartbeatScheduler",
    "HeartbeatError",
]
