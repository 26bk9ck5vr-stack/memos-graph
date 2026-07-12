"""memos-graph CLI entry point."""

import click
from pathlib import Path


@click.group()
@click.version_option(version="0.1.0")
def main():
    """memos-graph — Agent state and long-term memory engine."""
    pass


@main.command()
def init():
    """Initialize config at ~/.config/memos-graph/config.yaml."""
    from memos_graph.config import ensure_config_dir, get_default_config

    config_dir = ensure_config_dir()
    config_path = config_dir / "config.yaml"

    if config_path.exists():
        click.echo(f"Config already exists at {config_path}")
        return

    config = get_default_config()
    config_path.write_text(config)
    click.echo(f"Config created at {config_path}")


@main.command()
@click.option("--config", "-c", "config_path", type=click.Path(exists=True), help="Config file path")
def migrate(config_path: str | None):
    """Run Alembic migrations."""
    from memos_graph.db.migrations import run_migrations

    config_file = Path(config_path) if config_path else None
    run_migrations(config_file)
    click.echo("Migrations completed.")


@main.command()
@click.option("--port", "-p", default=8765, type=int, help="Port to listen on")
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind")
@click.option("--daemon", "-d", is_flag=True, help="Run as daemon")
@click.option("--config", "-c", "config_path", type=click.Path(exists=True), help="Config file path")
def serve(port: int, host: str, daemon: bool, config_path: str | None):
    """Start the FastAPI daemon."""
    import uvicorn
    from memos_graph.server import create_app

    config_file = Path(config_path) if config_path else None
    app = create_app(config_file)

    if daemon:
        import os
        import sys
        pid = os.fork()
        if pid > 0:
            click.echo(f"memos-graph started as daemon (PID: {pid})")
            sys.exit(0)
        os.setsid()
        os.umask(0)

    click.echo(f"Starting memos-graph on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


@main.command()
@click.option("--port", "-p", default=8080, type=int, help="Viewer port")
@click.option("--host", "-h", default="127.0.0.1", help="Viewer host")
def viewer(port: int, host: str):
    """Start the Viewer UI."""
    from memos_graph.viewer.server import run_viewer
    run_viewer(host=host, port=port)


@main.command()
@click.argument("pack_path", type=click.Path(exists=True))
@click.option("--migrate-sessions", is_flag=True, help="Migrate Nako session files")
def pack_install(pack_path: str, migrate_sessions: bool):
    """Install an Agent Pack."""
    import asyncio
    from memos_graph.pack.installer import install_pack

    result = asyncio.run(install_pack(pack_path, {"migrate_sessions": migrate_sessions}))
    click.echo(f"Pack installed: {result['pack_id']} v{result['version']}")


@main.command()
def pack_list():
    """List installed Agent Packs."""
    import asyncio
    from memos_graph.pack.registry import list_packs

    packs = asyncio.run(list_packs())
    if not packs:
        click.echo("No packs installed.")
        return

    click.echo("Installed packs:")
    for pack in packs:
        status = "enabled" if pack.get("enabled", True) else "disabled"
        click.echo(f"  - {pack['id']} v{pack['version']} ({status})")


@main.command()
@click.argument("pack_id")
def pack_run(pack_id: str):
    """Run an Agent Pack."""
    import asyncio
    from memos_graph.pack.runner import run_pack

    result = asyncio.run(run_pack(pack_id))
    click.echo(f"Pack {pack_id} v{result['version']} completed")
    for file_id, res in result.get("agent_results", {}).items():
        click.echo(f"  [{res['status']}] {file_id}")


@main.command()
@click.argument("pack_id")
def pack_update(pack_id: str):
    """Update an Agent Pack."""
    import asyncio
    from memos_graph.pack.installer import update_pack

    result = asyncio.run(update_pack(pack_id))
    click.echo(f"Pack {pack_id} updated: v{result['old_version']} → v{result['new_version']}")


@main.command()
@click.argument("pack_id")
@click.option("--keep-data/--no-keep-data", default=True, help="Keep pack data after uninstall")
def pack_uninstall(pack_id: str, keep_data: bool):
    """Uninstall an Agent Pack."""
    import asyncio
    from memos_graph.pack.installer import uninstall_pack

    result = asyncio.run(uninstall_pack(pack_id, keep_data=keep_data))
    click.echo(f"Pack {pack_id} uninstalled (data kept: {result['data_kept']})")


@main.command()
def install_systemd():
    """Install systemd unit file."""
    import shutil
    from pathlib import Path

    unit_content = """[Unit]
Description=memos-graph daemon
After=network.target postgresql.service

[Service]
Type=simple
User=%s
ExecStart=/usr/bin/memos-graph serve --port 8765
Restart=always

[Install]
WantedBy=multi-user.target
""" % click.get_current_context().obj.get('user', 'gato')

    systemd_dir = Path("/etc/systemd/system")
    if not systemd_dir.exists():
        click.echo("Error: /etc/systemd/system not found. Run as root.")
        return

    unit_path = systemd_dir / "memos-graph.service"
    unit_path.write_text(unit_content)
    click.echo(f"Systemd unit installed at {unit_path}")
    click.echo("Run: sudo systemctl daemon-reload && sudo systemctl enable memos-graph")


@main.command()
def doctor():
    """Run diagnostics."""
    import asyncio
    import socket
    from pathlib import Path

    click.echo("Running diagnostics...")

    # Check PostgreSQL
    click.echo("\n[PostgreSQL]")
    try:
        import asyncpg
        from memos_graph.config import load_config
        config = load_config()

        async def check_pg():
            conn = await asyncpg.connect(config.database.url)
            await conn.close()
            return True

        asyncio.run(check_pg())
        click.echo("  ✓ PostgreSQL connected")
    except Exception as e:
        click.echo(f"  ✗ PostgreSQL: {e}")

    # Check Ollama
    click.echo("\n[Ollama]")
    try:
        import httpx
        from memos_graph.config import load_config
        config = load_config()

        resp = httpx.get(f"{config.embedding.base_url}/api/tags", timeout=5)
        if resp.status_code == 200:
            click.echo("  ✓ Ollama connected")
        else:
            click.echo(f"  ✗ Ollama: HTTP {resp.status_code}")
    except Exception as e:
        click.echo(f"  ✗ Ollama: {e}")

    # Check ports
    click.echo("\n[Port availability]")
    for port in [8765, 8080]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        if result == 0:
            click.echo(f"  ✗ Port {port} is in use")
        else:
            click.echo(f"  ✓ Port {port} is available")
        sock.close()


@main.command()
def version():
    """Show version."""
    click.echo("memos-graph v0.1.0")


if __name__ == "__main__":
    main()
