"""memos-graph database layer."""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator

Base = declarative_base()


def create_engine_and_session(database_url: str, pool_size: int = 10, pool_recycle: int = 3600):
    """Create async engine and session factory."""
    engine = create_async_engine(
        database_url,
        pool_size=pool_size,
        pool_recycle=pool_recycle,
        pool_pre_ping=True,
        echo=False,
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    return engine, async_session


async def get_session(async_session: async_sessionmaker) -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get DB session."""
    async with async_session() as session:
        yield session
