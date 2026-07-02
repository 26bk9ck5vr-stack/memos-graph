"""Contract tests for v0.1.0-docs API surface.

These tests assert **interface contracts** (public class exists, method signatures correct,
exceptions raised correctly). They do NOT test business logic — that's the
implementation tests (T5.x, T6.x, T11.x, T12.x in TASK_BREAKDOWN.md).

v0.1.0-docs 阶段：所有 contract tests PASS（验证接口形状对）。
v0.2 实装后：删 `@pytest.mark.xfail(raises=NotImplementedByDesignError)` 标记，
tests 自动升级为真业务测试。
"""

from __future__ import annotations

import inspect
import pytest
import asyncio


# ============================================================
# 1. recall/ 契约（对应 TEST_SPEC §2 全部）
# ============================================================

class TestRecallContract:
    """Recall engine public API 契约。"""

    def test_module_imports(self):
        """recall/__init__.py 暴露公开类。"""
        from memos_graph.recall import (
            RecallEngine, RecallRequest, RecallHit, RecallResult,
            RecallError, NotImplementedByDesignError,
        )
        assert RecallEngine is not None
        assert RecallRequest is not None

    def test_recall_engine_class_exists(self):
        from memos_graph.recall import RecallEngine
        assert inspect.isclass(RecallEngine)

    def test_recall_engine_constructor(self):
        from memos_graph.recall import RecallEngine
        # 默认构造
        e = RecallEngine()
        assert e is not None
        # 带参数构造
        e2 = RecallEngine(db_url="postgresql://x", embedding_service=None)
        assert e2 is not None

    def test_recall_engine_has_search_method(self):
        from memos_graph.recall import RecallEngine
        assert hasattr(RecallEngine, "search")
        assert inspect.iscoroutinefunction(RecallEngine.search)

    def test_recall_engine_has_expand_graph_method(self):
        from memos_graph.recall import RecallEngine
        assert hasattr(RecallEngine, "expand_graph")
        assert inspect.iscoroutinefunction(RecallEngine.expand_graph)

    def test_recall_engine_has_fts_search_method(self):
        from memos_graph.recall import RecallEngine
        assert hasattr(RecallEngine, "fts_search")
        assert inspect.iscoroutinefunction(RecallEngine.fts_search)

    def test_recall_engine_has_vector_search_method(self):
        from memos_graph.recall import RecallEngine
        assert hasattr(RecallEngine, "vector_search")
        assert inspect.iscoroutinefunction(RecallEngine.vector_search)

    def test_recall_request_dataclass(self):
        from memos_graph.recall import RecallRequest
        r = RecallRequest(query="hi", agent_id="nako")
        assert r.query == "hi"
        assert r.agent_id == "nako"
        assert r.scope == "all"
        assert r.use_graph is True
        assert r.graph_decay == 0.3
        assert r.max_results == 10

    @pytest.mark.xfail(raises=Exception, reason="v0.1 占位 — T5.4a/4b 实装")
    @pytest.mark.asyncio
    async def test_search_raises_not_implemented(self, sample_recall_request):
        """v0.1 阶段：search 应 raise NotImplementedByDesignError。
        v0.2 实装后此 test 应改为 xfail 删掉 / 或改 assert 真业务结果。
        """
        from memos_graph.recall import RecallEngine, RecallRequest, NotImplementedByDesignError
        engine = RecallEngine()
        req = RecallRequest(**sample_recall_request)
        with pytest.raises(NotImplementedByDesignError):
            await engine.search(req)

    @pytest.mark.xfail(raises=Exception, reason="v0.1 占位 — T5.3 实装")
    @pytest.mark.asyncio
    async def test_expand_graph_raises_not_implemented(self):
        from memos_graph.recall import RecallEngine, NotImplementedByDesignError
        engine = RecallEngine()
        with pytest.raises(NotImplementedByDesignError):
            await engine.expand_graph(chunk_id=1, decay=0.3)


