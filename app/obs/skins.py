from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkinStyle:
    skin_path: str = ""
    width_px: int = 512
    height_px: int = 32
    font_family: str = "sans-serif"
    font_size_px: int = 32
    font_color: str = "#ffffff"

    def css_variables(self) -> str:
        return (
            f"--skin-width:{max(1, self.width_px)}px;"
            f"--skin-height:{max(1, self.height_px)}px;"
            f"--font-family:{self.font_family};"
            f"--font-size:{max(1, self.font_size_px)}px;"
            f"--font-color:{self.font_color};"
        )
