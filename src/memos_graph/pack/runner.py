"""Pack Runner — real execution for v1.0.0-beta.

Implements actual pack execution:
- Loads pack.yaml manifest
- Executes scripts in pack/scripts/ directory
- Returns real execution results
- Supports interactive mode

Note: Agent skill execution and conversation flow planned for v1.5.0.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Any, Optional
import yaml

logger = logging.getLogger(__name__)


class PackRunError(Exception):
    """Error running a pack."""
    pass


class PackRunner:
    """Real pack runner for v1.0.0-beta.

    Features:
    - Load pack.yaml manifest
    - Execute pack scripts (real execution)
    - Support interactive mode (simple echo for MVP)
    - Return actual execution results

    TODO (v1.5.0):
    - Agent skill execution
    - Conversation flow management
    - State persistence
    - Error recovery
    """

    def __init__(
        self,
        pack_id: str,
        pack_dir: Path | str,
    ) -> None:
        """Initialize pack runner.

        Args:
            pack_id: Pack identifier
            pack_dir: Pack installation directory
        """
        self._pack_id = pack_id
        self._pack_dir = Path(pack_dir)
        self._manifest: dict[str, Any] | None = None

    async def load_manifest(self) -> dict[str, Any]:
        """Load pack.yaml manifest.

        Raises:
            PackRunError: If manifest cannot be loaded.
        """
        manifest_file = self._pack_dir / "pack.yaml"
        
        if not manifest_file.exists():
            raise PackRunError(f"Pack manifest not found: {manifest_file}")
        
        try:
            with open(manifest_file, 'r', encoding='utf-8') as f:
                self._manifest = yaml.safe_load(f)
        except Exception as e:
            raise PackRunError(f"Failed to parse pack.yaml: {e}")
        
        if not isinstance(self._manifest, dict):
            raise PackRunError(f"Invalid pack.yaml: not a dict")
        
        logger.info(f"Loaded pack manifest: {self._pack_id}")
        return self._manifest

    async def run(
        self,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run the pack.

        For v1.0.0-beta, executes the pack's main script if defined in manifest.
        If no script is defined, returns basic manifest info.

        Args:
            context: Execution context (agent state, memories, etc.)

        Returns:
            Execution result with status, output, and any errors

        Raises:
            PackRunError: If execution fails.
        """
        if self._manifest is None:
            await self.load_manifest()
        
        logger.info(f"Running pack: {self._pack_id}")
        
        # Check for main script
        scripts = self._manifest.get("scripts", {})
        main_script = scripts.get("main") or scripts.get("run") or scripts.get("entry")
        
        if not main_script:
            # No script defined - return basic manifest execution
            return {
                "pack_id": self._pack_id,
                "status": "success",
                "message": "Pack executed (no main script defined)",
                "output": {
                    "manifest_name": self._manifest.get("name", self._pack_id),
                    "manifest_version": self._manifest.get("version", "unknown"),
                },
            }
        
        # Execute main script
        script_path = self._pack_dir / main_script
        if not script_path.exists():
            raise PackRunError(f"Main script not found: {script_path}")
        
        return await self.run_script(main_script, args=[])

    async def run_script(
        self,
        script_name: str,
        args: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run a pack script.

        Real execution: runs the script as subprocess and captures output.

        Args:
            script_name: Script name (relative to scripts/ or pack root)
            args: Script arguments

        Returns:
            Script execution result with stdout, stderr, return code

        Raises:
            PackRunError: If script execution fails.
        """
        # Try scripts/ directory first, then pack root
        scripts_dir = self._pack_dir / "scripts"
        script_path = scripts_dir / script_name
        
        if not script_path.exists():
            script_path = self._pack_dir / script_name
        
        if not script_path.exists():
            raise PackRunError(f"Script not found: {script_name}")
        
        # Determine executable
        if script_path.suffix == ".py":
            # Use sys.executable for cross-platform compatibility
            import sys
            cmd = [sys.executable, str(script_path)] + (args or [])
        elif script_path.suffix in (".sh", ".bash"):
            cmd = ["bash", str(script_path)] + (args or [])
        else:
            # Try executing directly
            cmd = [str(script_path)] + (args or [])
        
        logger.info(f"Executing script: {' '.join(cmd)}")
        
        try:
            # Run subprocess with timeout
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._pack_dir),
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=30.0,  # 30 second timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise PackRunError(f"Script timed out after 30s: {script_name}")
            
            stdout_str = stdout.decode('utf-8', errors='replace') if stdout else ""
            stderr_str = stderr.decode('utf-8', errors='replace') if stderr else ""
            
            return {
                "script": script_name,
                "status": "success" if process.returncode == 0 else "failed",
                "return_code": process.returncode,
                "stdout": stdout_str,
                "stderr": stderr_str,
            }
        
        except PackRunError:
            raise
        except Exception as e:
            raise PackRunError(f"Failed to execute script {script_name}: {e}")


async def run_pack(
    pack_id: str,
    pack_dir: Path | str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convenience function to run a pack.

    Args:
        pack_id: Pack identifier
        pack_dir: Pack installation directory
        context: Execution context

    Returns:
        Execution result
    """
    runner = PackRunner(pack_id, pack_dir)
    return await runner.run(context)


async def run_pack_interactive(
    pack_id: str,
    pack_dir: Path | str,
    user_input: str,
) -> dict[str, Any]:
    """Run pack in interactive mode.

    For v1.0.0-beta: executes pack's "interactive" script if defined,
    otherwise returns a simple echo response.

    Args:
        pack_id: Pack identifier
        pack_dir: Pack installation directory
        user_input: User input string

    Returns:
        Response to user input
    """
    runner = PackRunner(pack_id, pack_dir)
    
    try:
        await runner.load_manifest()
    except PackRunError:
        pass
    
    # Check for interactive script
    if runner._manifest:
        scripts = runner._manifest.get("scripts", {})
        interactive_script = scripts.get("interactive") or scripts.get("chat")
        
        if interactive_script:
            try:
                result = await runner.run_script(interactive_script, args=[user_input])
                return {
                    "pack_id": pack_id,
                    "response": result.get("stdout", "").strip() or "...",
                    "status": result.get("status", "success"),
                }
            except PackRunError as e:
                return {
                    "pack_id": pack_id,
                    "response": f"Error: {e}",
                    "status": "failed",
                }
    
    # Default interactive response (MVP)
    return {
        "pack_id": pack_id,
        "response": f"[{pack_id}] Received: {user_input[:100]}",
        "status": "success",
    }


__all__ = [
    "PackRunner",
    "PackRunError",
    "run_pack",
    "run_pack_interactive",
]