from __future__ import annotations

import sqlite3
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from app.core.config import AppConfig
from app.db.repositories.profiles import upsert_manual_ai_reply_settings
from app.db.schema import initialize_database
from app.services.ai_reply import (
    AiReplyDecision,
    AiReplyHook,
    build_ai_reply_payload,
    build_codex_reply_prompt,
    decide_ai_reply,
    normalize_reply_text,
    parse_keywords,
    parse_rules,
)
from app.services.manual_ai_reply_sent_comments import record_manual_ai_reply_sent_comment


def test_parse_keywords_accepts_lines_and_commas() -> None:
    assert parse_keywords("おい\n 返事して,AI ") == ["おい", "返事して", "AI"]


def test_parse_rules_accepts_individual_reactions() -> None:
    rules = parse_rules("おはよう=>おはようございます\n初見=>初見さんいらっしゃい")
    assert [(rule.keyword, rule.reaction) for rule in rules] == [
        ("おはよう", "おはようございます"),
        ("初見", "初見さんいらっしゃい"),
    ]


def test_decide_ai_reply_matches_keyword() -> None:
    config = AppConfig(ai_reply_enabled=True, ai_reply_rules="返事して=>返事する")
    decision = decide_ai_reply(config, {"content": "AI返事して"})
    assert decision.matched
    assert decision.keyword == "返事して"
    assert decision.reaction == "返事する"


def test_decide_ai_reply_matches_prefix() -> None:
    config = AppConfig(ai_reply_enabled=True, ai_reply_trigger_prefix=">AI", ai_reply_rules="")
    decision = decide_ai_reply(config, {"content": ">AI 今日どうする"})
    assert decision.matched
    assert decision.keyword == ">AI"
    assert decision.prompt == "今日どうする"
    assert decision.trigger_type == "prefix"


def test_decide_ai_reply_ignores_disabled() -> None:
    config = AppConfig(ai_reply_enabled=False, ai_reply_keywords="返事して")
    decision = decide_ai_reply(config, {"content": "返事して"})
    assert not decision.matched
    assert decision.reason == "disabled"


def test_build_ai_reply_payload_contains_monitor_friendly_fields() -> None:
    payload = build_ai_reply_payload(
        lv="lv123",
        decision=AiReplyDecision(True, keyword="返事して", reaction="返事する", session_id="s1", trigger_type="keyword"),
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
    assert payload["reaction"] == "返事する"
    assert payload["session_id"] == "s1"
    assert payload["comment"]["display_name"] == "1コメさん"
    assert payload["comment"]["content"] == "返事して"


def test_build_codex_reply_prompt_contains_session_history() -> None:
    prompt = build_codex_reply_prompt(
        lv="lv123",
        row={"content": ">AI 続き教えて"},
        display_name="太郎",
        decision=AiReplyDecision(True, keyword=">AI", prompt="続き教えて", session_id="s1", trigger_type="prefix"),
        history=[{"user": "前の話", "assistant": "前の返事"}],
    )
    assert "前の話" in prompt
    assert "前の返事" in prompt
    assert "続き教えて" in prompt


def test_normalize_reply_text_is_single_line() -> None:
    assert normalize_reply_text('"返事\\nです"') == "返事 です"


class AiReplyHookAutoSafetyTests(unittest.TestCase):
    def test_suppresses_auto_when_target_account_disabled(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)
        logs: list[tuple[str, str]] = []
        hook = AiReplyHook(
            AppConfig(ai_reply_enabled=True, ai_reply_trigger_prefix=">AI"),
            lambda level, message: logs.append((level, message)),
        )

        @contextmanager
        def fake_session():
            yield conn

        with patch("app.services.ai_reply.database_session", fake_session):
            decision = hook.maybe_submit(
                lv="lv1",
                row={"content": ">AI 返事して", "user_id": "account-1"},
                account_id="account-1",
            )

        self.assertFalse(decision.matched)
        self.assertEqual("対象アカウント側のAI自動コメント許可がOFF", decision.reason)
        self.assertTrue(any("AI返信自動送信抑止" in message for _level, message in logs))

    def test_suppresses_auto_duplicate_source(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize_database(conn)
        row = {"content": ">AI 返事して", "user_id": "account-1", "message_id": "m1", "no": "10"}
        upsert_manual_ai_reply_settings(conn, "account-1", {"manual_ai_reply_auto_comment_enabled": True})
        record_manual_ai_reply_sent_comment(conn, lv="lv1", text="返信済み", account_id="account-1", source_row=row, method="auto")
        logs: list[tuple[str, str]] = []
        hook = AiReplyHook(
            AppConfig(ai_reply_enabled=True, ai_reply_trigger_prefix=">AI"),
            lambda level, message: logs.append((level, message)),
        )

        @contextmanager
        def fake_session():
            yield conn

        with patch("app.services.ai_reply.database_session", fake_session):
            decision = hook.maybe_submit(lv="lv1", row=row, account_id="account-1")

        self.assertFalse(decision.matched)
        self.assertEqual("同じコメントへ送信済み", decision.reason)
