"""memos-graph Pack protocol — loader/installer/runner (v0.9.0-beta).

Note: Runner MVP implemented for v1.0.0.
Registry not implemented (planned for v1.5.0).
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
from memos_graph.pack.runner import (
    PackRunner,
    PackRunError,
    run_pack,
    run_pack_interactive,
)

# Re-export NotImplementedByDesignError from embedding for cross-module tests
from memos_graph.embedding import NotImplementedByDesignError

# Registry is not implemented in v0.9.0-beta
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
    # Manager
    "PackManager",
    "PackManagerError",
    "PackError",
    # Runner (MVP)
    "PackRunner",
    "PackRunError",
    "run_pack",
    "run_pack_interactive",
    # Errors
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
