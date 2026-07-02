"""Health check endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from memos_graph.db.session import get_session
import httpx

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check - always returns 200 if server is running."""
    return {"status": "healthy", "version": "0.1.0"}


@router.get("/health/ready")
async def readiness_check(
    session: AsyncSession = Depends(get_session),
):
    """Readiness check - verifies DB and LLM connectivity."""
    from memos_graph.config import load_config

    config = load_config()

    # Check database
    try:
        await session.execute("SELECT 1")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Check LLM
    llm_status = "unknown"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{config.llm.base_url}/health",
                headers={"Authorization": f"Bearer {config.llm.api_key}"},
                timeout=5.0,
            )
            if resp.status_code == 200:
                llm_status = "connected"
            else:
                llm_status = f"error: HTTP {resp.status_code}"
    except Exception as e:
        llm_status = f"error: {str(e)}"

    # Check Ollama (embedding)
    ollama_status = "unknown"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{config.embedding.base_url}/api/tags",
                timeout=5.0,
            )
            if resp.status_code == 200:
                ollama_status = "connected"
            else:
                ollama_status = f"error: HTTP {resp.status_code}"
    except Exception as e:
        ollama_status = f"error: {str(e)}"

    all_healthy = db_status == "connected" and ollama_status == "connected"

    return {
        "status": "ready" if all_healthy else "not_ready",
        "database": db_status,
        "llm": llm_status,
        "ollama": ollama_status,
    }
