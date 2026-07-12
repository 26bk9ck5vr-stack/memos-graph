"""Pack installer - installs packs from local paths or Git URLs."""

import shutil
from pathlib import Path
from typing import Optional
from .loader import PackLoader


class PackInstallError(Exception):
    """Exception raised when pack installation fails."""
    pass


class PackInstaller:
    """Install Agent Packs to the memos-graph packs directory."""
    
    DEFAULT_INSTALL_DIR = Path.home() / ".local" / "share" / "memos-graph" / "packs"
    
    def __init__(self, install_dir: Optional[Path] = None):
        self.install_dir = install_dir or self.DEFAULT_INSTALL_DIR
        self.install_dir.mkdir(parents=True, exist_ok=True)
    
    def install_local(self, source_path: Path, pack_id: Optional[str] = None) -> str:
        """
        Install pack from local path.
        
        Args:
            source_path: Path to source pack directory
            pack_id: Optional pack ID override (uses pack.yaml id if not provided)
            
        Returns:
            Installed pack ID
            
        Raises:
            FileNotFoundError: If source path doesn't exist
            PackInstallError: If installation fails
        """
        if not source_path.exists():
            raise FileNotFoundError(f"Source path not found: {source_path}")
        
        try:
            # Load and validate pack.yaml
            pack_id_from_yaml, name, version, manifest = PackLoader.load_minimal(source_path)
        except Exception as e:
            raise PackInstallError(f"Failed to load pack.yaml: {e}")
        
        # Use provided pack_id or from yaml
        if pack_id is None:
            pack_id = pack_id_from_yaml
        
        install_path = self.install_dir / pack_id
        
        # Copy files
        if install_path.exists():
            shutil.rmtree(install_path)
        
        shutil.copytree(source_path, install_path)
        
        return pack_id
    
    def get_install_path(self, pack_id: str) -> Path:
        """Get the install path for a pack."""
        return self.install_dir / pack_id
    
    def pack_exists(self, pack_id: str) -> bool:
        """Check if a pack is already installed."""
        return (self.install_dir / pack_id).exists()


# Compatibility exports
def install_pack(source, pack_id=None):
    return PackInstaller().install_local(Path(source), pack_id)

def update_pack(pack_id: str) -> None:
    """Update a pack (stub - not implemented in MVP)."""
    raise NotImplementedError("Pack update not implemented in MVP")

def uninstall_pack(pack_id: str) -> None:
    """Uninstall a pack (stub - not implemented in MVP)."""
    raise NotImplementedError("Pack uninstall not implemented in MVP")
