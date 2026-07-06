from __future__ import annotations

from app.core.config import AppConfig
from app.services.tag_change import decide_tag_change, parse_tag_change_rules, parse_tag_operation_command


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
    assert decision.operation is not None
    assert decision.operation.add_tags == ("雑談", "ゲーム")


def test_parse_tag_operation_command_add_remove_clear() -> None:
    operation = parse_tag_operation_command("タグ: -- -プログラミング -雑談 +ゲーム +初見歓迎")
    assert operation is not None
    assert operation.clear_all
    assert operation.remove_tags == ("プログラミング", "雑談")
    assert operation.add_tags == ("ゲーム", "初見歓迎")


def test_decide_tag_change_matches_operation_command() -> None:
    config = AppConfig(tag_change_enabled=True)
    decision = decide_tag_change(config, {"content": "タグ: -雑談 +ゲーム"})
    assert decision.matched
    assert decision.keyword == "タグ:"
    assert decision.operation is not None
    assert decision.operation.remove_tags == ("雑談",)
    assert decision.operation.add_tags == ("ゲーム",)


def test_decide_tag_change_ignores_disabled() -> None:
    config = AppConfig(tag_change_enabled=False, tag_change_rules="タグ変えて=>雑談")
    decision = decide_tag_change(config, {"content": "タグ変えて"})
    assert not decision.matched
    assert decision.reason == "disabled"
