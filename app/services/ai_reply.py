from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from app.core.config import AppConfig
from app.core.paths import APP_PATHS
from app.services.codex_exec_runner import run_codex_exec
from app.services.comment_post import post_comment


LogSink = Callable[[str, str], None]


@dataclass(frozen=True)
class AiReplyDecision:
    matched: bool
    keyword: str = ""
    reaction: str = ""
    prompt: str = ""
    session_id: str = ""
    trigger_type: str = ""
    reason: str = ""


@dataclass(frozen=True)
class AiReplyRule:
    keyword: str
    reaction: str = ""


class AiReplyHook:
    def __init__(self, config: AppConfig, log_sink: LogSink) -> None:
        self.config = config
        self.log_sink = log_sink
        self._inflight_keys: set[str] = set()
        self._lock = threading.Lock()
        self._session_store = AiReplySessionStore(APP_PATHS.ai_reply_sessions)

    def update_config(self, config: AppConfig) -> None:
        self.config = config

    def maybe_submit(self, *, lv: str, row: dict[str, Any], display_name: str = "") -> AiReplyDecision:
        decision = decide_ai_reply(self.config, row)
        if not decision.matched:
            return decision
        key = ai_reply_dedupe_key(lv, row)
        with self._lock:
            if key in self._inflight_keys:
                return AiReplyDecision(False, reason="inflight")
            self._inflight_keys.add(key)
        session_key = ai_reply_session_key(lv=lv, row=row, keyword=decision.keyword, trigger_type=decision.trigger_type)
        session = self._session_store.get_or_create(session_key)
        decision = AiReplyDecision(
            True,
            keyword=decision.keyword,
            reaction=decision.reaction,
            prompt=decision.prompt,
            session_id=session.session_id,
            trigger_type=decision.trigger_type,
        )
        thread = threading.Thread(
            target=self._run_codex_and_post,
            args=(lv, row, display_name, decision, session_key, session, key),
            name="ai-reply-hook",
            daemon=True,
        )
        thread.start()
        return decision

    def _run_codex_and_post(
        self,
        lv: str,
        row: dict[str, Any],
        display_name: str,
        decision: AiReplyDecision,
        session_key: str,
        session: "AiReplySession",
        key: str,
    ) -> None:
        try:
            prompt = build_codex_reply_prompt(
                lv=lv,
                row=row,
                display_name=display_name,
                decision=decision,
                history=session.history,
            )
            result = run_codex_exec(
                prompt,
                timeout_seconds=int(self.config.ai_reply_timeout_seconds or 300),
                model=self.config.ai_reply_model,
                effort=self.config.ai_reply_effort,
            )
            if not result.ok:
                self.log_sink("WARN", f"AI返信Codex失敗: code={result.returncode} {result.stderr[-300:]}")
                return
            reply = normalize_reply_text(result.text)
            if not reply:
                self.log_sink("WARN", "AI返信Codex空応答")
                return
            post_comment(lv, reply, is_anonymous=True)
            self._session_store.append_turn(
                session_key,
                user_text=str(row.get("content") or row.get("text") or ""),
                assistant_text=reply,
                session_id=session.session_id,
            )
            self.log_sink("INFO", f"AI返信投稿完了: session={session.session_id} keyword={decision.keyword} text={reply[:40]}")
        except Exception as exc:
            self.log_sink("WARN", f"AI返信失敗: {type(exc).__name__}: {exc}")
        finally:
            with self._lock:
                self._inflight_keys.discard(key)


def decide_ai_reply(config: AppConfig, row: dict[str, Any]) -> AiReplyDecision:
    if not config.ai_reply_enabled:
        return AiReplyDecision(False, reason="disabled")
    text = str(row.get("content") or row.get("text") or "").strip()
    if not text:
        return AiReplyDecision(False, reason="empty_comment")
    trigger_prefix = str(config.ai_reply_trigger_prefix or "").strip()
    if trigger_prefix and text.startswith(trigger_prefix):
        prompt = text[len(trigger_prefix) :].strip()
        return AiReplyDecision(True, keyword=trigger_prefix, prompt=prompt, trigger_type="prefix")
    for rule in parse_rules(config.ai_reply_rules or config.ai_reply_keywords):
        if rule.keyword in text:
            return AiReplyDecision(True, keyword=rule.keyword, reaction=rule.reaction, prompt=text, trigger_type="keyword")
    return AiReplyDecision(False, reason="no_keyword")


def parse_keywords(value: str) -> list[str]:
    return [rule.keyword for rule in parse_rules(value)]


