"""Pack registry - manages pack registration in database."""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone


def list_packs(enabled_only: bool = False) -> List[Dict[str, Any]]:
    """List all registered packs (stub - use API instead)."""
    raise NotImplementedError("Use GET /api/v1/packs instead")


def get_pack(pack_id: str) -> Optional[Dict[str, Any]]:
    """Get pack by ID (stub - use API instead)."""
    raise NotImplementedError("Use GET /api/v1/packs/{id} instead")


def register_pack(
    pack_id: str,
    name: str,
    version: str,
    manifest: Dict[str, Any],
    install_path: str,
    enabled: bool = True,
) -> Dict[str, Any]:
    """Register a pack in database (stub - use API instead)."""
    raise NotImplementedError("Use POST /api/v1/packs instead")


def set_pack_enabled(pack_id: str, enabled: bool) -> None:
    """Enable or disable a pack (stub - use API instead)."""
    raise NotImplementedError("Use PUT /api/v1/packs/{id}/enable instead")


def unregister_pack(pack_id: str) -> None:
    """Unregister a pack (stub - use API instead)."""
    raise NotImplementedError("Not implemented yet")