# ============================================================
# 2. embedding/ 契约（对应 TEST_SPEC §3）
# ============================================================

class TestEmbeddingContract:
    """Embedding service public API 契约。"""

    def test_module_imports(self):
        from memos_graph.embedding import (
            Embedder, EmbeddingService, EmbeddingError, NotImplementedByDesignError,
        )
        assert Embedder is not None
        assert EmbeddingService is not None

    def test_embedder_is_abstract(self):
        from memos_graph.embedding import Embedder
        assert inspect.isabstract(Embedder)

    def test_embedder_has_embed_method(self):
        from memos_graph.embedding import Embedder
        assert hasattr(Embedder, "embed")
        assert inspect.iscoroutinefunction(Embedder.embed)

    def test_embedder_has_embed_batch_method(self):
        from memos_graph.embedding import Embedder
        assert hasattr(Embedder, "embed_batch")
        assert inspect.iscoroutinefunction(Embedder.embed_batch)

    def test_embedder_has_dimension_property(self):
        from memos_graph.embedding import Embedder
        assert "dimension" in dir(Embedder)

    def test_embedding_service_constructor(self):
        from memos_graph.embedding import EmbeddingService
        s = EmbeddingService()
        assert s is not None
        s2 = EmbeddingService(
            provider="ollama",
            model="mxbai-embed-large",
            base_url="http://x:11434",
            cache_db="/tmp/cache.db",
        )
        assert s2 is not None

    def test_embedding_service_dimension(self):
        """v0.1 实装：model → dimension 映射已可用（不需要等 T6.2）。"""
        from memos_graph.embedding import EmbeddingService
        s1 = EmbeddingService(model="nomic-embed-text")
        assert s1.dimension == 768
        s2 = EmbeddingService(model="mxbai-embed-large")
        assert s2.dimension == 1024

    @pytest.mark.xfail(raises=Exception, reason="v0.1 占位 — T6.2 实装")
    @pytest.mark.asyncio
    async def test_embed_raises_not_implemented(self):
        from memos_graph.embedding import EmbeddingService, NotImplementedByDesignError
        s = EmbeddingService()
        with pytest.raises(NotImplementedByDesignError):
            await s.embed("hello")

    @pytest.mark.xfail(raises=Exception, reason="v0.1 占位 — T6.3 实装")
    @pytest.mark.asyncio
    async def test_cached_embed_raises_not_implemented(self):
        from memos_graph.embedding import EmbeddingService, NotImplementedByDesignError
        s = EmbeddingService()
        with pytest.raises(NotImplementedByDesignError):
            await s.cached_embed("hello")


# ============================================================
# 3. pack/ 契约（对应 TEST_SPEC §5）
# ============================================================

