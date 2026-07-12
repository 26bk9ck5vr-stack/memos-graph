"""Database session management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session

from memos_graph.config import Config

_async_session_factory = None


def create_session_factory(database_url: str, pool_size: int = 10, pool_recycle: int = 3600):
    """Create async engine and session factory."""
    global _async_session_factory
    engine = create_async_engine(
        database_url,
        pool_size=pool_size,
        pool_recycle=pool_recycle,
        pool_pre_ping=True,
        echo=False,
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    _async_session_factory = async_session
    return engine, async_session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for session. DO NOT use in application code - use _async_session_factory() instead."""
    global _async_session_factory
    if _async_session_factory is None:
        from memos_graph.config import load_config
        from memos_graph.db.session import create_session_factory as _init_factory
        _init_factory(load_config().database.url)
    async with _async_session_factory() as session:
        yield session


__all__ = ["get_session", "create_session_factory", "_async_session_factory"]
