"""Test configuration and fixtures — v0.1.0-docs 适配版。

v0.1 阶段：所有依赖"实装后才存在"的功能（PG testcontainers、Ollama）
用占位 fixture 提供——跟 src/ 占位实现对齐。
v0.2 实装 TASK_BREAKDOWN 后：替换成 testcontainers 真 PG / httpx mock Ollama。
"""

from __future__ import annotations

import pytest


# ============================================================
# 通用 fixtures
# ============================================================

@pytest.fixture
def test_db_url() -> str:
    """Test database URL。

    v0.1 占位：返回 placeholder（不会真连）。
    v0.2 实装 T1 后：返回 testcontainers PG URL。
    """
    return "postgresql+asyncpg://memos:memos@localhost:5432/memos_test"


@pytest.fixture
def sample_chunk_data() -> dict:
    """Sample chunk data for testing。"""
    return {
        "agent_id": "nako",
        "scope": "private",
        "role": "user",
        "content": "我喜欢吃甜食，特别是蛋糕和冰淇淋。",
        "metadata": {"topic": "food", "sentiment": "positive"},
    }


@pytest.fixture
def sample_agent_state() -> dict:
    """Sample agent state。"""
    return {
        "agent_id": "nako",
        "pack_id": "nako",
        "stage": 2,
        "affinity": 45.0,
        "mood": 70.0,
        "energy": 60.0,
        "state": {"favorite_color": "blue"},
    }


@pytest.fixture
def sample_event_data() -> dict:
    """Sample event data。"""
    return {
        "agent_id": "nako",
        "event_type": "message",
        "actor": "user",
        "payload": {"topics": ["food"], "emotions": ["happy"]},
        "summary": "用户表达了对甜食的喜爱",
    }


@pytest.fixture
def sample_recall_request() -> dict:
    """Sample recall request — 测 RecallEngine.search 签名。"""
    return {
        "query": "用户喜欢什么食物",
        "agent_id": "nako",
        "scope": "all",
        "use_graph": True,
        "graph_decay": 0.3,
        "max_results": 10,
    }


@pytest.fixture
def sample_pack_yaml() -> dict:
    """Sample pack.yaml — 测 PackManager 签名。"""
    return {
        "id": "nako",
        "name": "野木奈子 Nako",
        "version": "0.3.0",
        "runtime": "openclaw",
        "memos_graph": {
            "required": True,
            "pack_agent_id": "nako",
        },
    }
