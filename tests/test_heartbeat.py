"""Tests for heartbeat scheduler and rules."""

import asyncio
from datetime import datetime, timedelta

import pytest

from memos_graph.heartbeat.scheduler import (
    HeartbeatScheduler,
    HeartbeatRule,
    HeartbeatStage,
)
from memos_graph.heartbeat.rules import (
    HeartbeatRuleConfig,
    parse_heartbeat_rules,
    _parse_thresholds,
)


class TestHeartbeatRule:
    """Tests for HeartbeatRule staged thresholds."""

    def test_default_thresholds(self):
        """Default stage thresholds are 6h, 24h, 72h, 168h."""
        rule = HeartbeatRule("test", "1h", lambda p, c: None)
        assert rule.stage_1_hours == 6.0
        assert rule.stage_2_hours == 24.0
        assert rule.stage_3_hours == 72.0
        assert rule.stage_4_hours == 168.0

    def test_custom_thresholds(self):
        """Custom thresholds are accepted."""
        rule = HeartbeatRule(
            "test", "1h", lambda p, c: None,
            stage_1_hours=3.0,
            stage_2_hours=12.0,
            stage_3_hours=48.0,
            stage_4_hours=96.0,
        )
        assert rule.stage_1_hours == 3.0
        assert rule.stage_4_hours == 96.0

    def test_get_current_stage_never_fired(self):
        """Never-fired rule returns stage 1."""
        rule = HeartbeatRule("test", "1h", lambda p, c: None)
        rule._last_fired = None
        assert rule.get_current_stage(0) == HeartbeatStage.STAGE_1

    def test_get_current_stage_stage_2(self):
        """Hours in stage 2 range returns STAGE_2."""
        rule = HeartbeatRule("test", "1h", lambda p, c: None)
        rule._last_fired = datetime.utcnow() - timedelta(hours=10)
        assert rule.get_current_stage(10) == HeartbeatStage.STAGE_2

    def test_get_current_stage_stage_3(self):
        rule = HeartbeatRule("test", "1h", lambda p, c: None)
        rule._last_fired = datetime.utcnow() - timedelta(hours=30)
        assert rule.get_current_stage(30) == HeartbeatStage.STAGE_3

    def test_get_current_stage_stage_4(self):
        rule = HeartbeatRule("test", "1h", lambda p, c: None)
        rule._last_fired = datetime.utcnow() - timedelta(hours=100)
        assert rule.get_current_stage(100) == HeartbeatStage.STAGE_4

    def test_get_current_stage_stage_5(self):
        rule = HeartbeatRule("test", "1h", lambda p, c: None)
        rule._last_fired = datetime.utcnow() - timedelta(hours=200)
        assert rule.get_current_stage(200) == HeartbeatStage.STAGE_5

    def test_should_fire_never_fired(self):
        """Never fired → stage 1 (should fire)."""
        rule = HeartbeatRule("test", "1h", lambda p, c: None)
        rule._last_fired = None
        result = rule.should_fire(quiet_hours=False)
        assert result == HeartbeatStage.STAGE_1

    def test_should_fire_quiet_hours_blocks(self):
        """Quiet hours returns False even if rule is due."""
        rule = HeartbeatRule("test", "1h", lambda p, c: None)
        rule._last_fired = None
        result = rule.should_fire(quiet_hours=True)
        assert result is False

    def test_should_fire_disabled(self):
        """Disabled rule returns False."""
        rule = HeartbeatRule("test", "1h", lambda p, c: None, enabled=False)
        result = rule.should_fire(quiet_hours=False)
        assert result is False

    def test_should_fire_not_yet_due(self):
        """Rule not yet due returns False."""
        rule = HeartbeatRule("test", "1h", lambda p, c: None)
        rule._last_fired = datetime.utcnow()
        result = rule.should_fire(quiet_hours=False)
        assert result is False

    def test_use_llm_content_flag(self):
        """use_llm_content is stored on the rule."""
        rule = HeartbeatRule("test", "1h", lambda p, c: None, use_llm_content=True)
        assert rule.use_llm_content is True

    def test_to_dict_includes_stages(self):
        """to_dict includes stage_thresholds and use_llm_content."""
        rule = HeartbeatRule("test", "1h", lambda p, c: None, use_llm_content=True)
        d = rule.to_dict()
        assert "stage_thresholds" in d
        assert d["stage_thresholds"]["stage_1_hours"] == 6.0
        assert d["use_llm_content"] is True


