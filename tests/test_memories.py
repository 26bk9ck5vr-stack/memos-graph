"""Tests for memory CRUD operations — v0.1.0-docs contract 适配版。

v0.1 阶段：跳过真业务测试（需要真 PG / pgvector）。
v0.2 阶段：用 testcontainers 起 PG + pgvector，替换 sqlite+aiosqlite。

原版本（v0.1 设计错误 — 用 sqlite 测 PG schema）已废弃。
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(
    reason="v0.1.0-docs: 真业务测试需要 PG + pgvector (TEST_SPEC §1)。"
           "v0.2 实装 T1.x 后用 testcontainers 替换。占位期间跳过。"
)
@pytest.mark.asyncio
async def test_create_chunk_pg_real_db(sample_chunk_data):
    """v0.2 占位：实装 T1.x 后用真 PG 测。

    pytest.skip 标的原因：原版本用 sqlite+aiosqlite 测 PG schema (JSONB/TSVECTOR/Vector)，
    这是设计错误（TEST_SPEC §1 明确禁用 SQLite）。
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from memos_graph.db.models import Base, Chunk

    # 真实测试代码（v0.2 启用）：
    # engine = create_async_engine("postgresql+asyncpg://memos:memos@localhost:5432/memos_test")
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)
    # async_session = async_sessionmaker(engine, expire_on_commit=False)
    # async with async_session() as session:
    #     chunk = Chunk(**sample_chunk_data)
    #     session.add(chunk)
    #     await session.commit()
    #     assert chunk.id is not None
    raise NotImplementedError("T1.x 待实装")


@pytest.mark.skip(reason="v0.1.0-docs skip — see test_create_chunk_pg_real_db")
@pytest.mark.asyncio
async def test_get_chunk_pg_real_db(sample_chunk_data):
    raise NotImplementedError("T1.x 待实装")