class TestPackContract:
    """Pack manager public API 契约。"""

    def test_module_imports(self):
        from memos_graph.pack import (
            PackManager, PackError, NotImplementedByDesignError,
        )
        assert PackManager is not None

    def test_pack_manager_constructor(self):
        from memos_graph.pack import PackManager
        m = PackManager()
        assert m is not None

    def test_pack_manager_has_all_methods(self):
        from memos_graph.pack import PackManager
        # 8 个公开方法必须存在
        for method in [
            "install", "update", "uninstall", "list", "info", "run", "stop", "verify",
        ]:
            assert hasattr(PackManager, method), f"PackManager 缺 {method} 方法"

    def test_pack_manager_methods_are_async(self):
        from memos_graph.pack import PackManager
        # 这些应该是 async
        for method in ["install", "update", "uninstall", "list", "info", "run", "stop", "verify"]:
            m = getattr(PackManager, method)
            assert inspect.iscoroutinefunction(m), f"PackManager.{method} 应该是 async"

    def test_pack_manager_packs_dir_default(self):
        from memos_graph.pack import PackManager
        m = PackManager()
        # 默认 packs 目录是 ~/.local/share/memos-graph/packs
        assert "memos-graph/packs" in str(m._packs_dir)

    @pytest.mark.xfail(raises=Exception, reason="v0.1 占位 — T11.2 实装")
    @pytest.mark.asyncio
    async def test_install_raises_not_implemented(self, sample_pack_yaml):
        from memos_graph.pack import PackManager, NotImplementedByDesignError
        m = PackManager()
        with pytest.raises(NotImplementedByDesignError):
            await m.install(source="./nako", options={})

    @pytest.mark.xfail(raises=Exception, reason="v0.1 占位 — T11.2 实装")
    @pytest.mark.asyncio
    async def test_update_raises_not_implemented(self):
        from memos_graph.pack import PackManager, NotImplementedByDesignError
        m = PackManager()
        with pytest.raises(NotImplementedByDesignError):
            await m.update(pack_id="nako")

    @pytest.mark.xfail(raises=Exception, reason="v0.1 占位 — T11.4 实装")
    @pytest.mark.asyncio
    async def test_list_raises_not_implemented(self):
        from memos_graph.pack import PackManager, NotImplementedByDesignError
        m = PackManager()
        with pytest.raises(NotImplementedByDesignError):
            await m.list()


# ============================================================
# 4. heartbeat/ 契约（对应 TEST_SPEC §4）
# ============================================================

class TestHeartbeatContract:
    """Heartbeat scheduler public API 契约。"""

    def test_module_imports(self):
        from memos_graph.heartbeat import (
            HeartbeatScheduler, HeartbeatError, NotImplementedByDesignError,
        )
        assert HeartbeatScheduler is not None

    def test_scheduler_constructor(self):
        from memos_graph.heartbeat import HeartbeatScheduler
        s = HeartbeatScheduler()
        assert s is not None
        s2 = HeartbeatScheduler(schedule_seconds=600, quiet_hours="22:00-06:00")
        assert s2._schedule_seconds == 600
        assert s2._quiet_hours == "22:00-06:00"

    def test_scheduler_has_methods(self):
        from memos_graph.heartbeat import HeartbeatScheduler
        for method in ["start", "stop", "tick", "should_heartbeat", "dispatch"]:
            assert hasattr(HeartbeatScheduler, method), f"缺 {method}"

    def test_scheduler_start_stop_async(self):
        from memos_graph.heartbeat import HeartbeatScheduler
        assert inspect.iscoroutinefunction(HeartbeatScheduler.start)
        assert inspect.iscoroutinefunction(HeartbeatScheduler.stop)
        assert inspect.iscoroutinefunction(HeartbeatScheduler.tick)
        assert inspect.iscoroutinefunction(HeartbeatScheduler.dispatch)

    def test_scheduler_should_heartbeat_sync(self):
        """should_heartbeat 是 sync（高频调用，避免 async 开销）。"""
        from memos_graph.heartbeat import HeartbeatScheduler
        assert not inspect.iscoroutinefunction(HeartbeatScheduler.should_heartbeat)

    @pytest.mark.xfail(raises=Exception, reason="v0.1 占位 — T12.2 实装")
    @pytest.mark.asyncio
    async def test_start_raises_not_implemented(self):
        from memos_graph.heartbeat import HeartbeatScheduler, NotImplementedByDesignError
        s = HeartbeatScheduler()
        with pytest.raises(NotImplementedByDesignError):
            await s.start()

    @pytest.mark.xfail(raises=Exception, reason="v0.1 占位 — T12.2 实装")
    @pytest.mark.asyncio
    async def test_tick_raises_not_implemented(self):
        from memos_graph.heartbeat import HeartbeatScheduler, NotImplementedByDesignError
        s = HeartbeatScheduler()
        with pytest.raises(NotImplementedByDesignError):
            await s.tick()


# ============================================================
# 5. context_engine/ 契约
# ============================================================

