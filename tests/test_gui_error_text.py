from __future__ import annotations

import unittest

from app.gui.error_text import summarize_error_for_dialog, wrap_error_details


class GuiErrorTextTests(unittest.TestCase):
    def test_timeout_summary_does_not_include_long_command(self) -> None:
        message = "TimeoutExpired: Command '[' + 'C:' + ('x' * 300)"
        summary = summarize_error_for_dialog(message)
        self.assertIn("タイムアウト", summary)
        self.assertNotIn("Command", summary)

    def test_long_details_are_hard_wrapped(self) -> None:
        details = wrap_error_details("x" * 260, width=80)
        self.assertTrue(all(len(line) <= 80 for line in details.splitlines()))


if __name__ == "__main__":
    unittest.main()
