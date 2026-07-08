from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.db.repositories.broadcast_history import BroadcastHistoryMetadata


def program_info_to_history_metadata(lv: str, info: Any) -> BroadcastHistoryMetadata:
    data = to_plain_data(info)
    return BroadcastHistoryMetadata(
        lv=lv,
        title=first_direct(info, ("title",)) or first_path(data, ("title", "program.title", "programInfo.title")),
        broadcaster_id=first_path(
            data,
            (
                "supplier.programProviderId",
                "program.supplier.programProviderId",
                "programProvider.programProviderId.value",
                "programProvider.programProviderId",
                "programProvider.id.value",
                "socialGroup.id",
                "socialGroup.socialGroupId",
                "program.socialGroup.id",
                "program.socialGroup.socialGroupId",
                "owner.id",
                "owner.userId",
                "broadcaster_id",
                "broadcasterId",
                "programProviderId",
            ),
        ),
        broadcaster_name=first_path(
            data,
            (
                "supplier.name",
                "program.supplier.name",
                "programProvider.name",
                "socialGroup.name",
                "program.socialGroup.name",
                "owner.name",
                "owner.nickname",
                "broadcaster_name",
                "broadcasterName",
            ),
        ),
        program_status=first_direct(info, ("status",))
        or first_path(data, ("status", "program.status", "programInfo.status")),
        started_at=first_path(
            data,
            (
                "beginTime",
                "beginAt",
                "startTime",
                "startedAt",
                "openTime",
                "program.beginTime",
                "program.beginAt",
                "program.startTime",
                "program.openTime",
                "program.schedule.beginTime.seconds",
                "program.schedule.openTime.seconds",
                "program.schedule.startTime.seconds",
            ),
        )
        or None,
        ended_at=first_path(
            data,
            (
                "endTime",
                "endAt",
                "endedAt",
                "program.endTime",
                "program.endAt",
                "program.endedAt",
                "program.schedule.endTime.seconds",
                "program.schedule.scheduledEndTime.seconds",
            ),
        )
        or None,
    )


def enrich_history_metadata(lv: str, metadata: BroadcastHistoryMetadata | None = None) -> BroadcastHistoryMetadata:
    merged = metadata or BroadcastHistoryMetadata(lv=lv)
    try:
        merged = merge_history_metadata(merged, fetch_broadcast_page_history_metadata(lv))
    except Exception:
        pass
    if merged.broadcaster_id:
        try:
            merged = merge_history_metadata(
                merged,
                fetch_user_history_metadata(lv, merged.broadcaster_id, broadcaster_name=merged.broadcaster_name),
            )
        except Exception:
            pass
    return merged


def merge_history_metadata(
    base: BroadcastHistoryMetadata,
    overlay: BroadcastHistoryMetadata | None,
) -> BroadcastHistoryMetadata:
    if overlay is None:
        return base
    return BroadcastHistoryMetadata(
        lv=overlay.lv or base.lv,
        title=overlay.title or base.title,
        broadcaster_id=overlay.broadcaster_id or base.broadcaster_id,
        broadcaster_name=overlay.broadcaster_name or base.broadcaster_name,
        program_status=overlay.program_status or base.program_status,
        started_at=overlay.started_at or base.started_at,
        ended_at=overlay.ended_at or base.ended_at,
    )


def fetch_broadcast_page_history_metadata(lv: str, *, timeout: float = 15.0) -> BroadcastHistoryMetadata:
    lv = str(lv or "").strip()
    if not re.fullmatch(r"lv\d+", lv):
        return BroadcastHistoryMetadata(lv=lv)
    url = f"https://live.nicovideo.jp/watch/{lv}"
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "ja-JP,ja;q=0.9",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        html = response.read().decode(charset, errors="replace")
    return broadcast_page_html_to_history_metadata(lv, html)


