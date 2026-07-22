"""Heartbeat module - MVP scheduler + rules (v0.9.0-beta).

Note: HeartbeatScheduler MVP implemented for v1.0.0.
Full async background scheduling planned for v1.5.0.
"""

# Re-export NotImplementedByDesignError for cross-module tests
from memos_graph.embedding import NotImplementedByDesignError

# HeartbeatScheduler MVP
from .scheduler import HeartbeatScheduler, HeartbeatError

from .rules import parse_heartbeat_rules, HeartbeatRuleConfig, HeartbeatRuleConfig as HeartbeatRule

__all__ = [
    "HeartbeatScheduler",
    "HeartbeatError",
    "parse_heartbeat_rules",
    "HeartbeatRule",
    "HeartbeatRuleConfig",
    "NotImplementedByDesignError",
]
