"""Heartbeat module - placeholder (v0.9.0-beta).

Note: HeartbeatScheduler is not implemented in v0.9.0-beta.
Only rules.py is available for heartbeat rule parsing.

See KNOWN_ISSUES.md for implementation status.
"""

# Re-export NotImplementedByDesignError for cross-module tests
from memos_graph.embedding import NotImplementedByDesignError

# HeartbeatScheduler will be implemented in v1.5.0
# from .scheduler import HeartbeatScheduler

from .rules import parse_heartbeat_rules, HeartbeatRuleConfig, HeartbeatRuleConfig as HeartbeatRule

__all__ = [
    "parse_heartbeat_rules",
    "HeartbeatRule",
    "HeartbeatRuleConfig",
    "NotImplementedByDesignError",
    # "HeartbeatScheduler",  # Not implemented in v0.9.0-beta
]
