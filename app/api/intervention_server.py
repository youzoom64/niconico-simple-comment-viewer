from __future__ import annotations

import argparse
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib import request
from urllib.parse import parse_qs, urlparse

from app.api.personal_settings import apply_personal_setting_by_context, build_personal_setting_context
from app.core.paths import APP_PATHS
from app.db.connection import database_session
from app.db.repositories.profiles import get_live_user_profile, list_live_user_profiles, upsert_live_user_profile
from app.db.schema import initialize_database
from app.profiles.listener_identity import resolve_listener_identity
from app.settings.store import JsonSettingsStore


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8793
DEFAULT_MONITOR_URL = "http://127.0.0.1:8794"


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="simple comment viewer local intervention API")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), InterventionHandler)
    print(f"simple comment viewer intervention API listening on http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


class InterventionHandler(BaseHTTPRequestHandler):
    server_version = "SimpleCommentViewerInterventionAPI/0.1"

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self.write_json(
                    {
                        "ok": True,
                        "service": "niconico-simple-comment-viewer",
                        "db": str(APP_PATHS.database),
                        "auth_enabled": bool(load_api_key()),
                    }
                )
                return
            if parsed.path == "/api/comments/latest":
                self.require_local_and_auth()
                self.handle_latest_comments(parse_qs(parsed.query))
                return
            if parsed.path == "/api/comments/by-no":
                self.require_local_and_auth()
                query = parse_qs(parsed.query)
                result = resolve_comment_by_no(first_query_value(query, "no"), first_query_value(query, "lv"))
                self.write_json({"ok": True, "result": result})
                return
            if parsed.path == "/api/personal-settings/by-comment-no":
                self.require_local_and_auth()
                query = parse_qs(parsed.query)
                resolved = resolve_comment_by_no(first_query_value(query, "no"), first_query_value(query, "lv"))
                result = build_personal_setting_context(
                    resolved,
                    comment_limit=parse_limit(first_query_value(query, "limit"), default=120, max_value=1000),
                    history_lv=first_query_value(query, "history_lv"),
                )
                self.write_json({"ok": True, "result": result})
                return
            if parsed.path == "/api/live-user-profiles":
                self.require_local_and_auth()
                self.handle_get_live_user_profiles(parse_qs(parsed.query))
                return
            self.write_error_json(HTTPStatus.NOT_FOUND, "not_found")
        except RequestAborted:
            return
        except ValueError as exc:
            self.write_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path == "/api/comments/resolve":
                self.require_local_and_auth()
                payload = self.read_json_body()
                result = resolve_comment_by_no(payload.get("no"), payload.get("lv"))
                self.write_json({"ok": True, "result": result})
                return
            if parsed.path == "/api/personal-settings/resolve-by-comment-no":
                self.require_local_and_auth()
                payload = self.read_json_body()
                resolved = resolve_comment_by_no(payload.get("no"), payload.get("lv"))
                result = build_personal_setting_context(
                    resolved,
                    comment_limit=parse_limit(payload.get("limit"), default=120, max_value=1000),
                    history_lv=normalize_text(payload.get("history_lv")),
                )
                self.write_json({"ok": True, "result": result})
                return
            if parsed.path == "/api/personal-settings/apply-by-comment-no":
                self.require_local_and_auth()
                payload = self.read_json_body()
                resolved = resolve_comment_by_no(payload.get("no"), payload.get("lv"))
                result = apply_personal_setting_by_context(resolved, payload)
                self.write_json({"ok": True, "result": result})
                return
            if parsed.path == "/api/monitor/special-users/register-by-comment-no":
                self.require_local_and_auth()
                payload = self.read_json_body()
                result = register_monitor_special_user_by_comment_no(payload)
                self.write_json({"ok": True, "result": result})
                return
            if parsed.path in {"/api/live-user-profiles", "/api/db/live-user-profiles/upsert"}:
                self.require_local_and_auth()
                payload = self.read_json_body()
                result = save_live_user_profile(payload)
                self.write_json({"ok": True, "profile": result})
                return
            self.write_error_json(HTTPStatus.NOT_FOUND, "not_found")
        except RequestAborted:
            return
        except ValueError as exc:
            self.write_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def handle_latest_comments(self, query: dict[str, list[str]]) -> None:
        lv = first_query_value(query, "lv")
        limit = parse_limit(first_query_value(query, "limit"), default=20, max_value=200)
        with database_session() as conn:
            initialize_database(conn)
            if lv:
                rows = conn.execute(
                    """
                    SELECT * FROM normalized_events
                    WHERE lv = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (lv, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM normalized_events
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        self.write_json({"ok": True, "comments": [comment_row_to_dict(row) for row in rows]})

    def handle_get_live_user_profiles(self, query: dict[str, list[str]]) -> None:
        user_id = first_query_value(query, "user_id")
        with database_session() as conn:
            initialize_database(conn)
            if user_id:
                row = get_live_user_profile(conn, user_id)
                self.write_json({"ok": True, "profile": dict(row) if row else None})
                return
            rows = list_live_user_profiles(conn)
            self.write_json({"ok": True, "profiles": [dict(row) for row in rows]})

    def require_local_and_auth(self) -> None:
        host = str(self.client_address[0])
        if host not in {"127.0.0.1", "::1", "localhost"}:
            self.write_error_json(HTTPStatus.FORBIDDEN, "local_only")
            raise RequestAborted
        expected = load_api_key()
        if expected and self.headers.get("X-API-Key", "") != expected:
            self.write_error_json(HTTPStatus.UNAUTHORIZED, "invalid_api_key")
            raise RequestAborted

    def read_json_body(self) -> dict[str, Any]:
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            self.write_error_json(HTTPStatus.BAD_REQUEST, "invalid_content_length")
            raise RequestAborted from exc
        if size <= 0:
            return {}
        raw = self.rfile.read(size)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            self.write_error_json(HTTPStatus.BAD_REQUEST, "invalid_json")
            raise RequestAborted from exc
        if not isinstance(data, dict):
            self.write_error_json(HTTPStatus.BAD_REQUEST, "json_object_required")
            raise RequestAborted
        return data

    def write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def write_error_json(self, status: HTTPStatus, error: str) -> None:
        self.write_json({"ok": False, "error": error}, status)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")


class RequestAborted(Exception):
    pass


def load_api_key() -> str:
    value = os.environ.get("NICONICO_COMMENT_VIEWER_API_KEY", "").strip()
    if value:
        return value
    data = JsonSettingsStore().load_dict()
    return str(data.get("intervention_api_key") or data.get("local_api_key") or "").strip()


def first_query_value(query: dict[str, list[str]], name: str) -> str:
    values = query.get(name) or []
    return str(values[0]).strip() if values else ""


def parse_limit(value: Any, *, default: int, max_value: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(1, min(number, max_value))


def normalize_text(value: Any) -> str:
    return str(value or "").strip()


def comment_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "lv": normalize_text(row["lv"]),
        "event_kind": normalize_text(row["event_kind"]),
        "no": normalize_text(row["no"]),
        "user_id": normalize_text(row["user_id"]),
        "raw_user_id": normalize_text(row["raw_user_id"]),
        "hashed_user_id": normalize_text(row["hashed_user_id"]),
        "account_status": normalize_text(row["account_status"]),
        "commands": normalize_text(row["commands"]),
        "content": normalize_text(row["content"]),
        "display_text": normalize_text(row["display_text"] or row["content"]),
        "speech_text": normalize_text(row["speech_text"] or row["content"]),
        "created_at": normalize_text(row["created_at"]),
    }


def resolve_comment_by_no(no: Any, lv: Any = "") -> dict[str, Any]:
    no_text = normalize_text(no)
    lv_text = normalize_text(lv)
    if not no_text:
        raise ValueError("no is required")
    with database_session() as conn:
        initialize_database(conn)
        if lv_text:
            row = conn.execute(
                """
                SELECT * FROM normalized_events
                WHERE lv = ? AND no = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (lv_text, no_text),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT * FROM normalized_events
                WHERE no = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (no_text,),
            ).fetchone()
        if row is None:
            raise ValueError("comment not found")
        comment = comment_row_to_dict(row)
        identity = resolve_listener_identity(comment)
        broadcaster = conn.execute(
            """
            SELECT broadcaster_id, broadcaster_name, title
            FROM broadcast_history
            WHERE lv = ?
            """,
            (comment["lv"],),
        ).fetchone()
    anonymous_no = anonymous_184_display_no(comment["lv"], comment["hashed_user_id"])
    return {
        "comment": comment,
        "identity": {
            "label": identity.label,
            "primary_value": identity.primary_value,
            "values": list(identity.values),
            "anonymous_184_no": anonymous_no,
        },
        "broadcaster": dict(broadcaster) if broadcaster else {},
    }


def anonymous_184_display_no(lv: str, hashed_user_id: str) -> str:
    if not lv or not hashed_user_id:
        return ""
    path = APP_PATHS.ui_state
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError):
        return ""
    section = data.get("anonymous_184_first_comments", {})
    if not isinstance(section, dict):
        return ""
    lv_map = section.get(lv, {})
    if not isinstance(lv_map, dict):
        return ""
    return normalize_text(lv_map.get(hashed_user_id))


