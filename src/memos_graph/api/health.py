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
    from sqlalchemy import text

    config = load_config()

    # Check database
    try:
        await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Check LLM (SiliconFlow doesn't have /health endpoint, test with embeddings)
    llm_status = "unknown"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{config.llm.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {config.llm.api_key}"},
                json={"model": config.llm.model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                timeout=5.0,
            )
            if resp.status_code in [200, 401]:  # 401 means API key issue but server is up
                llm_status = "connected" if resp.status_code == 200 else f"auth_error: {resp.status_code}"
            else:
                llm_status = f"error: HTTP {resp.status_code}"
    except Exception as e:
        llm_status = f"error: {str(e)}"

    # Check Embedding (SiliconFlow or Ollama)
    embedding_status = "unknown"
    try:
        async with httpx.AsyncClient() as client:
            if "siliconflow" in config.embedding.base_url:
                resp = await client.post(
                    f"{config.embedding.base_url}/embeddings",
                    headers={"Authorization": f"Bearer {config.embedding.api_key}"},
                    json={"model": config.embedding.model, "input": "test"},
                    timeout=5.0,
                )
            else:
                resp = await client.get(
                    f"{config.embedding.base_url}/api/tags",
                    timeout=5.0,
                )
            if resp.status_code in [200, 401]:
                embedding_status = "connected" if resp.status_code == 200 else f"auth_error: {resp.status_code}"
            else:
                embedding_status = f"error: HTTP {resp.status_code}"
    except Exception as e:
        embedding_status = f"error: {str(e)}"

    all_healthy = db_status == "connected" and embedding_status == "connected"

    return {
        "status": "ready" if all_healthy else "not_ready",
        "database": db_status,
        "llm": llm_status,
        "embedding": embedding_status,
    }