def broadcast_page_html_to_history_metadata(lv: str, html: str) -> BroadcastHistoryMetadata:
    data = extract_embedded_data(html)
    embedded = program_info_to_history_metadata(lv, data) if data else BroadcastHistoryMetadata(lv=lv)
    fallback = BroadcastHistoryMetadata(
        lv=lv,
        title=extract_string_field(html, ("title", "programTitle", "liveTitle")),
        broadcaster_id=extract_string_field(html, ("programProviderId", "supplierId", "ownerId", "userId")),
        broadcaster_name=extract_supplier_name(html),
        started_at=value_to_text(extract_unix_time_field(html, ("beginTime", "begin_time", "openTime", "open_time"))) or None,
        ended_at=value_to_text(extract_unix_time_field(html, ("endTime", "end_time"))) or None,
    )
    return merge_history_metadata(fallback, embedded)


class EmbeddedDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.data_props = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.data_props or tag.lower() != "script":
            return
        values = {name.lower(): value or "" for name, value in attrs}
        if values.get("id") == "embedded-data":
            self.data_props = values.get("data-props", "")


def extract_embedded_data(html: str) -> Any:
    parser = EmbeddedDataParser()
    parser.feed(html or "")
    if not parser.data_props:
        return None
    try:
        return json.loads(parser.data_props)
    except json.JSONDecodeError:
        return json.loads(unescape(parser.data_props))


def extract_unix_time_field(html: str, field_names: tuple[str, ...]) -> int | None:
    text = html or ""
    unescaped = unescape(text)
    for source in (text, unescaped):
        for field_name in field_names:
            patterns = (
                rf'{re.escape(field_name)}&quot;\s*:\s*(\d+)',
                rf'"{re.escape(field_name)}"\s*:\s*(\d+)',
                rf"'{re.escape(field_name)}'\s*:\s*(\d+)",
            )
            for pattern in patterns:
                match = re.search(pattern, source)
                if match:
                    try:
                        return int(match.group(1))
                    except ValueError:
                        pass
    return None


def extract_string_field(html: str, field_names: tuple[str, ...]) -> str:
    text = html or ""
    unescaped = unescape(text)
    for source in (text, unescaped):
        for field_name in field_names:
            patterns = (
                rf'{re.escape(field_name)}&quot;\s*:\s*&quot;([^&]+)&quot;',
                rf'"{re.escape(field_name)}"\s*:\s*"([^"]*)"',
            )
            for pattern in patterns:
                match = re.search(pattern, source)
                if match:
                    return unescape(match.group(1)).strip()
    return ""


def extract_supplier_name(html: str) -> str:
    data = extract_embedded_data(html)
    if data:
        return first_path(data, ("program.supplier.name", "supplier.name", "programProvider.name", "socialGroup.name"))
    return extract_string_field(html, ("supplierName", "broadcaster", "ownerName", "nickname"))


def fetch_user_history_metadata(
    lv: str,
    broadcaster_id: str,
    *,
    broadcaster_name: str = "",
) -> BroadcastHistoryMetadata:
    provider_type = provider_type_for_broadcaster_id(broadcaster_id)
    if not provider_type:
        return BroadcastHistoryMetadata(lv=lv, broadcaster_id=broadcaster_id, broadcaster_name=broadcaster_name)
    programs = fetch_user_broadcast_history_programs(broadcaster_id, provider_type=provider_type, limit=20)
    for program in programs:
        program_lv = value_to_text(value_at_path(program, "id.value"))
        if program_lv == lv:
            return user_history_program_to_history_metadata(
                program,
                lv,
                broadcaster_id=broadcaster_id,
                broadcaster_name=broadcaster_name,
            )
    return BroadcastHistoryMetadata(lv=lv, broadcaster_id=broadcaster_id, broadcaster_name=broadcaster_name)


def provider_type_for_broadcaster_id(value: str) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"ch\d+", text, flags=re.IGNORECASE):
        return "channel"
    if text.isdigit():
        return "user"
    return ""


