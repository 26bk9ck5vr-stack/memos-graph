"""Alembic migrations wrapper."""

import subprocess
from pathlib import Path


def run_migrations(config_path: Path | None = None):
    """Run Alembic migrations."""
    import asyncio
    from memos_graph.config import load_config, ensure_data_dir

    if config_path:
        from memos_graph.config import load_config as load_config_from_path
        config = load_config_from_path(config_path)
    else:
        config = load_config()

    # Ensure data directory exists
    ensure_data_dir()

    # Run alembic upgrade
    alembic_dir = Path(__file__).parent.parent.parent / "alembic"
    alembic_ini = alembic_dir.parent / "alembic.ini"

    # Set DATABASE_URL environment for alembic
    import os
    os.environ["DATABASE_URL"] = config.database.url

    subprocess.run(
        ["alembic", "-c", str(alembic_ini), "upgrade", "head"],
        check=True,
    )