def register_monitor_special_user_by_comment_no(payload: dict[str, Any]) -> dict[str, Any]:
    resolved = resolve_comment_by_no(payload.get("no"), payload.get("lv"))
    comment = resolved["comment"]
    identity = resolved["identity"]
    broadcaster = resolved.get("broadcaster") or {}
    user_id = normalize_text(identity.get("primary_value"))
    if not user_id:
        raise ValueError("listener identity not found")
    label = normalize_text(payload.get("label"))
    if not label:
        label = normalize_text(identity.get("anonymous_184_no"))
        label = f"184-{label}" if label else user_id
    monitor_url = normalize_text(payload.get("monitor_url")) or DEFAULT_MONITOR_URL
    api_key = normalize_text(payload.get("monitor_api_key") or payload.get("api_key"))
    detection_payload = {
        "lv": comment["lv"],
        "special_user_id": user_id,
        "special_user_name": label,
        "broadcaster_id": normalize_text(payload.get("broadcaster_id") or broadcaster.get("broadcaster_id")),
        "broadcaster_name": normalize_text(payload.get("broadcaster_name") or broadcaster.get("broadcaster_name")),
        "comment_no": comment["no"],
        "comment_text": comment["display_text"] or comment["content"],
        "posted_at": comment["created_at"],
        "source": "simple_comment_viewer",
        "note": normalize_text(payload.get("note")),
        "dry_run": bool(payload.get("dry_run", False)),
    }
    monitor_result = post_json(
        f"{monitor_url.rstrip('/')}/api/special-users/detected",
        detection_payload,
        api_key=api_key,
    )
    return {
        "resolved": resolved,
        "monitor_request": detection_payload,
        "monitor_response": monitor_result,
    }


def post_json(url: str, payload: dict[str, Any], *, api_key: str = "") -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    req = request.Request(url, data=data, headers=headers, method="POST")
    with request.urlopen(req, timeout=10) as response:
        raw = response.read().decode("utf-8")
    result = json.loads(raw) if raw else {}
    return result if isinstance(result, dict) else {"raw": result}


def save_live_user_profile(payload: dict[str, Any]) -> dict[str, Any]:
    user_id = normalize_text(payload.get("user_id"))
    if not user_id:
        raise ValueError("user_id is required")
    with database_session() as conn:
        initialize_database(conn)
        upsert_live_user_profile(conn, payload)
        row = get_live_user_profile(conn, user_id)
        return dict(row) if row else {"user_id": user_id}


if __name__ == "__main__":
    raise SystemExit(run())
