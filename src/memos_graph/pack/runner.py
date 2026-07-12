"""Pack runner - executes pack agent files."""

from typing import Optional, Dict, Any


class PackRunError(Exception):
    """Exception raised when pack execution fails."""
    pass


def run_pack(pack_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run a pack (stub - not implemented in MVP).
    
    Returns:
        Execution result with status and output
        
    Raises:
        PackRunError: If execution fails
    """
    raise NotImplementedError("Pack execution not implemented in MVP")


def run_pack_interactive(pack_id: str) -> None:
    """
    Run pack in interactive mode (stub - not implemented).
    
    Raises:
        PackRunError: If execution fails
    """
    raise NotImplementedError("Interactive mode not implemented in MVP")
