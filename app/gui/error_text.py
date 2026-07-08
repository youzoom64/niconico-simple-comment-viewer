from __future__ import annotations


def summarize_error_for_dialog(message: str, *, limit: int = 180) -> str:
    text = " ".join(str(message or "").split())
    if not text:
        return "詳細なし"
    if "TimeoutExpired" in text:
        return "Codex実行がタイムアウトしました。詳細はログまたは詳細欄を確認してください。"
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def wrap_error_details(message: str, *, width: int = 120) -> str:
    text = str(message or "")
    if not text:
        return ""
    wrapped_lines: list[str] = []
    for source_line in text.splitlines() or [""]:
        line = source_line
        while len(line) > width:
            wrapped_lines.append(line[:width])
            line = line[width:]
        wrapped_lines.append(line)
    return "\n".join(wrapped_lines)