def parse_rules(value: str) -> list[AiReplyRule]:
    result: list[str] = []
    rules: list[AiReplyRule] = []
    seen: set[str] = set()
    for raw in str(value or "").replace(",", "\n").splitlines():
        line = raw.strip()
        if "=>" in line:
            keyword, reaction = line.split("=>", 1)
        elif "\t" in line:
            keyword, reaction = line.split("\t", 1)
        else:
            keyword, reaction = line, ""
        keyword = keyword.strip()
        reaction = reaction.strip()
        if keyword and keyword not in seen:
            seen.add(keyword)
            result.append(keyword)
            rules.append(AiReplyRule(keyword=keyword, reaction=reaction))
    return rules


def build_ai_reply_payload(
    *,
    lv: str,
    row: dict[str, Any],
    decision: AiReplyDecision | None = None,
    keyword: str = "",
    display_name: str = "",
) -> dict[str, Any]:
    decision = decision or AiReplyDecision(True, keyword=keyword)
    return {
        "source": "simple_comment_viewer",
        "event": "comment_ai_reply_requested",
        "lv": lv,
        "watch_url": f"https://live.nicovideo.jp/watch/{lv}" if lv else "",
        "matched_keyword": decision.keyword,
        "trigger_type": decision.trigger_type,
        "reaction": decision.reaction,
        "prompt": decision.prompt,
        "session_id": decision.session_id,
        "comment": {
            "kind": row.get("kind") or "",
            "no": row.get("no") or "",
            "message_id": row.get("message_id") or "",
            "user_id": row.get("user_id") or "",
            "raw_user_id": row.get("raw_user_id") or "",
            "hashed_user_id": row.get("hashed_user_id") or "",
            "display_name": display_name,
            "content": row.get("content") or row.get("text") or "",
            "vpos": row.get("vpos") or "",
            "at": row.get("at") or "",
        },
        "raw_row": row,
    }


def ai_reply_dedupe_key(lv: str, row: dict[str, Any]) -> str:
    event_id = str(row.get("message_id") or row.get("no") or row.get("vpos") or row.get("content") or "")
    user_id = str(row.get("user_id") or row.get("raw_user_id") or row.get("hashed_user_id") or "")
    return f"{lv}:{event_id}:{user_id}"


def ai_reply_session_key(*, lv: str, row: dict[str, Any], keyword: str, trigger_type: str) -> str:
    user_id = str(row.get("user_id") or row.get("raw_user_id") or row.get("hashed_user_id") or "unknown")
    return f"{lv}:{user_id}:{trigger_type}:{keyword}"


class AiReplySessionStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()

    def get_or_create(self, key: str) -> "AiReplySession":
        with self._lock:
            data = self._load()
            raw = data.get(key)
            if isinstance(raw, dict):
                session_id = str(raw.get("session_id") or "").strip() or uuid4().hex
                history = raw.get("history") if isinstance(raw.get("history"), list) else []
                return AiReplySession(session_id=session_id, history=[item for item in history if isinstance(item, dict)])
            if str(raw or "").strip():
                return AiReplySession(session_id=str(raw).strip(), history=[])
            session = AiReplySession(session_id=uuid4().hex, history=[])
            data[key] = {"session_id": session.session_id, "history": []}
            self._save(data)
            return session

    def append_turn(self, key: str, *, user_text: str, assistant_text: str, session_id: str) -> None:
        with self._lock:
            data = self._load()
            raw = data.get(key) if isinstance(data.get(key), dict) else {}
            history = raw.get("history") if isinstance(raw.get("history"), list) else []
            history.append({"user": user_text, "assistant": assistant_text})
            data[key] = {"session_id": session_id, "history": history[-20:]}
            self._save(data)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(key): value for key, value in data.items()}

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@dataclass(frozen=True)
class AiReplySession:
    session_id: str
    history: list[dict[str, Any]]


def build_codex_reply_prompt(
    *,
    lv: str,
    row: dict[str, Any],
    display_name: str,
    decision: AiReplyDecision,
    history: list[dict[str, Any]],
) -> str:
    content = str(row.get("content") or row.get("text") or "")
    instruction = decision.reaction or decision.prompt or content
    history_text = "\n".join(
        f"視聴者: {item.get('user','')}\n返信: {item.get('assistant','')}"
        for item in history[-10:]
        if isinstance(item, dict)
    )
    return f"""ニコ生コメントへの短い返信を1つだけ作れ。
条件:
- 返答本文だけを出力する
- 80文字以内
- 改行しない
- 説明や引用符を付けない
- 荒い口調や煽りは避ける

放送ID: {lv}
相手名: {display_name or '視聴者'}
トリガー: {decision.trigger_type}
キーワード: {decision.keyword}
反応指示: {instruction}

過去の同一セッション会話:
{history_text or 'なし'}

今回のコメント:
{content}
"""


def normalize_reply_text(text: str) -> str:
    value = str(text or "").strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1].strip()
    value = value.replace("\\r", " ").replace("\\n", " ").replace("\r", " ").replace("\n", " ")
    return value[:180]
