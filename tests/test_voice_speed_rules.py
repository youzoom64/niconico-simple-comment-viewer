from __future__ import annotations

import unittest

from app.voicevox.speed_rules import resolve_linear_speed_scale


class VoiceSpeedRulesTests(unittest.TestCase):
    def test_linear_speed_uses_first_queue_scale_as_step_source(self) -> None:
        self.assertEqual(1.0, resolve_linear_speed_scale(0, 1.0, 1.1, 3.0))
        self.assertAlmostEqual(1.1, resolve_linear_speed_scale(1, 1.0, 1.1, 3.0))
        self.assertAlmostEqual(1.2, resolve_linear_speed_scale(2, 1.0, 1.1, 3.0))
        self.assertAlmostEqual(1.3, resolve_linear_speed_scale(3, 1.0, 1.1, 3.0))

    def test_first_queue_scale_can_make_larger_steps(self) -> None:
        self.assertAlmostEqual(1.2, resolve_linear_speed_scale(1, 1.0, 1.2, 3.0))
        self.assertAlmostEqual(1.4, resolve_linear_speed_scale(2, 1.0, 1.2, 3.0))
        self.assertAlmostEqual(1.6, resolve_linear_speed_scale(3, 1.0, 1.2, 3.0))

    def test_linear_speed_is_clamped_to_max_scale(self) -> None:
        self.assertEqual(1.5, resolve_linear_speed_scale(100, 1.0, 1.2, 1.5))


if __name__ == "__main__":
    unittest.main()
