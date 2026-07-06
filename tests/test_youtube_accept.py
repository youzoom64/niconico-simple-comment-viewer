from __future__ import annotations

from app.core.config import AppConfig
from app.services.youtube_accept import find_first_youtube_video


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
            "youtube_obs_source_name": "ブラウザ 2",
        }
    )
    data = config.to_dict()
    assert data["youtube_accept_enabled"] is True
    assert data["youtube_obs_source_name"] == "ブラウザ 2"
