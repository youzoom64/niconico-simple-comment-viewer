from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Any

from app.obs.animation import lane_style, overlay_animation_css
from app.obs.skins import SkinStyle


@dataclass(frozen=True)
class ObsComment:
    text: str
    lane: int = 0
    duration_seconds: float = 18.0
    skin: SkinStyle = field(default_factory=SkinStyle)
    metadata: dict[str, Any] = field(default_factory=dict)


def render_overlay_document(comments: list[ObsComment]) -> str:
    body = "\n".join(render_comment(comment) for comment in comments)
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
html, body {{
  margin: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: transparent;
}}
.obs-root {{
  position: fixed;
  inset: 0;
  overflow: hidden;
  background: transparent;
  pointer-events: none;
}}
.obs-comment {{
  position: absolute;
  right: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: var(--skin-height);
  color: var(--font-color);
  font-family: var(--font-family);
  font-size: var(--font-size);
  white-space: nowrap;
  text-shadow: 0 2px 4px rgba(0,0,0,.65);
}}
.obs-skin {{
  width: var(--skin-width);
  height: var(--skin-height);
  object-fit: contain;
}}
{overlay_animation_css()}
</style>
</head>
<body>
<div class="obs-root">
{body}
</div>
</body>
</html>
"""


def render_comment(comment: ObsComment) -> str:
    style = (
        comment.skin.css_variables()
        + lane_style(comment.lane, comment.skin.height_px + 8)
        + f"animation-duration:{max(1.0, comment.duration_seconds):.2f}s;"
    )
    skin_html = ""
    if comment.skin.skin_path:
        skin_html = f'<img class="obs-skin" src="{escape(comment.skin.skin_path, quote=True)}" alt="">'
    return (
        f'<div class="obs-comment" style="{escape(style, quote=True)}">'
        f"{skin_html}<span>{escape(comment.text)}</span>"
        "</div>"
    )