def fetch_user_broadcast_history_programs(
    provider_id: str,
    *,
    provider_type: str = "user",
    limit: int = 20,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    params = urlencode(
        {
            "providerId": str(provider_id),
            "providerType": str(provider_type or "user"),
            "isIncludeNonPublic": "false",
            "offset": "0",
            "limit": str(max(1, int(limit or 20))),
            "withTotalCount": "true",
        }
    )
    request = Request(
        f"https://live.nicovideo.jp/front/api/v2/user-broadcast-history?{params}",
        headers={
            "X-Frontend-Id": "9",
            "X-Frontend-Version": "0",
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "ja-JP,ja;q=0.9",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode(response.headers.get_content_charset() or "utf-8"))
    data = payload.get("data") if isinstance(payload, dict) else None
    programs = data.get("programsList") if isinstance(data, dict) else None
    return [program for program in programs if isinstance(program, dict)] if isinstance(programs, list) else []


def user_history_program_to_history_metadata(
    program: dict[str, Any],
    lv: str,
    *,
    broadcaster_id: str = "",
    broadcaster_name: str = "",
) -> BroadcastHistoryMetadata:
    program_info = program.get("program") if isinstance(program.get("program"), dict) else {}
    schedule = program_info.get("schedule") if isinstance(program_info.get("schedule"), dict) else {}
    provider = program.get("programProvider") if isinstance(program.get("programProvider"), dict) else {}
    provider_id = provider.get("programProviderId") if isinstance(provider.get("programProviderId"), dict) else {}
    social_group = program.get("socialGroup") if isinstance(program.get("socialGroup"), dict) else {}
    provider_kind = str(program_info.get("provider") or social_group.get("type") or "").strip().upper()
    if provider_kind == "CHANNEL":
        api_broadcaster_id = value_to_text(social_group.get("socialGroupId")) or value_to_text(provider_id.get("value"))
        api_broadcaster_name = value_to_text(social_group.get("name")) or value_to_text(provider.get("name"))
    else:
        api_broadcaster_id = value_to_text(provider_id.get("value")) or value_to_text(social_group.get("socialGroupId"))
        api_broadcaster_name = value_to_text(provider.get("name")) or value_to_text(social_group.get("name"))
    return BroadcastHistoryMetadata(
        lv=lv,
        title=value_to_text(program_info.get("title")),
        broadcaster_id=api_broadcaster_id or str(broadcaster_id or "").strip(),
        broadcaster_name=api_broadcaster_name or str(broadcaster_name or "").strip(),
        program_status=value_to_text(schedule.get("status")),
        started_at=value_to_text(schedule.get("beginTime") or schedule.get("openTime")) or None,
        ended_at=value_to_text(schedule.get("endTime") or schedule.get("scheduledEndTime")) or None,
    )


def to_plain_data(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_plain_data(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain_data(item, depth + 1) for item in value]
    if is_dataclass(value):
        return to_plain_data(asdict(value), depth + 1)
    if hasattr(value, "_asdict"):
        return to_plain_data(value._asdict(), depth + 1)
    if hasattr(value, "__dict__"):
        return {
            str(key): to_plain_data(item, depth + 1)
            for key, item in vars(value).items()
            if not str(key).startswith("_")
        }
    return str(value)


def first_direct(value: Any, names: tuple[str, ...]) -> str:
    for name in names:
        text = value_to_text(getattr(value, name, None))
        if text:
            return text
    return ""


def first_path(data: Any, paths: tuple[str, ...]) -> str:
    for path in paths:
        value = value_at_path(data, path)
        text = value_to_text(value)
        if text:
            return text
    return ""


def value_at_path(data: Any, path: str) -> Any:
    value = data
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        next_value = get_case_insensitive(value, part)
        if next_value is None:
            return None
        value = next_value
    return value


def get_case_insensitive(data: dict[str, Any], key: str) -> Any:
    if key in data:
        return data[key]
    normalized = normalize_key(key)
    for item_key, value in data.items():
        if normalize_key(item_key) == normalized:
            return value
    return None


def normalize_key(value: str) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def value_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        for key in ("value", "seconds"):
            if key in value:
                return value_to_text(value.get(key))
    return str(value).strip()
