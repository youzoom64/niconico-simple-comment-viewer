from __future__ import annotations

from app.core.config import AppConfig
from app.services.ai_reply import build_ai_reply_payload, decide_ai_reply, parse_keywords


def test_parse_keywords_accepts_lines_and_commas() -> None:
    assert parse_keywords("おい\n 返事して,AI ") == ["おい", "返事して", "AI"]


def test_decide_ai_reply_matches_keyword() -> None:
    config = AppConfig(ai_reply_enabled=True, ai_reply_keywords="返事して")
    decision = decide_ai_reply(config, {"content": "AI返事して"})
    assert decision.matched
    assert decision.keyword == "返事して"


def test_decide_ai_reply_ignores_disabled() -> None:
    config = AppConfig(ai_reply_enabled=False, ai_reply_keywords="返事して")
    decision = decide_ai_reply(config, {"content": "返事して"})
    assert not decision.matched
    assert decision.reason == "disabled"


def test_build_ai_reply_payload_contains_monitor_friendly_fields() -> None:
    payload = build_ai_reply_payload(
        lv="lv123",
        keyword="返事して",
        display_name="1コメさん",
        row={
            "kind": "anonymous_184_chat",
            "no": 7,
            "message_id": "m1",
            "user_id": "a:hash",
            "content": "返事して",
        },
    )
    assert payload["event"] == "comment_ai_reply_requested"
    assert payload["watch_url"] == "https://live.nicovideo.jp/watch/lv123"
    assert payload["comment"]["display_name"] == "1コメさん"
    assert payload["comment"]["content"] == "返事して"