class TestContextEngineContract:
    """Context injector public API 契约。"""

    def test_module_imports(self):
        from memos_graph.context_engine import (
            ContextInjector, ContextEngineError, NotImplementedByDesignError,
        )
        assert ContextInjector is not None

    def test_injector_constructor(self):
        from memos_graph.context_engine import ContextInjector
        c = ContextInjector()
        assert c is not None

    def test_injector_has_methods(self):
        from memos_graph.context_engine import ContextInjector
        assert hasattr(ContextInjector, "build_system_prompt")
        assert hasattr(ContextInjector, "inject")
        assert inspect.iscoroutinefunction(ContextInjector.build_system_prompt)
        assert inspect.iscoroutinefunction(ContextInjector.inject)

    @pytest.mark.xfail(raises=Exception, reason="v0.1 占位 — context_engine 实装")
    @pytest.mark.asyncio
    async def test_build_system_prompt_raises(self):
        from memos_graph.context_engine import ContextInjector, NotImplementedByDesignError
        c = ContextInjector()
        with pytest.raises(NotImplementedByDesignError):
            await c.build_system_prompt("nako")


# ============================================================
# 6. 跨模块契约（异常类型 / 异常继承）
# ============================================================

class TestCrossModuleContract:
    """模块间共享契约。"""

    def test_all_not_implemented_errors_inherit(self):
        """所有 NotImplementedByDesignError 应该能独立 raise + 互不干扰。"""
        from memos_graph.recall import NotImplementedByDesignError as R
        from memos_graph.embedding import NotImplementedByDesignError as E
        from memos_graph.pack import NotImplementedByDesignError as P
        from memos_graph.heartbeat import NotImplementedByDesignError as H
        from memos_graph.context_engine import NotImplementedByDesignError as C
        # 各自可独立 raise
        with pytest.raises(R):
            raise R("test")
        with pytest.raises(E):
            raise E("test")
        with pytest.raises(P):
            raise P("test")
        with pytest.raises(H):
            raise H("test")
        with pytest.raises(C):
            raise C("test")

    def test_all_modules_have_not_implemented_marker(self):
        """v0.1 占位实现一致性：每个核心 module 都有 NotImplementedByDesignError。"""
        from memos_graph import recall, embedding, pack, heartbeat, context_engine
        for mod in [recall, embedding, pack, heartbeat, context_engine]:
            assert hasattr(mod, "NotImplementedByDesignError"), (
                f"{mod.__name__} 缺 NotImplementedByDesignError 标记"
            )

    def test_recall_request_default_values(self):
        """RecallRequest 默认值稳定（v0.1 → v0.2 不允许改）。"""
        from memos_graph.recall import RecallRequest
        r = RecallRequest(query="x", agent_id="y")
        # 锁定默认
        assert r.scope == "all"
        assert r.use_graph is True
        assert r.graph_decay == 0.3
        assert r.max_results == 10


# ============================================================
# 7. fixtures 可用性（确保 conftest.py 的 fixture 真能跑）
# ============================================================

class TestFixturesWork:
    def test_sample_chunk_data(self, sample_chunk_data):
        assert sample_chunk_data["agent_id"] == "nako"
        assert "甜食" in sample_chunk_data["content"]

    def test_sample_agent_state(self, sample_agent_state):
        assert sample_agent_state["stage"] == 2
        assert sample_agent_state["affinity"] == 45.0

    def test_sample_event_data(self, sample_event_data):
        assert sample_event_data["event_type"] == "message"

    def test_sample_recall_request(self, sample_recall_request):
        assert sample_recall_request["query"] == "用户喜欢什么食物"
        assert sample_recall_request["agent_id"] == "nako"

    def test_sample_pack_yaml(self, sample_pack_yaml):
        assert sample_pack_yaml["id"] == "nako"
        assert sample_pack_yaml["runtime"] == "openclaw"
