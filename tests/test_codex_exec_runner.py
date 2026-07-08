from __future__ import annotations

import unittest

from app.services.codex_exec_runner import normalize_timeout_seconds


class CodexExecRunnerTests(unittest.TestCase):
    def test_timeout_zero_or_missing_means_no_timeout(self) -> None:
        self.assertIsNone(normalize_timeout_seconds(None))
        self.assertIsNone(normalize_timeout_seconds(0))
        self.assertIsNone(normalize_timeout_seconds(-1))

    def test_positive_timeout_is_kept(self) -> None:
        self.assertEqual(12, normalize_timeout_seconds(12.8))


if __name__ == "__main__":
    unittest.main()
