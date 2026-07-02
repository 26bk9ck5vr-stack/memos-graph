"""FastAPI server for memos-graph."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path
import logging

from memos_graph.config import load_config, Config
from memos_graph.db.session import create_session_factory
from memos_graph.db.models import Base
from memos_graph.api import health, memories, agents, events, promises, packs, users, graph
from memos_graph.llm.client import LLMClient

logger = logging.getLogger(__name__)


def create_app(config_path: Path | None = None, config: Config | None = None) -> FastAPI:
    """Create FastAPI application."""

    if config is None:
        config = load_config(config_path)

    # Create FastAPI app
    app = FastAPI(
        title="memos-graph",
        description="Agent state and long-term memory engine",
        version="0.1.0",
    )

    # CORS (disabled by default for localhost-only deployment)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize database
    engine, async_session = create_session_factory(
        config.database.url,
        pool_size=config.database.pool_size,
        pool_recycle=config.database.pool_recycle,
    )

    # Initialize LLM client
    llm_client = LLMClient(
        base_url=config.llm.base_url,
        api_key=config.llm.api_key,
        model=config.llm.model,
        timeout=config.llm.timeout_seconds,
    )

    # Store state in app
    app.state.config = config
    app.state.engine = engine
    app.state.async_session = async_session
    app.state.llm_client = llm_client

    @app.on_event("startup")
    async def startup():
        """Startup event."""
        logger.info("memos-graph starting...")

        # Create tables if not exist (for dev)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info(f"Database connected: {config.database.url}")
        logger.info(f"LLM client initialized: {config.llm.model}")

    @app.on_event("shutdown")
    async def shutdown():
        """Shutdown event."""
        await engine.dispose()
        await llm_client.close()
        logger.info("memos-graph shutdown complete")

    # Exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": str(exc)}},
        )

    # Register routers
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(memories.router, prefix="/api/v1", tags=["memories"])
    app.include_router(agents.router, prefix="/api/v1", tags=["agents"])
    app.include_router(events.router, prefix="/api/v1", tags=["events"])
    app.include_router(promises.router, prefix="/api/v1", tags=["promises"])
    app.include_router(packs.router, prefix="/api/v1", tags=["packs"])
    app.include_router(users.router, prefix="/api/v1", tags=["users"])
    app.include_router(graph.router, prefix="/api/v1", tags=["graph"])

    return app
