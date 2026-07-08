from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.logging import LogSink, log_branch, log_execution, log_result

NullLogSink = lambda _level, _message: None


def resolve_user_icon_reference(row: dict[str, Any], *, log: LogSink = NullLogSink) -> tuple[str, dict[str, Any] | None]:
    user_id = ""
    for key in ("raw_user_id", "user_id"):
        candidate = str(row.get(key) or "").strip()
        if candidate and candidate != "0":
            user_id = candidate
            break
    if not user_id:
        log_branch(log, "本人アイコン取得スキップ", level="DEBUG", reason="missing_user_id")
        return "", None
    try:
        from app.gui.user_icons import cached_user_icon_path
    except Exception as exc:
        log_branch(log, "本人アイコン取得スキップ", level="WARN", reason=f"icon_module_unavailable:{type(exc).__name__}")
        return "", None
    log_execution(log, "本人アイコン取得", level="INFO", user_id=user_id)
    path = cached_user_icon_path(user_id)
    if path is None:
        log_branch(log, "本人アイコンなし", level="WARN", user_id=user_id)
        return "", None
    summary = summarize_icon_image(path, log=log)
    log_result(log, "本人アイコン取得", path=path, summary=bool(summary))
    return str(path), summary


def summarize_icon_image(path: Path, *, log: LogSink = NullLogSink) -> dict[str, Any] | None:
    try:
        from PIL import Image
    except ImportError:
        log_branch(log, "本人アイコン要約スキップ", level="WARN", reason="Pillow is not installed")
        return None
    try:
        with Image.open(path) as image:
            image = image.convert("RGBA")
            sample = image.resize((1, 1))
            average = sample.getpixel((0, 0))[:3]
            palette_image = image.convert("P", palette=Image.Palette.ADAPTIVE, colors=5)
            palette = palette_image.getpalette() or []
            color_counts = palette_image.getcolors() or []
            color_counts.sort(reverse=True)
            dominant = []
            for _count, color_index in color_counts[:5]:
                offset = int(color_index) * 3
                if offset + 2 < len(palette):
                    dominant.append(rgb_to_hex(tuple(palette[offset : offset + 3])))
            return {
                "path": str(path),
                "width": image.width,
                "height": image.height,
                "average_color": rgb_to_hex(average),
                "dominant_colors": dominant,
            }
    except Exception as exc:
        log_branch(log, "本人アイコン要約失敗", level="WARN", error=f"{type(exc).__name__}: {exc}")
        return None


def rgb_to_hex(rgb: tuple[int, int, int] | tuple[Any, Any, Any]) -> str:
    red, green, blue = (max(0, min(255, int(value))) for value in rgb)
    return f"#{red:02x}{green:02x}{blue:02x}"
