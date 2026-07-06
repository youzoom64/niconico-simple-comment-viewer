from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from app.core.config import AppConfig
CHROME_USER_DATA = Path(os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data"))
CHROME_EXE = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


@dataclass(frozen=True)
class TagChangeRule:
    keyword: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class TagChangeDecision:
    matched: bool
    keyword: str = ""
    tags: tuple[str, ...] = ()
    reason: str = ""


def parse_tag_change_rules(value: str) -> list[TagChangeRule]:
    rules: list[TagChangeRule] = []
    seen: set[str] = set()
    for raw in str(value or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if "=>" in line:
            keyword, tags_text = line.split("=>", 1)
        elif "\t" in line:
            keyword, tags_text = line.split("\t", 1)
        else:
            keyword, tags_text = line, ""
        keyword = keyword.strip()
        tags = tuple(tag.strip() for tag in tags_text.replace("/", ",").split(",") if tag.strip())
        if keyword and tags and keyword not in seen:
            seen.add(keyword)
            rules.append(TagChangeRule(keyword=keyword, tags=tags))
    return rules


def decide_tag_change(config: AppConfig, row: dict[str, Any]) -> TagChangeDecision:
    if not config.tag_change_enabled:
        return TagChangeDecision(False, reason="disabled")
    text = str(row.get("content") or row.get("text") or "").strip()
    if not text:
        return TagChangeDecision(False, reason="empty_comment")
    for rule in parse_tag_change_rules(config.tag_change_rules):
        if rule.keyword in text:
            return TagChangeDecision(True, keyword=rule.keyword, tags=rule.tags)
    return TagChangeDecision(False, reason="no_keyword")


def change_live_tags(lv: str, tags: tuple[str, ...], *, headless: bool = True, timeout_seconds: float = 30.0) -> None:
    profile_dir = default_chrome_profile_dir()
    port = 9224
    process = launch_debug_chrome(profile_dir=profile_dir, port=port, headless=headless, copy_profile=True)
    driver = get_debug_driver(port=port, wait=0.8)
    try:
        driver.set_page_load_timeout(max(10, int(timeout_seconds)))
        driver.get(f"https://live.nicovideo.jp/watch/{lv}")
        WebDriverWait(driver, timeout_seconds).until(lambda d: d.execute_script("return document.readyState") == "complete")
        apply_tags_with_dom(driver, tags, timeout_seconds=timeout_seconds)
    finally:
        try:
            driver.quit()
        finally:
            process.terminate()


def chrome_options(*, headless: bool) -> Options:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--window-size=1280,900")
    return options


def default_chrome_profile_dir() -> str:
    profiles = get_profiles()
    if not profiles:
        raise RuntimeError(f"Chromeプロファイルが見つからない: {CHROME_USER_DATA}")
    logged_in = [profile for profile in profiles if profile.get("email")]
    return str((logged_in or profiles)[0]["profile_dir"])


def get_profiles() -> list[dict[str, str]]:
    profiles: list[dict[str, str]] = []
    if not CHROME_USER_DATA.exists():
        return profiles
    for item in CHROME_USER_DATA.iterdir():
        if not item.is_dir():
            continue
        if item.name != "Default" and not item.name.startswith("Profile "):
            continue
        prefs_path = item / "Preferences"
        if not prefs_path.exists():
            continue
        try:
            import json

            prefs = json.loads(prefs_path.read_text(encoding="utf-8"))
            account_info = prefs.get("account_info", [{}])
            info = account_info[0] if account_info else {}
            profiles.append(
                {
                    "profile_dir": item.name,
                    "name": str(info.get("full_name") or ""),
                    "email": str(info.get("email") or ""),
                }
            )
        except Exception:
            continue
    profiles.sort(key=chrome_profile_sort_key)
    return profiles


def chrome_profile_sort_key(profile: dict[str, str]) -> tuple[int, int | str]:
    profile_dir = profile.get("profile_dir") or ""
    if profile_dir == "Default":
        return (0, 0)
    if profile_dir.startswith("Profile "):
        try:
            return (1, int(profile_dir.replace("Profile ", "")))
        except ValueError:
            pass
    return (2, profile_dir)


def launch_debug_chrome(
    *,
    profile_dir: str,
    port: int,
    headless: bool,
    copy_profile: bool,
) -> subprocess.Popen:
    if not CHROME_EXE.exists():
        raise FileNotFoundError(f"Chromeが見つからない: {CHROME_EXE}")
    profile_path = CHROME_USER_DATA / profile_dir
    if not profile_path.exists():
        raise FileNotFoundError(f"プロファイルが見つからない: {profile_path}")

    debug_user_data = Path(__file__).resolve().parents[2] / "data" / f"chrome_debug_data_{port}"
    debug_profile_path = debug_user_data / profile_dir
    if copy_profile:
        prefs_dst = debug_profile_path / "Preferences"
        if not prefs_dst.exists():
            debug_profile_path.mkdir(parents=True, exist_ok=True)
            for filename in ("Cookies", "Login Data", "Preferences", "Web Data", "Bookmarks", "Favicons"):
                src = profile_path / filename
                dst = debug_profile_path / filename
                if src.exists():
                    try:
                        shutil.copy2(src, dst)
                    except Exception:
                        pass
            local_state_src = CHROME_USER_DATA / "Local State"
            local_state_dst = debug_user_data / "Local State"
            if local_state_src.exists() and not local_state_dst.exists():
                try:
                    shutil.copy2(local_state_src, local_state_dst)
                except Exception:
                    pass
    else:
        debug_profile_path.mkdir(parents=True, exist_ok=True)

    args = [
        str(CHROME_EXE),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={debug_user_data}",
        f"--profile-directory={profile_dir}",
    ]
    if headless:
        args.append("--headless=new")
    process = subprocess.Popen(args)
    time.sleep(0.8)
    return process


def get_debug_driver(*, port: int, wait: float = 0) -> webdriver.Chrome:
    if wait > 0:
        time.sleep(wait)
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    driver_path = find_cached_chromedriver()
    if driver_path:
        return webdriver.Chrome(service=Service(driver_path), options=options)
    return webdriver.Chrome(options=options)


def find_cached_chromedriver() -> str | None:
    cache_root = Path(os.path.expandvars(r"%USERPROFILE%\.cache\selenium\chromedriver\win64"))
    if not cache_root.is_dir():
        return None
    candidates: list[tuple[tuple[int, ...], Path]] = []
    for version in cache_root.iterdir():
        driver_path = version / "chromedriver.exe"
        if not driver_path.exists():
            continue
        parts: list[int] = []
        for part in version.name.split("."):
            try:
                parts.append(int(part))
            except ValueError:
                parts.append(0)
        candidates.append((tuple(parts), driver_path))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return str(candidates[0][1])


def apply_tags_with_dom(driver: webdriver.Chrome, tags: tuple[str, ...], *, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    script = """
const tags = arguments[0];
const buttons = Array.from(document.querySelectorAll('button, [role="button"], a'));
const edit = buttons.find(el => /タグ.*(編集|設定)|編集.*タグ/.test((el.innerText || el.textContent || '').trim()));
if (edit) edit.click();
return Boolean(edit);
"""
    driver.execute_script(script, list(tags))
    time.sleep(0.5)
    while time.monotonic() < deadline:
        if driver.execute_script(set_tags_script(), list(tags)):
            return
        time.sleep(0.5)
    raise RuntimeError("タグ編集UIが見つからない、または保存できない")


def set_tags_script() -> str:
    return """
const tags = arguments[0];
const text = tags.join(' ');
const inputs = Array.from(document.querySelectorAll('input[type="text"], textarea, [contenteditable="true"]'));
const target = inputs.find(el => {
  const label = [el.placeholder, el.getAttribute('aria-label'), el.name, el.id].filter(Boolean).join(' ');
  return /タグ|tag/i.test(label) || el.tagName === 'TEXTAREA' || el.isContentEditable;
});
if (!target) return false;
target.focus();
if (target.isContentEditable) {
  target.innerText = text;
  target.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: text}));
} else {
  target.value = text;
  target.dispatchEvent(new Event('input', {bubbles: true}));
  target.dispatchEvent(new Event('change', {bubbles: true}));
}
const buttons = Array.from(document.querySelectorAll('button, [role="button"], a'));
const save = buttons.find(el => /(保存|登録|変更|完了|更新)/.test((el.innerText || el.textContent || '').trim()));
if (save) {
  save.click();
  return true;
}
target.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true}));
return true;
"""
