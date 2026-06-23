from __future__ import annotations


def overlay_animation_css() -> str:
    return """
@keyframes slideRightToLeftEaseOut {
  0% { transform: translateX(110vw); opacity: 0; }
  6% { opacity: 1; }
  75% { opacity: 1; }
  100% { transform: translateX(-110vw); opacity: 0; }
}
.obs-comment {
  animation-name: slideRightToLeftEaseOut;
  animation-timing-function: cubic-bezier(.05,.78,.22,1);
  animation-fill-mode: forwards;
}
"""


def lane_style(lane_index: int, lane_height_px: int) -> str:
    bottom = max(0, lane_index) * max(1, lane_height_px)
    return f"bottom:{bottom}px;"
