"""Heartbeat rules parsing from HEARTBEAT.md storage files."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# === Data Classes ===

@dataclass
class HeartbeatRuleConfig:
    """Parsed heartbeat rule configuration."""
    name: str
    interval: str = "24h"
    quiet_hours: str | None = None  # e.g. "23:00-08:00"
    stage_thresholds: list[float] = field(
        default_factory=lambda: [6.0, 24.0, 72.0, 168.0]
    )  # [stage_1_hours, stage_2_hours, stage_3_hours, stage_4_hours]
    enabled: bool = True
    use_llm_content: bool = False
    raw_lines: list[str] = field(default_factory=list)


# === Parser ===

def parse_heartbeat_rules(content: str) -> list[HeartbeatRuleConfig]:
    """Parse heartbeat rules from HEARTBEAT.md content.

    Supports format:
        # 心跳规则示例
        - name: daily-checkin
          interval: 24h
          quiet_hours: 23:00-08:00
          stage_thresholds: 6h,24h,72h,168h
          enabled: true

    Args:
        content: Raw HEARTBEAT.md content

    Returns:
        List of parsed HeartbeatRuleConfig objects
    """
    rules: list[HeartbeatRuleConfig] = []
    current_rule: dict[str, Any] = {}

    for line in content.split("\n"):
        stripped = line.strip()

        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            continue

        # List item (rule entry)
        if stripped.startswith("-"):
            # Save previous rule if exists
            if current_rule:
                rules.append(_dict_to_config(current_rule))

            current_rule = {}

            # Parse key:value on the same line as the list marker (e.g. "- name: foo")
            # This line may also contain just "- name: foo\n  interval: 24h"
            # So we still need to parse it below
            if ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip().lstrip("- ").lower()
                value = value.strip()

                if key == "name":
                    current_rule["name"] = value
                elif key == "interval":
                    current_rule["interval"] = value
                elif key == "quiet_hours":
                    current_rule["quiet_hours"] = value if value != "null" else None
                elif key == "stage_thresholds":
                    current_rule["stage_thresholds"] = _parse_thresholds(value)
                elif key == "enabled":
                    current_rule["enabled"] = value.lower() in ("true", "1", "yes", "on")
                elif key == "use_llm_content":
                    current_rule["use_llm_content"] = value.lower() in ("true", "1", "yes", "on")

            continue

        # Parse key: value pairs within rule
        if current_rule and ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip().lower()
            value = value.strip()

            if key == "name":
                current_rule["name"] = value
            elif key == "interval":
                current_rule["interval"] = value
            elif key == "quiet_hours":
                current_rule["quiet_hours"] = value if value != "null" else None
            elif key == "stage_thresholds":
                current_rule["stage_thresholds"] = _parse_thresholds(value)
            elif key == "enabled":
                current_rule["enabled"] = value.lower() in ("true", "1", "yes", "on")
            elif key == "use_llm_content":
                current_rule["use_llm_content"] = value.lower() in ("true", "1", "yes", "on")

    # Don't forget last rule
    if current_rule:
        rules.append(_dict_to_config(current_rule))

    return rules


def _parse_thresholds(value: str) -> list[float]:
    """Parse stage thresholds from comma-separated string.

    Examples:
        "6h,24h,72h,168h" -> [6.0, 24.0, 72.0, 168.0]
        "6,24,72,168" -> [6.0, 24.0, 72.0, 168.0]
    """
    thresholds = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        # Remove 'h' suffix if present and convert to float
        if part.endswith("h"):
            thresholds.append(float(part[:-1]))
        else:
            thresholds.append(float(part))
    return thresholds


def _dict_to_config(d: dict[str, Any]) -> HeartbeatRuleConfig:
    """Convert parsed dict to HeartbeatRuleConfig."""
    return HeartbeatRuleConfig(
        name=d.get("name", "unnamed"),
        interval=d.get("interval", "24h"),
        quiet_hours=d.get("quiet_hours"),
        stage_thresholds=d.get(
            "stage_thresholds",
            [6.0, 24.0, 72.0, 168.0]
        ),
        enabled=d.get("enabled", True),
        use_llm_content=d.get("use_llm_content", False),
    )


# === Storage Loader ===

def load_rules_from_storage(
    storage_path: str | Path | None = None,
) -> list[HeartbeatRuleConfig]:
    """Load heartbeat rules from storage/HEARTBEAT.md.

    Args:
        storage_path: Path to storage directory. If None, uses default:
            {project_root}/storage/HEARTBEAT.md

    Returns:
        List of parsed HeartbeatRuleConfig objects
    """
    if storage_path is None:
        # Default: storage/HEARTBEAT.md relative to project root
        storage_path = _find_project_root() / "storage" / "HEARTBEAT.md"
    else:
        storage_path = Path(storage_path)

    if not storage_path.exists():
        logger.warning(f"HEARTBEAT.md not found at {storage_path}, returning empty rules")
        return []

    try:
        content = storage_path.read_text(encoding="utf-8")
        return parse_heartbeat_rules(content)
    except Exception as e:
        logger.error(f"Failed to read HEARTBEAT.md from {storage_path}: {e}")
        return []


def _find_project_root() -> Path:
    """Find project root by looking for marker files."""
    current = Path(__file__).resolve().parent
    # Go up until we find a marker (pyproject.toml, .git, etc.)
    for _ in range(10):
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    # Fallback to current working directory
    return Path.cwd()


def save_rules_to_storage(
    rules: list[HeartbeatRuleConfig],
    storage_path: str | Path | None = None,
) -> None:
    """Save heartbeat rules to storage/HEARTBEAT.md.

    Args:
        rules: List of HeartbeatRuleConfig to save
        storage_path: Path to storage directory. If None, uses default.
    """
    if storage_path is None:
        storage_path = _find_project_root() / "storage" / "HEARTBEAT.md"
    else:
        storage_path = Path(storage_path)

    storage_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Heartbeat Rules",
        "# Auto-generated by memos-graph heartbeat system",
        "",
    ]

    for rule in rules:
        lines.append(f"- name: {rule.name}")
        lines.append(f"  interval: {rule.interval}")
        if rule.quiet_hours:
            lines.append(f"  quiet_hours: {rule.quiet_hours}")

        # Format thresholds as "6h,24h,72h,168h"
        thresholds_str = ",".join(f"{t}h" for t in rule.stage_thresholds)
        lines.append(f"  stage_thresholds: {thresholds_str}")

        lines.append(f"  enabled: {str(rule.enabled).lower()}")
        if rule.use_llm_content:
            lines.append(f"  use_llm_content: true")

        lines.append("")

    storage_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Saved {len(rules)} heartbeat rules to {storage_path}")


# === Apply Rules to Scheduler ===

def apply_rules_to_scheduler(
    rules: list[HeartbeatRuleConfig],
    scheduler: Any,
) -> None:
    """Apply parsed HeartbeatRuleConfig rules to a HeartbeatScheduler instance.

    Args:
        rules: List of HeartbeatRuleConfig from parse_rules_from_storage()
        scheduler: HeartbeatScheduler instance with register() method
    """
    from memos_graph.heartbeat.scheduler import HeartbeatRule

    for config in rules:
        if not config.enabled:
            continue

        # Convert thresholds list to individual params
        stage_thresholds = config.stage_thresholds
        while len(stage_thresholds) < 4:
            stage_thresholds.append([6.0, 24.0, 72.0, 168.0][len(stage_thresholds)])

        def dummy_callback(pack_id: str, context: dict) -> None:
            logger.info(f"HB callback for {pack_id}: {context}")

        scheduler.register(
            pack_id=config.name,
            schedule=config.interval,
            callback=dummy_callback,
            stage_1_hours=stage_thresholds[0],
            stage_2_hours=stage_thresholds[1],
            stage_3_hours=stage_thresholds[2],
            stage_4_hours=stage_thresholds[3],
            use_llm_content=config.use_llm_content,
        )


# === Exports ===

__all__ = [
    "HeartbeatRuleConfig",
    "parse_heartbeat_rules",
    "load_rules_from_storage",
    "save_rules_to_storage",
    "apply_rules_to_scheduler",
]
