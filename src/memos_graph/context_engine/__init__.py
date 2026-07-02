"""memos-graph context engine for injecting memories into prompts — v0.1.0-docs 占位。

TASK_BREAKDOWN T7 + ARCHITECTURE §3.4 描述。
"""

from __future__ import annotations

from typing import Any


# === 异常 ===

class ContextEngineError(Exception):
    """Context engine 基类异常。"""


class NotImplementedByDesignError(ContextEngineError):
    """v0.1.0-docs 阶段未实装。"""


class ContextInjector:
    """向 runtime prompt 注入长期记忆（v0.1 占位）。

    公开方法（**契约** — 见 ARCHITECTURE §3.4）：
    - `build_system_prompt(agent_id, base_prompt) -> str`
    - `inject(agent_id, messages) -> list[dict]`

    注入内容（按顺序）：
    1. SOUL.md + IDENTITY.md
    2. agent_state 快照（"你现在阶段 2，心情 70，精力 60"）
    3. user_profile（"主人喜欢甜食、讨厌香菜"）
    4. open promises（"你答应过周末做蛋糕"）
    5. 最近 5 条 events 摘要
    """

    def __init__(
        self,
        pack_dir: str | None = None,
        db_url: str | None = None,
    ) -> None:
        self._pack_dir = pack_dir
        self._db_url = db_url

    async def build_system_prompt(self, agent_id: str, base_prompt: str = "") -> str:
        raise NotImplementedByDesignError(
            "ContextInjector.build_system_prompt 待实装"
        )

    async def inject(self, agent_id: str, messages: list[dict]) -> list[dict]:
        raise NotImplementedByDesignError(
            "ContextInjector.inject 待实装"
        )


__all__ = [
    "ContextInjector",
    "ContextEngineError",
    "NotImplementedByDesignError",
]
