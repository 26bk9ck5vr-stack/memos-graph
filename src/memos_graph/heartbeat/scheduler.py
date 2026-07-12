"""Heartbeat scheduler - checks and triggers active messages for agents."""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from memos_graph.db.models import AgentState

logger = logging.getLogger(__name__)


class HeartbeatScheduler:
    """Scheduler for agent heartbeat (active messages)."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_pending_heartbeats(self) -> List[AgentState]:
        """
        Get all agents with pending_heartbeat = True.
        
        Returns:
            List of AgentState objects that need heartbeat
        """
        result = await session.execute(
            select(AgentState).where(AgentState.pending_heartbeat == True)
        )
        return list(result.scalars().all())
    
    async def check_and_schedule(self) -> List[str]:
        """
        Check all agents and schedule heartbeats based on thresholds.
        
        MVP logic:
        - If last_interaction > threshold for current stage, set pending_heartbeat = True
        - Returns list of agent_ids that need heartbeat
        
        Returns:
            List of agent IDs that need heartbeat
        """
        # Default thresholds (hours since last interaction)
        thresholds = {
            1: 48,  # Stage 1: 48 hours
            2: 24,  # Stage 2: 24 hours
            3: 12,  # Stage 3: 12 hours
            4: 8,   # Stage 4: 8 hours
            5: 6,   # Stage 5: 6 hours
        }
        
        now = datetime.now(timezone.utc)
        agents_needing_heartbeat = []
        
        # Get all agent states
        result = await self.session.execute(select(AgentState))
        states = result.scalars().all()
        
        for state in states:
            # Skip if already pending
            if state.pending_heartbeat:
                continue
            
            # Check if interaction is old enough
            if state.last_interaction:
                hours_since = (now - state.last_interaction).total_seconds() / 3600
                threshold = thresholds.get(state.stage, 24)
                
                if hours_since >= threshold:
                    state.pending_heartbeat = True
                    agents_needing_heartbeat.append(state.agent_id)
                    logger.info(f"Agent {state.agent_id} scheduled for heartbeat (stage={state.stage}, hours_since={hours_since:.1f})")
        
        if agents_needing_heartbeat:
            await self.session.commit()
        
        return agents_needing_heartbeat
    
    async def mark_heartbeat_sent(self, agent_id: str) -> None:
        """
        Mark heartbeat as sent for an agent.
        
        Args:
            agent_id: The agent ID to update
        """
        result = await self.session.execute(
            select(AgentState).where(AgentState.agent_id == agent_id)
        )
        state = result.scalar_one_or_none()
        
        if state:
            state.pending_heartbeat = False
            state.last_heartbeat = datetime.now(timezone.utc)
            await self.session.commit()
            logger.info(f"Agent {agent_id} heartbeat marked as sent")
    
    async def trigger_manual_heartbeat(self, agent_id: str) -> bool:
        """
        Manually trigger a heartbeat for an agent.
        
        Args:
            agent_id: The agent ID to trigger
            
        Returns:
            True if successful, False if agent not found
        """
        result = await self.session.execute(
            select(AgentState).where(AgentState.agent_id == agent_id)
        )
        state = result.scalar_one_or_none()
        
        if not state:
            return False
        
        state.pending_heartbeat = True
        await self.session.commit()
        logger.info(f"Agent {agent_id} manual heartbeat triggered")
        return True
