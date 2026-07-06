from __future__ import annotations

import sqlite3
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from app.core.config import AppConfig
from app.services.comment_post import WATCH_APP_DB_PATH


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
    session = load_latest_user_session()
    options = chrome_options(headless=headless)
    with tempfile.TemporaryDirectory(prefix="scv_tag_chrome_") as profile_dir:
        options.add_argument(f"--user-data-dir={profile_dir}")
        driver = webdriver.Chrome(options=options)
        try:
            driver.set_page_load_timeout(max(10, int(timeout_seconds)))
            driver.get("https://live.nicovideo.jp/")
            driver.add_cookie({"name": "user_session", "value": session, "domain": ".nicovideo.jp", "path": "/"})
            driver.get(f"https://live.nicovideo.jp/watch/{lv}")
            WebDriverWait(driver, timeout_seconds).until(lambda d: d.execute_script("return document.readyState") == "complete")
            apply_tags_with_dom(driver, tags, timeout_seconds=timeout_seconds)
        finally:
            driver.quit()


def chrome_options(*, headless: bool) -> Options:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--window-size=1280,900")
    return options


def load_latest_user_session(db_path: Path = WATCH_APP_DB_PATH) -> str:
    if not db_path.exists():
        raise RuntimeError(f"user_session DBが見つからない: {db_path}")
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT user_session
            FROM niconico_sessions
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
    if not row or not str(row[0]).strip():
        raise RuntimeError("保存済み user_session が見つからない")
    return str(row[0]).strip()


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
