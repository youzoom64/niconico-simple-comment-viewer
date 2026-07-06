from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from google.protobuf.json_format import MessageToDict

from app.events.kinds import CHAT_KINDS


def message_to_dict(message: Any) -> dict[str, Any]:
    try:
        return MessageToDict(message, preserving_proto_field_name=True)
    except TypeError:
        return MessageToDict(message)
    except Exception as exc:
        return {"_string": str(message), "_error": f"{type(exc).__name__}: {exc}"}


def color_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if hasattr(value, "r") and hasattr(value, "g") and hasattr(value, "b"):
        return f"#{int(value.r):02x}{int(value.g):02x}{int(value.b):02x}"
    return str(value)


def normalize_chat_payload(kind: str, payload: Any) -> dict[str, Any]:
    modifier = getattr(payload, "modifier", None)
    raw_user_id = getattr(payload, "raw_user_id", "")
    hashed_user_id = getattr(payload, "hashed_user_id", "")
    user_id = str(raw_user_id) if raw_user_id not in {None, 0, "0", ""} else str(hashed_user_id or "")

    commands: list[str] = []
    if raw_user_id in {0, "0"}:
        commands.append("184")
    if modifier is not None:
        for attr, default in (
            ("position", "naka"),
            ("size", "medium"),
            ("font", "defont"),
            ("opacity", "Normal"),
        ):
            value = getattr(payload, attr, None) or getattr(modifier, attr, None)
            if value and str(value) != default:
                commands.append(str(value))
        color = getattr(modifier, "color", None) or getattr(payload, "color", None)
        color_text = color_to_text(color)
        if color_text and color_text != "white":
            commands.append(color_text)

    return {
        "kind": kind,
        "no": getattr(payload, "no", ""),
        "user_id": user_id,
        "raw_user_id": "" if raw_user_id is None else str(raw_user_id),
        "hashed_user_id": "" if hashed_user_id is None else str(hashed_user_id),
        "account_status": str(getattr(payload, "account_status", "")),
        "vpos": getattr(payload, "vpos", ""),
        "commands": " ".join(commands),
        "content": str(getattr(payload, "content", "") or ""),
    }


def normalize_standard_ndgr_comment(chunked_message: Any, kind: str) -> dict[str, Any] | None:
    try:
        from ndgr_client import NDGRClient

        comment = NDGRClient.convertToNDGRComment(chunked_message)
        xml_comment = NDGRClient.convertToXMLCompatibleComment(comment)
        raw_user_id = getattr(comment, "raw_user_id", "")
        hashed_user_id = getattr(comment, "hashed_user_id", "")
        user_id = str(raw_user_id) if raw_user_id not in {None, 0, "0", ""} else str(hashed_user_id or "")
        at = getattr(comment, "at", None)
        return {
            "kind": kind,
            "no": getattr(comment, "no", ""),
            "user_id": user_id,
            "raw_user_id": "" if raw_user_id is None else str(raw_user_id),
            "hashed_user_id": "" if hashed_user_id is None else str(hashed_user_id),
            "account_status": str(getattr(comment, "account_status", "")),
            "vpos": getattr(comment, "vpos", ""),
            "commands": str(getattr(xml_comment, "mail", "") or ""),
            "content": str(getattr(comment, "content", "") or ""),
            "at": at.isoformat(timespec="microseconds") if isinstance(at, datetime) else "",
        }
    except Exception:
        return None


def summarize_non_chat(kind: str, payload_dict: dict[str, Any]) -> str:
    if kind == "tag_updated":
        tag_summary = summarize_tag_updated(payload_dict)
        if tag_summary:
            return tag_summary
    for key in ("message", "content", "text", "label", "name", "title", "body", "item_name"):
        value = payload_dict.get(key)
        if value:
            return str(value)
    return json.dumps(payload_dict, ensure_ascii=False, separators=(",", ":"))[:240]


def summarize_tag_updated(payload_dict: dict[str, Any]) -> str:
    tags = payload_dict.get("tags")
    if not isinstance(tags, list):
        return ""
    names: list[str] = []
    for tag in tags:
        if isinstance(tag, dict):
            text = str(tag.get("text") or tag.get("name") or "").strip()
        else:
            text = str(tag or "").strip()
        if text:
            names.append(text)
    return " / ".join(names)


def chunked_message_to_row(chunked_message: Any, source: str, page_index: int) -> dict[str, Any] | None:
    if not chunked_message.HasField("meta") or not chunked_message.HasField("message"):
        return None

    meta = chunked_message.meta
    message = chunked_message.message
    kind = message.WhichOneof("data") or "unknown"
    payload = getattr(message, kind) if kind != "unknown" and hasattr(message, kind) else message
    payload_dict = message_to_dict(payload)
    raw_dict = message_to_dict(chunked_message)

    base = {
        "source": source,
        "page_index": page_index,
        "message_id": getattr(meta, "id", ""),
        "at": "",
        "kind": kind,
        "no": "",
        "user_id": "",
        "raw_user_id": "",
        "hashed_user_id": "",
        "account_status": "",
        "vpos": "",
        "commands": "",
        "content": "",
        "payload": payload_dict,
        "raw": raw_dict,
    }
    at = getattr(meta, "at", None)
    if at is not None and hasattr(at, "ToDatetime"):
        try:
            base["at"] = at.ToDatetime().isoformat(timespec="microseconds")
        except Exception:
            base["at"] = str(at)

    if kind in CHAT_KINDS:
        normalized = normalize_standard_ndgr_comment(chunked_message, kind)
        base.update(normalized or normalize_chat_payload(kind, payload))
    elif kind == "forwarded_chat":
        chat_payload = getattr(payload, "chat", None)
        if chat_payload is not None:
            base.update(normalize_chat_payload(kind, chat_payload))
        base["content"] = base["content"] or summarize_non_chat(kind, payload_dict)
    else:
        base["content"] = summarize_non_chat(kind, payload_dict)
        if kind == "tag_updated" and base["content"]:
            base["message"] = base["content"]

    return base
