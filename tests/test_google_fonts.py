from __future__ import annotations

import unittest

from app.gui.common.google_fonts import build_google_fonts_css_url, extract_font_urls


class GoogleFontsTest(unittest.TestCase):
    def test_build_google_fonts_css_url_encodes_family(self) -> None:
        url = build_google_fonts_css_url("Dela Gothic One")

        self.assertEqual(
            "https://fonts.googleapis.com/css2?family=Dela+Gothic+One&display=swap",
            url,
        )

    def test_extract_font_urls_keeps_unique_fonts_gstatic_urls(self) -> None:
        css = """
        @font-face { src: url(https://fonts.gstatic.com/s/example/a.ttf) format('truetype'); }
        @font-face { src: url('https://fonts.gstatic.com/s/example/a.ttf') format('truetype'); }
        @font-face { src: url("https://fonts.gstatic.com/s/example/b.ttf") format('truetype'); }
        @font-face { src: url(https://example.com/not-font.ttf) format('truetype'); }
        """

        self.assertEqual(
            [
                "https://fonts.gstatic.com/s/example/a.ttf",
                "https://fonts.gstatic.com/s/example/b.ttf",
            ],
            extract_font_urls(css),
        )


if __name__ == "__main__":
    unittest.main()
