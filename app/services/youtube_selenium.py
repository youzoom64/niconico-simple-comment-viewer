from __future__ import annotations

import socket
import time
from dataclasses import dataclass

from app.services.chrome_debug import get_driver, get_profiles, launch_chrome
from app.services.youtube_accept import YouTubeVideo
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchWindowException, TimeoutException, WebDriverException

YOUTUBE_SELENIUM_PORT = 9234


@dataclass(frozen=True)
class YouTubeSeleniumResult:
    video: YouTubeVideo
    profile_dir: str
    port: int
    url: str
    title: str
    duration_seconds: float = 0.0
    ended: bool = False


def default_youtube_profile_dir() -> str:
    profiles = get_profiles()
    if not profiles:
        return "Default"
    return str(profiles[0].get("profile_dir") or "Default")


def youtube_watch_url(video: YouTubeVideo) -> str:
    return f"https://www.youtube.com/watch?v={video.video_id}"


def is_debug_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", int(port))) == 0


def open_youtube_video(
    video: YouTubeVideo,
    profile_dir: str = "",
    port: int = YOUTUBE_SELENIUM_PORT,
    wait_until_end: bool = False,
) -> YouTubeSeleniumResult:
    profile = profile_dir.strip() or default_youtube_profile_dir()
    if is_debug_port_open(port):
        driver = get_driver(port=port, wait=0.2)
    else:
        launch_chrome(profile, port=port, headless=False, copy_profile=True, prefer_api_profile=False)
        driver = get_driver(port=port, wait=1.0)

    switch_to_page_tab(driver)
    driver.set_page_load_timeout(30)
    try:
        driver.get(youtube_watch_url(video))
    except TimeoutException:
        pass
    current_url = str(driver.current_url or "")
    title = str(driver.title or "")
    duration_seconds = 0.0
    ended = False
    if wait_until_end:
        duration_seconds, ended = wait_for_video_end(driver)
        close_current_tab(driver)
    return YouTubeSeleniumResult(
        video=video,
        profile_dir=profile,
        port=port,
        url=current_url,
        title=title,
        duration_seconds=duration_seconds,
        ended=ended,
    )


def switch_to_page_tab(driver) -> None:
    try:
        handles = list(driver.window_handles)
    except WebDriverException:
        handles = []
    for handle in handles:
        try:
            driver.switch_to.window(handle)
            url = str(driver.current_url or "")
        except (NoSuchWindowException, WebDriverException):
            continue
        if not url.startswith("chrome-extension://") and not url.startswith("devtools://"):
            return
    try:
        driver.switch_to.new_window("tab")
    except WebDriverException:
        driver.execute_cdp_cmd("Target.createTarget", {"url": "about:blank"})
        handles = list(driver.window_handles)
        if handles:
            driver.switch_to.window(handles[-1])


def wait_for_video_end(driver, *, start_timeout_seconds: float = 90.0, poll_seconds: float = 1.0) -> tuple[float, bool]:
    first = wait_for_video_element(driver, start_timeout_seconds)
    request_play(driver)
    started = wait_for_playback_start(driver, first, start_timeout_seconds)
    duration = float(started.get("duration") or 0.0)
    while True:
        info = video_state(driver)
        if not info:
            return duration, False
        current = float(info.get("currentTime") or 0.0)
        duration = float(info.get("duration") or duration or 0.0)
        if bool(info.get("ended")):
            return duration, True
        if duration > 0 and current >= max(0.0, duration - 0.5):
            return duration, True
        time.sleep(poll_seconds)


def wait_for_video_element(driver, timeout_seconds: float) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        info = video_state(driver)
        if info:
            return info
        time.sleep(0.5)
    raise TimeoutError("YouTube video element not found")


def wait_for_playback_start(driver, first: dict, timeout_seconds: float) -> dict:
    deadline = time.monotonic() + timeout_seconds
    last_time = float(first.get("currentTime") or 0.0)
    while time.monotonic() < deadline:
        request_play(driver)
        info = video_state(driver)
        if info:
            current = float(info.get("currentTime") or 0.0)
            if current > last_time + 0.2 and not bool(info.get("paused")):
                return info
            last_time = max(last_time, current)
        time.sleep(0.5)
    raise TimeoutError("YouTube playback did not start")


def video_state(driver) -> dict | None:
    return driver.execute_script(
        """
        const video = document.querySelector('video');
        if (!video) {
            return null;
        }
        return {
            currentTime: Number(video.currentTime) || 0,
            duration: Number.isFinite(video.duration) ? video.duration : 0,
            paused: Boolean(video.paused),
            ended: Boolean(video.ended),
            readyState: Number(video.readyState) || 0
        };
        """
    )


def request_play(driver) -> None:
    try:
        paused = bool(driver.execute_script("const v=document.querySelector('video'); return v ? v.paused : true;"))
        if not paused:
            return
        driver.execute_script("const v=document.querySelector('video'); if (v) { v.play().catch(() => {}); }")
    except WebDriverException:
        return
    try:
        button = driver.find_element(By.CSS_SELECTOR, "button.ytp-play-button")
        button.click()
    except WebDriverException:
        pass


def close_current_tab(driver) -> None:
    try:
        driver.close()
    except WebDriverException:
        return
    try:
        handles = list(driver.window_handles)
        if handles:
            driver.switch_to.window(handles[0])
    except WebDriverException:
        pass
