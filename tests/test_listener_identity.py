from __future__ import annotations

import unittest

from app.profiles.listener_identity import resolve_listener_identity


class ListenerIdentityTests(unittest.TestCase):
    def test_registered_user_prefers_raw_user_id(self) -> None:
        identity = resolve_listener_identity({"user_id": "1234", "raw_user_id": "1234", "hashed_user_id": "hash"})

        self.assertEqual("アカウントID: 1234", identity.label)
        self.assertEqual((("raw_user_id", "1234"), ("user_id", "1234")), identity.values)

    def test_anonymous_user_uses_hash(self) -> None:
        identity = resolve_listener_identity({"user_id": "hash", "raw_user_id": "0", "hashed_user_id": "hash"})

        self.assertEqual("匿名/ハッシュID: hash", identity.label)
        self.assertEqual((("hashed_user_id", "hash"), ("user_id", "hash")), identity.values)

    def test_missing_user_returns_empty_identity(self) -> None:
        identity = resolve_listener_identity({"user_id": "", "raw_user_id": "0", "hashed_user_id": ""})

        self.assertTrue(identity.is_empty())


if __name__ == "__main__":
    unittest.main()
