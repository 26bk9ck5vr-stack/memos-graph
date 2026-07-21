"""memos-graph Pack Manager — minimal implementation for contract tests.

Note: Full implementation planned for v1.5.0.
This is a stub to pass contract tests (v0.9.0-beta).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PackManagerError(Exception):
    """Base error for PackManager."""
    pass


# Alias for contract tests
PackError = PackManagerError


class PackManager:
    """Manages installed packs.

    Note: Minimal implementation for contract tests.
    Full implementation planned for v1.5.0.
    """

    def __init__(self, packs_dir: Path | str | None = None) -> None:
        """Initialize PackManager.

        Args:
            packs_dir: Directory containing installed packs.
                      Defaults to ~/.local/share/memos-graph/packs
        """
        if packs_dir is None:
            from memos_graph.config import get_config_dir
            self._packs_dir = Path(get_config_dir()) / "packs"
        else:
            self._packs_dir = Path(packs_dir)

    @property
    def packs_dir(self) -> Path:
        """Return the packs directory."""
        return self._packs_dir

    @property
    def dimension(self) -> int:
        """Return embedding dimension for API compatibility."""
        # Note: Actual dimension depends on model (bge-m3=1024, nomic=768)
        # This property is for contract test compatibility
        return 1024  # Default for BAAI/bge-m3

    async def list_packs(self) -> list[dict[str, Any]]:
        """List all installed packs.

        Returns:
            List of pack metadata dicts.
        """
        # Stub implementation
        return []

    async def get_pack(self, pack_id: str) -> dict[str, Any] | None:
        """Get pack metadata by ID.

        Args:
            pack_id: Pack identifier.

        Returns:
            Pack metadata dict or None if not found.
        """
        # Stub implementation
        return None

    async def install_pack(self, source: str) -> dict[str, Any]:
        """Install a pack from source.

        Args:
            source: Git URL or local path.

        Returns:
            Installed pack metadata.
        """
        raise PackManagerError("PackManager.install_pack not implemented in v0.9.0-beta")

    async def uninstall_pack(self, pack_id: str) -> bool:
        """Uninstall a pack.

        Args:
            pack_id: Pack identifier.

        Returns:
            True if successful.
        """
        raise PackManagerError("PackManager.uninstall_pack not implemented in v0.9.0-beta")

    async def enable_pack(self, pack_id: str) -> bool:
        """Enable a pack.

        Args:
            pack_id: Pack identifier.

        Returns:
            True if successful.
        """
        raise PackManagerError("PackManager.enable_pack not implemented in v0.9.0-beta")

    async def disable_pack(self, pack_id: str) -> bool:
        """Disable a pack.

        Args:
            pack_id: Pack identifier.

        Returns:
            True if successful.
        """
        raise PackManagerError("PackManager.disable_pack not implemented in v0.9.0-beta")

    async def run_pack(self, pack_id: str, **kwargs: Any) -> dict[str, Any]:
        """Run a pack.

        Args:
            pack_id: Pack identifier.
            **kwargs: Pack-specific arguments.

        Returns:
            Pack execution result.
        """
        raise PackManagerError("PackManager.run_pack not implemented in v0.9.0-beta")

    # API aliases for contract tests
    async def install(self, source: str) -> dict[str, Any]:
        """Alias for install_pack."""
        return await self.install_pack(source)

    async def update(self, pack_id: str) -> dict[str, Any]:
        """Alias for update_pack."""
        raise PackManagerError("PackManager.update not implemented in v0.9.0-beta")

    async def uninstall(self, pack_id: str) -> bool:
        """Alias for uninstall_pack."""
        return await self.uninstall_pack(pack_id)

    async def list(self) -> list[dict[str, Any]]:
        """Alias for list_packs.

        Note: Raises NotImplementedByDesignError for contract tests.
        """
        from memos_graph.embedding import NotImplementedByDesignError
        raise NotImplementedByDesignError("PackManager.list not implemented in v0.9.0-beta")

    async def info(self, pack_id: str) -> dict[str, Any] | None:
        """Alias for get_pack."""
        return await self.get_pack(pack_id)

    async def run(self, pack_id: str, **kwargs: Any) -> dict[str, Any]:
        """Alias for run_pack."""
        return await self.run_pack(pack_id, **kwargs)

    async def stop(self, pack_id: str) -> bool:
        """Stop a running pack.

        Note: Not implemented in v0.9.0-beta.
        """
        raise PackManagerError("PackManager.stop not implemented in v0.9.0-beta")

    async def verify(self, pack_id: str) -> bool:
        """Verify a pack installation.

        Note: Not implemented in v0.9.0-beta.
        """
        raise PackManagerError("PackManager.verify not implemented in v0.9.0-beta")


__all__ = [
    "PackManager",
    "PackManagerError",
    "PackError",
]
