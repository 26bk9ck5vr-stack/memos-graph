"""FastAPI server for memos-graph."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
import logging

from memos_graph.config import load_config, Config
from memos_graph.db.session import create_session_factory, _async_session_factory
from memos_graph.db.models import Base
from memos_graph.api import health, memories, agents, events, promises, packs, users, graph, neo4j_graph
from memos_graph.llm.client import LLMClient
from memos_graph.heartbeat.scheduler import HeartbeatScheduler
from memos_graph.sync.hermes_sync import HermesSyncWorker

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

    # CORS — allow all origins for local/network deployment
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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

    # Serve Viewer UI at root
    @app.get("/", response_class=FileResponse)
    async def root():
        viewer_path = Path(__file__).parent / "viewer" / "index.html"
        return FileResponse(viewer_path)
    
    # Neo4j Graph Viewer
    @app.get("/neo4j-graph", response_class=FileResponse)
    async def neo4j_graph_viewer():
        viewer_path = Path(__file__).parent / "viewer" / "neo4j-graph.html"
        if not viewer_path.exists():
            raise HTTPException(status_code=404, detail="Viewer not found")
        return viewer_path
    
    # Agent Dashboard
    @app.get("/dashboard", response_class=FileResponse)
    async def agent_dashboard():
        dashboard_path = Path(__file__).parent / "viewer" / "dashboard.html"
        if not dashboard_path.exists():
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return dashboard_path
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

        # Start HeartbeatScheduler (MVP: no background scheduler yet)
        # scheduler = HeartbeatScheduler.get_instance()
        # scheduler.start()
        logger.info("Heartbeat API available (background scheduler not implemented in MVP)")
        # app.state.scheduler = scheduler
        # logger.info("HeartbeatScheduler started")

        # Start HermesSyncWorker
        hermes_worker = HermesSyncWorker()
        await hermes_worker.start()
        app.state.hermes_worker = hermes_worker
        logger.info("HermesSyncWorker started")

    @app.on_event("shutdown")
    async def shutdown():
        """Shutdown event."""
        # Stop HermesSyncWorker
        worker = getattr(app.state, "hermes_worker", None)
        if worker:
            await worker.stop()
            logger.info("HermesSyncWorker stopped")

        # Stop HeartbeatScheduler
        # Stop HeartbeatScheduler (MVP: not implemented)
        # if hasattr(app.state, 'scheduler') and app.state.scheduler:
        #     await app.state.scheduler.stop()
        #     logger.info("HeartbeatScheduler stopped")

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
    app.include_router(neo4j_graph.router, prefix="/api/v1", tags=["neo4j"])

    return app