class TestHeartbeatScheduler:
    """Tests for HeartbeatScheduler."""

    def test_singleton(self):
        """get_instance returns same instance."""
        s1 = HeartbeatScheduler.get_instance()
        s2 = HeartbeatScheduler.get_instance()
        assert s1 is s2

    def test_register_and_get_rules(self):
        """register() adds rule, get_rules() returns it."""
        sched = HeartbeatScheduler.get_instance()
        sched.register("pack1", "30m", lambda p, c: None)
        rules = sched.get_rules()
        assert any(r["pack_id"] == "pack1" for r in rules)

    def test_register_with_staged_params(self):
        """register() accepts stage and LLM params."""
        sched = HeartbeatScheduler.get_instance()
        sched.register(
            "pack2", "1h", lambda p, c: None,
            stage_1_hours=3.0,
            stage_2_hours=12.0,
            stage_3_hours=48.0,
            stage_4_hours=96.0,
            use_llm_content=True,
        )
        rules = sched.get_rules()
        pack2_rule = next(r for r in rules if r["pack_id"] == "pack2")
        assert pack2_rule["stage_thresholds"]["stage_1_hours"] == 3.0
        assert pack2_rule["use_llm_content"] is True

    def test_unregister(self):
        """unregister() removes rule."""
        sched = HeartbeatScheduler.get_instance()
        sched.register("pack3", "2h", lambda p, c: None)
        sched.unregister("pack3")
        assert all(r["pack_id"] != "pack3" for r in sched.get_rules())

    def test_is_quiet_hours_returns_bool(self):
        """is_quiet_hours returns a bool."""
        sched = HeartbeatScheduler.get_instance()
        result = sched.is_quiet_hours("nonexistent-agent")
        assert isinstance(result, bool)


class TestGenerateHeartbeatContent:
    """Tests for LLM content generation (using asyncio.run directly — no pytest-asyncio plugin)."""

    def test_returns_str(self):
        """generate_heartbeat_content returns a string."""
        sched = HeartbeatScheduler.get_instance()
        content = asyncio.run(sched.generate_heartbeat_content("test-agent", stage=3))
        assert isinstance(content, str)
        assert len(content) > 0

    def test_default_content_by_stage(self):
        """Default content is returned for each stage."""
        sched = HeartbeatScheduler.get_instance()
        for stage in range(1, 6):
            content = asyncio.run(sched.generate_heartbeat_content("test-agent", stage=stage))
            assert isinstance(content, str)
            assert len(content) > 0


class TestParseThresholds:
    """Tests for _parse_thresholds helper."""

    def test_with_h_suffix(self):
        assert _parse_thresholds("6h,24h,72h,168h") == [6.0, 24.0, 72.0, 168.0]

    def test_without_h_suffix(self):
        assert _parse_thresholds("6,24,72,168") == [6.0, 24.0, 72.0, 168.0]

    def test_mixed(self):
        assert _parse_thresholds("6h,24,72h,168") == [6.0, 24.0, 72.0, 168.0]


class TestParseHeartbeatRules:
    """Tests for parse_heartbeat_rules."""

    def test_minimal_rule(self):
        content = "- name: test-rule"
        rules = parse_heartbeat_rules(content)
        assert len(rules) == 1
        assert rules[0].name == "test-rule"
        assert rules[0].interval == "24h"  # default
        assert rules[0].enabled is True

    def test_full_rule(self):
        content = """
- name: daily-checkin
  interval: 24h
  quiet_hours: 23:00-08:00
  stage_thresholds: 6h,24h,72h,168h
  enabled: true
"""
        rules = parse_heartbeat_rules(content)
        assert len(rules) == 1
        assert rules[0].name == "daily-checkin"
        assert rules[0].interval == "24h"
        assert rules[0].quiet_hours == "23:00-08:00"
        assert rules[0].stage_thresholds == [6.0, 24.0, 72.0, 168.0]
        assert rules[0].enabled is True

    def test_multiple_rules(self):
        content = """
- name: rule1
  interval: 12h

- name: rule2
  interval: 48h
  enabled: false
"""
        rules = parse_heartbeat_rules(content)
        assert len(rules) == 2
        assert rules[0].name == "rule1"
        assert rules[1].name == "rule2"
        assert rules[1].enabled is False

    def test_use_llm_content_flag(self):
        content = """
- name: llm-rule
  interval: 6h
  use_llm_content: true
"""
        rules = parse_heartbeat_rules(content)
        assert len(rules) == 1
        assert rules[0].use_llm_content is True

    def test_skips_comments_and_blank_lines(self):
        content = """
# comment
- name: rule1
  interval: 1h

  # indented comment

- name: rule2
"""
        rules = parse_heartbeat_rules(content)
        assert len(rules) == 2
