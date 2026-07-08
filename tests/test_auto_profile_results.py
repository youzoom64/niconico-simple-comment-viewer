from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.profiles.listener_identity import ListenerIdentity
from app.core.config import AppConfig
from app.services.auto_profile.execution import auto_profile_timeout_seconds
from app.services.auto_profile.results import (
    auto_profile_result_exists,
    auto_profile_result_key,
    auto_profile_result_path,
    load_auto_profile_result,
    save_auto_profile_result,
)


class AutoProfileResultsTests(unittest.TestCase):
    def test_result_key_uses_primary_identity_value(self) -> None:
        identity = ListenerIdentity("アカウントID: 1234", (("raw_user_id", "1234"), ("user_id", "1234")))

        self.assertEqual("1234", auto_profile_result_key(identity))

    def test_save_and_load_latest_result(self) -> None:
        identity = ListenerIdentity("匿名/ハッシュID: abc", (("hashed_user_id", "abc"),))
        with tempfile.TemporaryDirectory() as tmp:
            base_dir = Path(tmp)
            path = save_auto_profile_result(identity, {"analysis": {"plan": {"display_name": "abc"}}}, base_dir=base_dir)

            self.assertEqual(auto_profile_result_path(identity, base_dir=base_dir), path)
            self.assertTrue(auto_profile_result_exists(identity, base_dir=base_dir))
            loaded = load_auto_profile_result(identity, base_dir=base_dir)
            assert loaded is not None
            self.assertEqual("simple_comment_viewer/auto_profile_result/v1", loaded["schema"])
            self.assertEqual("abc", loaded["analysis"]["plan"]["display_name"])

    def test_auto_profile_timeout_is_disabled(self) -> None:
        self.assertIsNone(auto_profile_timeout_seconds(AppConfig(ai_reply_timeout_seconds=10)))
        self.assertIsNone(auto_profile_timeout_seconds(AppConfig(ai_reply_timeout_seconds=900)))


if __name__ == "__main__":
    unittest.main()
