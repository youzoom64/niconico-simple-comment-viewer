from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlparse


YOUTUBE_URL_RE = re.compile(r"https?://(?:www\.|m\.)?(?:youtube\.com|youtu\.be)/[^\s<>\"]+", re.IGNORECASE)


@dataclass(frozen=True)
class YouTubeVideo:
    video_id: str
    original_url: str

    @property
    def embed_url(self) -> str:
        query = urlencode(
            {
                "autoplay": "1",
                "playsinline": "1",
                "rel": "0",
            }
        )
        return f"https://www.youtube.com/embed/{self.video_id}?{query}"


def find_first_youtube_video(text: str) -> YouTubeVideo | None:
    for match in YOUTUBE_URL_RE.finditer(str(text or "")):
        url = match.group(0).rstrip("。、,.）)]}")
        video_id = extract_youtube_video_id(url)
        if video_id:
            return YouTubeVideo(video_id=video_id, original_url=url)
    return None


def extract_youtube_video_id(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host.endswith("youtu.be"):
        return clean_video_id(parsed.path.strip("/").split("/", 1)[0])
    if host.endswith("youtube.com"):
        if parsed.path == "/watch":
            return clean_video_id((parse_qs(parsed.query).get("v") or [""])[0])
        if parsed.path.startswith("/shorts/"):
            return clean_video_id(parsed.path.split("/")[2] if len(parsed.path.split("/")) > 2 else "")
        if parsed.path.startswith("/embed/"):
            return clean_video_id(parsed.path.split("/")[2] if len(parsed.path.split("/")) > 2 else "")
    return ""


def clean_video_id(value: str) -> str:
    match = re.match(r"^[A-Za-z0-9_-]{11}", str(value or ""))
    return match.group(0) if match else ""
