"""memos-graph Pack management — v0.1.0-docs 占位。

TASK_BREAKDOWN T11.1-T11.5 实装。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


# === 异常 ===

class PackError(Exception):
    """Pack manager 基类异常。"""


class NotImplementedByDesignError(PackError):
    """v0.1.0-docs 阶段未实装。T11.x 实装后删除。"""


class PackManager:
    """Pack 安装/升级/运行管理器（v0.1 占位）。

    公开方法（**契约**）：
    - `install(source: str | Path, options: dict) -> InstallResult`
    - `update(pack_id: str, to_version: str | None) -> UpdateResult`
    - `uninstall(pack_id: str, keep_data: bool = True) -> None`
    - `list(enabled_only: bool = True) -> list[PackInfo]`
    - `info(pack_id: str) -> PackInfo`
    - `run(pack_id: str, options: dict) -> RunHandle`
    - `stop(pack_id: str) -> None`
    - `verify(pack_id: str) -> VerifyResult`
    """

    PACKS_DIR = Path("~/.local/share/memos-graph/packs").expanduser()

    def __init__(self, db_url: str | None = None, packs_dir: Path | None = None) -> None:
        self._db_url = db_url
        self._packs_dir = packs_dir or self.PACKS_DIR

    async def install(self, source: str | Path, options: dict[str, Any] | None = None) -> dict:
        raise NotImplementedByDesignError(
            "PackManager.install 待 T11.2 实装（PACK_PROTOCOL §3）"
        )

    async def update(self, pack_id: str, to_version: str | None = None) -> dict:
        raise NotImplementedByDesignError(
            "PackManager.update 待 T11.2 实装（PACK_PROTOCOL §4）"
        )

    async def uninstall(self, pack_id: str, keep_data: bool = True) -> None:
        raise NotImplementedByDesignError(
            "PackManager.uninstall 待 T11.2 实装"
        )

    async def list(self, enabled_only: bool = True) -> list[dict]:
        raise NotImplementedByDesignError(
            "PackManager.list 待 T11.4 实装"
        )

    async def info(self, pack_id: str) -> dict:
        raise NotImplementedByDesignError(
            "PackManager.info 待 T11.4 实装"
        )

    async def run(self, pack_id: str, options: dict[str, Any] | None = None) -> dict:
        raise NotImplementedByDesignError(
            "PackManager.run 待 T11.3 实装（PACK_PROTOCOL §5）"
        )

    async def stop(self, pack_id: str) -> None:
        raise NotImplementedByDesignError(
            "PackManager.stop 待 T11.3 实装"
        )

    async def verify(self, pack_id: str) -> dict:
        raise NotImplementedByDesignError(
            "PackManager.verify 待 T11.x 实装（checksum）"
        )


__all__ = [
    "PackManager",
    "PackError",
    "NotImplementedByDesignError",
]
