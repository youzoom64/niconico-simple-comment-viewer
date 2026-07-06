from __future__ import annotations

from app.core.config import AppConfig
from app.services.youtube_accept import find_first_youtube_video
from app.services.youtube_selenium import wait_for_video_end, youtube_watch_url


def test_find_first_youtube_watch_url() -> None:
    video = find_first_youtube_video("これ https://www.youtube.com/watch?v=dQw4w9WgXcQ 見て")
    assert video is not None
    assert video.video_id == "dQw4w9WgXcQ"
    assert video.embed_url == "https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1&playsinline=1&rel=0"


def test_find_first_youtu_be_url() -> None:
    video = find_first_youtube_video("https://youtu.be/dQw4w9WgXcQ")
    assert video is not None
    assert video.video_id == "dQw4w9WgXcQ"


def test_youtube_accept_config_roundtrip() -> None:
    config = AppConfig.from_dict(
        {
            "youtube_accept_enabled": True,
            "youtube_chrome_profile": "Profile 11",
        }
    )
    data = config.to_dict()
    assert data["youtube_accept_enabled"] is True
    assert data["youtube_chrome_profile"] == "Profile 11"


def test_youtube_selenium_watch_url() -> None:
    video = find_first_youtube_video("https://youtu.be/dQw4w9WgXcQ")
    assert video is not None
    assert youtube_watch_url(video) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_wait_for_video_end_uses_video_time() -> None:
    driver = FakeVideoDriver(
        [
            {"currentTime": 0.0, "duration": 3.0, "paused": True, "ended": False},
            {"currentTime": 0.6, "duration": 3.0, "paused": False, "ended": False},
            {"currentTime": 2.5, "duration": 3.0, "paused": False, "ended": False},
        ]
    )
    duration, ended = wait_for_video_end(driver, start_timeout_seconds=1.0, poll_seconds=0.0)
    assert duration == 3.0
    assert ended is True


class FakeVideoDriver:
    def __init__(self, states: list[dict]) -> None:
        self.states = states
        self.index = 0

    def execute_script(self, script: str):
        if "return v ? v.paused : true" in script:
            return bool(self.states[min(self.index, len(self.states) - 1)]["paused"])
        if "v.play()" in script:
            return None
        state = self.states[min(self.index, len(self.states) - 1)]
        self.index += 1
        return dict(state)

    def find_element(self, *_args):
        return FakeButton()


class FakeButton:
    def click(self) -> None:
        return None
