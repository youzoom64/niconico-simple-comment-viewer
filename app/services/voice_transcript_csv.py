from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.paths import APP_PATHS


CSV_FIELDS = ("current_time", "broadcast_elapsed", "text")
LV_PATTERN = re.compile(r"lv\d+\Z")
USER_VOICE_SOURCES = {"mic", "microphone", "マイク"}


def normalize_match_text(value: Any) -> str:
    return str(value or "").strip().casefold()


def parse_auto_broadcaster_tokens(value: str) -> tuple[str, ...]:
    raw_tokens = re.split(r"[\r\n,，]+", str(value or ""))
    tokens: list[str] = []
    seen: set[str] = set()
    for raw in raw_tokens:
        token = normalize_match_text(raw)
        if token and token not in seen:
            tokens.append(token)
            seen.add(token)
    return tuple(tokens)


def matches_auto_broadcaster(value: str, *, broadcaster_id: str = "", broadcaster_name: str = "") -> bool:
    tokens = set(parse_auto_broadcaster_tokens(value))
    if not tokens:
        return False
    candidates = {
        normalize_match_text(broadcaster_id),
        normalize_match_text(broadcaster_name),
    }
    candidates.discard("")
    return bool(tokens & candidates)


def is_user_voice_source(source: Any) -> bool:
    return normalize_match_text(source) in USER_VOICE_SOURCES


def format_vpos_elapsed(vpos: Any) -> str:
    text = "" if vpos is None else str(vpos).strip()
    if not text:
        return ""
    try:
        centiseconds = int(float(text))
    except (TypeError, ValueError):
        return ""
    if centiseconds < 0:
        return ""
    total_seconds = centiseconds // 100
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def transcript_csv_path(lv: str, *, output_root: Path = APP_PATHS.output) -> Path:
    normalized = str(lv or "").strip()
    if not LV_PATTERN.fullmatch(normalized):
        raise ValueError(f"Invalid lv for transcript CSV path: {lv!r}")
    return output_root / "broadcasts" / normalized / "voice_transcript.csv"


@dataclass
class VoiceTranscriptCsvRecorder:
    output_root: Path = APP_PATHS.output
    lv: str = ""
    last_vpos: Any = ""

    @property
    def active(self) -> bool:
        return bool(self.lv)

    @property
    def path(self) -> Path | None:
        if not self.active:
            return None
        return transcript_csv_path(self.lv, output_root=self.output_root)

    def start(self, lv: str) -> Path:
        path = transcript_csv_path(lv, output_root=self.output_root)
        self.lv = str(lv).strip()
        self.last_vpos = ""
        return path

    def stop(self) -> None:
        self.lv = ""
        self.last_vpos = ""

    def update_vpos(self, vpos: Any) -> None:
        if vpos is not None and str(vpos).strip():
            self.last_vpos = vpos

    def append(self, text: str, *, vpos: Any | None = None, current_time: datetime | None = None) -> Path | None:
        body = str(text or "").strip()
        if not self.active or not body:
            return None
        path = self.path
        if path is None:
            return None
        target_vpos = self.last_vpos if vpos is None else vpos
        now = current_time or datetime.now()
        path.parent.mkdir(parents=True, exist_ok=True)
        needs_header = not path.exists() or path.stat().st_size == 0
        with path.open("a", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
            if needs_header:
                writer.writeheader()
            writer.writerow(
                {
                    "current_time": now.isoformat(timespec="seconds"),
                    "broadcast_elapsed": format_vpos_elapsed(target_vpos),
                    "text": body,
                }
            )
        return path
