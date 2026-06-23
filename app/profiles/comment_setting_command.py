from __future__ import annotations

import re
from dataclasses import dataclass

KIRITORIKUN_SKIN_RAW_BASE = "https://raw.githubusercontent.com/youzoom64/kiritorikun-skin-assets/main/skins"

KIRITORIKUN_FONTS = [
    "",
    "Dela Gothic One",
    "Hachi Maru Pop",
    "Klee One",
    "RocknRoll One",
    "New Tegomin",
    "Train One",
    "DotGothic16",
    "Reggae One",
    "Yuji Syuku",
    "Yuji Boku",
    "Mochiy Pop One",
    "Kaisei HarunoUmi",
    "Shippori Antique",
    "Stick",
    "Rampart One",
    "Zen Antique",
    "Mochiy Pop P One",
    "Zen Kurenaido",
    "Yusei Magic",
]

SETTING_COMMAND_PATTERN = re.compile(
    r"[＠@](?P<display_name>[^＠@{}]*?)\s*(?:\{(?P<body>[^{}]+)\})?\s*$"
)
SETTING_TOKEN_PATTERN = re.compile(r"^\s*(?P<kind>[SFVsfv])\s*(?P<value>\d+)\s*$")


@dataclass(frozen=True, slots=True)
class CommentSettingCommand:
    display_name: str = ""
    skin_id: int | None = None
    font_id: int | None = None
    voice_id: int | None = None

    @property
    def skin_path(self) -> str:
        if self.skin_id is None:
            return ""
        return f"{KIRITORIKUN_SKIN_RAW_BASE}/{self.skin_id}.png"

    @property
    def font_family(self) -> str:
        if self.font_id is None:
            return ""
        if 0 <= self.font_id < len(KIRITORIKUN_FONTS):
            return KIRITORIKUN_FONTS[self.font_id]
        return ""

    @property
    def voicevox_style(self) -> str:
        if self.voice_id is None:
            return ""
        return str(self.voice_id)

    def has_updates(self) -> bool:
        return bool(self.display_name) or self.skin_id is not None or self.font_id is not None or self.voice_id is not None

    def describe(self) -> str:
        parts: list[str] = []
        if self.display_name:
            parts.append(f"name={self.display_name}")
        if self.skin_id is not None:
            parts.append(f"S{self.skin_id}")
        if self.font_id is not None:
            parts.append(f"F{self.font_id}")
        if self.voice_id is not None:
            parts.append(f"V{self.voice_id}")
        return " ".join(parts)


@dataclass(frozen=True, slots=True)
class CommentSettingCommandMatch:
    readable_text: str
    command: CommentSettingCommand


def parse_comment_setting_command(text: str) -> CommentSettingCommand | None:
    result = split_comment_setting_command(text)
    return result.command if result else None


def split_comment_setting_command(text: str) -> CommentSettingCommandMatch | None:
    source = text or ""
    match = SETTING_COMMAND_PATTERN.search(source)
    if not match:
        return None
    display_name = match.group("display_name").strip()
    settings = parse_setting_body(match.group("body") or "")
    if settings is None:
        return None
    command = CommentSettingCommand(display_name=display_name, **settings)
    if not command.has_updates():
        return None
    return CommentSettingCommandMatch(
        readable_text=source[: match.start()].strip(),
        command=command,
    )


def parse_setting_body(body: str) -> dict[str, int | None] | None:
    if not body:
        return {"skin_id": None, "font_id": None, "voice_id": None}

    settings: dict[str, int | None] = {"skin_id": None, "font_id": None, "voice_id": None}
    saw_token = False
    for raw_token in body.split(","):
        token = raw_token.strip()
        if not token:
            continue
        match = SETTING_TOKEN_PATTERN.match(token)
        if not match:
            return None
        saw_token = True
        value = int(match.group("value"))
        kind = match.group("kind").upper()
        if kind == "S":
            settings["skin_id"] = value
        elif kind == "F":
            settings["font_id"] = value
        elif kind == "V":
            settings["voice_id"] = value
    return settings if saw_token else None
