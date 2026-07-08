from __future__ import annotations

import unittest

from app.obs.google_fonts import google_fonts_stylesheet_url, render_google_fonts_head_links
from app.obs.list_overlay_html import render_comment_list_html
from app.obs.live_overlay import render_overlay_html


class ObsGoogleFontsTest(unittest.TestCase):
    def test_google_fonts_stylesheet_url_contains_preset_families(self) -> None:
        url = google_fonts_stylesheet_url(["Dela Gothic One", "Reggae One"])

        self.assertEqual(
            "https://fonts.googleapis.com/css2?family=Dela+Gothic+One&family=Reggae+One&display=swap",
            url,
        )

    def test_head_links_load_google_fonts(self) -> None:
        html = render_google_fonts_head_links()

        self.assertIn("https://fonts.googleapis.com", html)
        self.assertIn("https://fonts.gstatic.com", html)
        self.assertIn("Dela+Gothic+One", html)

    def test_overlay_html_loads_google_fonts(self) -> None:
        html = render_overlay_html()

        self.assertIn("https://fonts.googleapis.com/css2", html)
        self.assertIn("Dela+Gothic+One", html)

    def test_list_overlay_html_loads_google_fonts(self) -> None:
        html = render_comment_list_html()

        self.assertIn("https://fonts.googleapis.com/css2", html)
        self.assertIn("Dela+Gothic+One", html)


if __name__ == "__main__":
    unittest.main()
