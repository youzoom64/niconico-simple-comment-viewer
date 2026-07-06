from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from app.core.config import AppConfig
from app.core.paths import APP_PATHS
from app.events.models import json_default


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
        endpoint = self.config.ai_reply_endpoint_url.strip()
        if not endpoint:
            return AiReplyDecision(False, reason="endpoint_empty")
        key = ai_reply_dedupe_key(lv, row)
        with self._lock:
            if key in self._inflight_keys:
                return AiReplyDecision(False, reason="inflight")
            self._inflight_keys.add(key)
        session_key = ai_reply_session_key(lv=lv, row=row, keyword=decision.keyword, trigger_type=decision.trigger_type)
        session_id = self._session_store.get_or_create(session_key)
        decision = AiReplyDecision(
            True,
            keyword=decision.keyword,
            reaction=decision.reaction,
            prompt=decision.prompt,
            session_id=session_id,
            trigger_type=decision.trigger_type,
        )
        payload = build_ai_reply_payload(lv=lv, row=row, decision=decision, display_name=display_name)
        thread = threading.Thread(
            target=self._post_payload,
            args=(endpoint, payload, key),
            name="ai-reply-hook",
            daemon=True,
        )
        thread.start()
        return decision

    def _post_payload(self, endpoint: str, payload: dict[str, Any], key: str) -> None:
        try:
            body = json.dumps(payload, ensure_ascii=False, default=json_default).encode("utf-8")
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "simple-comment-viewer/1.0",
            }
            api_key = self.config.ai_reply_api_key.strip()
            if api_key:
                headers["X-API-Key"] = api_key
            request = Request(endpoint, data=body, headers=headers, method="POST")
            timeout = max(1.0, float(self.config.ai_reply_timeout_seconds or 10.0))
            with urlopen(request, timeout=timeout) as response:
                status = getattr(response, "status", 200)
                response.read(512)
            self.log_sink("INFO", f"AI返信フック送信: status={status} keyword={payload.get('matched_keyword')}")
        except HTTPError as exc:
            detail = exc.read(512).decode("utf-8", errors="replace")
            self.log_sink("WARN", f"AI返信フックHTTP失敗: status={exc.code} {detail}")
        except (OSError, URLError, ValueError) as exc:
            self.log_sink("WARN", f"AI返信フック送信失敗: {type(exc).__name__}: {exc}")
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

    def get_or_create(self, key: str) -> str:
        with self._lock:
            data = self._load()
            value = str(data.get(key) or "").strip()
            if value:
                return value
            value = uuid4().hex
            data[key] = value
            self._save(data)
            return value

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(key): str(value) for key, value in data.items()}

    def _save(self, data: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
