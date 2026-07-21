"""memos-graph Pack protocol — loader/installer/manager (v0.9.0-beta).

Note: Registry and Runner are not implemented in v0.9.0-beta.
See KNOWN_ISSUES.md for details.
"""

from memos_graph.pack.loader import (
    PackLoadError,
    PackManifest,
    load_pack_from_dir,
    load_pack_from_git,
    load_pack_manifest,
    list_agent_files,
    copy_pack_to_install_dir,
)
from memos_graph.pack.installer import (
    install_pack,
    update_pack,
    uninstall_pack,
    PackInstallError,
)
from memos_graph.pack.manager import (
    PackManager,
    PackManagerError,
    PackError,
)

# Re-export NotImplementedByDesignError from embedding for cross-module tests
from memos_graph.embedding import NotImplementedByDesignError

# Registry and Runner are not implemented in v0.9.0-beta
__all__ = [
    "PackLoadError",
    "PackManifest",
    "load_pack_from_dir",
    "load_pack_from_git",
    "load_pack_manifest",
    "list_agent_files",
    "copy_pack_to_install_dir",
    "install_pack",
    "update_pack",
    "uninstall_pack",
    "PackInstallError",
    "PackManager",
    "PackManagerError",
    "PackError",
    "NotImplementedByDesignError",
]

__all__ = [
    # Loader
    "PackLoadError",
    "PackManifest",
    "load_pack_from_dir",
    "load_pack_from_git",
    "load_pack_manifest",
    "list_agent_files",
    "copy_pack_to_install_dir",
    # Installer
    "install_pack",
    "update_pack",
    "uninstall_pack",
    "PackInstallError",
    # Registry
    "list_packs",
    "get_pack",
    "register_pack",
    "set_pack_enabled",
    "unregister_pack",
    # Runner
    "run_pack",
    "run_pack_interactive",
    "PackRunError",
]
