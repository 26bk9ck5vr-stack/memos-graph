"""memos-graph heartbeat scheduler — v0.1.0-docs 占位。

TASK_BREAKDOWN T12.1-T12.4 实装。
"""

from __future__ import annotations

from typing import Any


# === 异常 ===

class HeartbeatError(Exception):
    """Heartbeat scheduler 基类异常。"""


class NotImplementedByDesignError(HeartbeatError):
    """v0.1.0-docs 阶段未实装。T12.x 实装后删除。"""


class HeartbeatScheduler:
    """心跳调度器（v0.1 占位）。

    公开方法（**契约** — 见 TEST_SPEC §4）：
    - `start() -> None`  启动 asyncio task
    - `stop() -> None`   停止
    - `tick() -> int`    跑一次 tick（手动触发），返回触发的 agent 数
    - `should_heartbeat(agent_state) -> bool`  判断是否触发
    - `dispatch(agent_id, message) -> bool` 投递到飞书

    v0.1 阶段：所有方法 raise NotImplementedByDesignError。
    """

    def __init__(
        self,
        schedule_seconds: int = 1800,
        quiet_hours: str = "23:00-08:00",
        rules: Any = None,
    ) -> None:
        self._schedule_seconds = schedule_seconds
        self._quiet_hours = quiet_hours
        self._rules = rules
        self._task: Any = None  # asyncio.Task 实际类型

    async def start(self) -> None:
        raise NotImplementedByDesignError(
            "HeartbeatScheduler.start 待 T12.2 实装"
        )

    async def stop(self) -> None:
        raise NotImplementedByDesignError(
            "HeartbeatScheduler.stop 待 T12.2 实装"
        )

    async def tick(self) -> int:
        """跑一次 tick，返回触发的 agent 数。"""
        raise NotImplementedByDesignError(
            "HeartbeatScheduler.tick 待 T12.2 实装"
        )

    def should_heartbeat(self, agent_state: dict) -> bool:
        """判断某 agent 是否应该发心跳。"""
        raise NotImplementedByDesignError(
            "HeartbeatScheduler.should_heartbeat 待 T12.1 + T12.2 实装"
        )

    async def dispatch(self, agent_id: str, message: str) -> bool:
        """投递心跳消息到飞书。"""
        raise NotImplementedByDesignError(
            "HeartbeatScheduler.dispatch 待 T12.3 实装"
        )


__all__ = [
    "HeartbeatScheduler",
    "HeartbeatError",
    "NotImplementedByDesignError",
]
