from __future__ import annotations

from app.core.config import AppConfig
from app.services.tag_change import decide_tag_change, parse_tag_change_rules


def test_parse_tag_change_rules() -> None:
    rules = parse_tag_change_rules("タグ変えて=>雑談,ゲーム/初見歓迎")
    assert len(rules) == 1
    assert rules[0].keyword == "タグ変えて"
    assert rules[0].tags == ("雑談", "ゲーム", "初見歓迎")


def test_decide_tag_change_matches_comment() -> None:
    config = AppConfig(tag_change_enabled=True, tag_change_rules="タグ変えて=>雑談,ゲーム")
    decision = decide_tag_change(config, {"content": "タグ変えて"})
    assert decision.matched
    assert decision.keyword == "タグ変えて"
    assert decision.tags == ("雑談", "ゲーム")


def test_decide_tag_change_ignores_disabled() -> None:
    config = AppConfig(tag_change_enabled=False, tag_change_rules="タグ変えて=>雑談")
    decision = decide_tag_change(config, {"content": "タグ変えて"})
    assert not decision.matched
    assert decision.reason == "disabled"
