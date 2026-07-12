"""Pack loader - parses pack.yaml files."""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class PackManifest:
    """Pack manifest structure (MVP - minimal fields)."""
    id: str
    name: str
    version: str
    runtime: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    license: Optional[str] = None
    memos_graph: Dict[str, Any] = field(default_factory=dict)
    heartbeat: Dict[str, Any] = field(default_factory=dict)
    skills: List[str] = field(default_factory=list)
    preserve_on_upgrade: List[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PackManifest':
        """Create PackManifest from dict."""
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            version=data.get('version', ''),
            runtime=data.get('runtime'),
            description=data.get('description'),
            author=data.get('author'),
            license=data.get('license'),
            memos_graph=data.get('memos_graph', {}),
            heartbeat=data.get('heartbeat', {}),
            skills=data.get('skills', []),
            preserve_on_upgrade=data.get('preserve_on_upgrade', []),
        )


class PackLoadError(Exception):
    """Exception raised when pack.yaml loading fails."""
    pass


class PackLoader:
    """Load and parse pack.yaml files."""
    
    @staticmethod
    def load(pack_path: Path) -> Dict[str, Any]:
        """
        Load pack.yaml from a directory.
        
        Args:
            pack_path: Path to pack directory (should contain pack.yaml)
            
        Returns:
            Parsed pack.yaml content as dict
            
        Raises:
            FileNotFoundError: If pack.yaml doesn't exist
            PackLoadError: If YAML parsing fails
        """
        yaml_path = pack_path / "pack.yaml"
        
        if not yaml_path.exists():
            raise FileNotFoundError(f"pack.yaml not found at {yaml_path}")
        
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise PackLoadError(f"Failed to parse pack.yaml: {e}")
    
    @staticmethod
    def validate_minimal(manifest: Dict[str, Any]) -> tuple[str, str, str]:
        """
        Validate minimal pack manifest (MVP).
        
        Required fields:
        - id: str (unique identifier)
        - name: str (display name)
        - version: str (semantic version)
        
        Returns:
            Tuple of (id, name, version)
            
        Raises:
            ValueError: If required fields are missing
        """
        required = ['id', 'name', 'version']
        missing = [f for f in required if f not in manifest]
        
        if missing:
            raise ValueError(f"Missing required fields: {missing}")
        
        return (
            str(manifest['id']),
            str(manifest['name']),
            str(manifest['version']),
        )
    
    @staticmethod
    def load_minimal(pack_path: Path) -> tuple[str, str, str, Dict[str, Any]]:
        """
        Load pack.yaml and extract minimal info (MVP).
        
        Returns:
            Tuple of (id, name, version, full_manifest)
        """
        manifest = PackLoader.load(pack_path)
        pack_id, name, version = PackLoader.validate_minimal(manifest)
        return pack_id, name, version, manifest


# Compatibility exports
load_pack_manifest = PackLoader.load
load_pack_from_dir = PackLoader.load_minimal


def load_pack_from_git(git_url: str, target_path: Optional[Path] = None) -> tuple[str, str, str, Dict[str, Any]]:
    """
    Load pack from Git URL (stub - not implemented in MVP).
    
    Raises:
        NotImplementedError: Git loading not supported in MVP
    """
    raise NotImplementedError("Git loading not supported in MVP. Use local path only.")


def list_agent_files(pack_path: Path) -> list[str]:
    """List agent files in a pack directory."""
    agent_dir = pack_path / "agent"
    if not agent_dir.exists():
        return []
    
    files = []
    for f in agent_dir.iterdir():
        if f.is_file() and f.suffix in ['.md', '.txt', '.yaml', '.yml']:
            files.append(f.name)
    return files


def copy_pack_to_install_dir(source: Path, dest: Path) -> None:
    """Copy pack to installation directory (stub - use PackInstaller instead)."""
    from memos_graph.pack.installer import PackInstaller
    installer = PackInstaller(install_dir=dest.parent)
    installer.install_local(source)
