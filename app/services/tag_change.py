from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from app.core.config import AppConfig
from app.services.chrome_debug import close_chrome, get_driver, get_profiles, launch_chrome


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


def change_live_tags(
    lv: str,
    tags: tuple[str, ...],
    *,
    headless: bool = True,
    timeout_seconds: float = 30.0,
    profile_dir: str = "",
) -> None:
    profile_dir = profile_dir or default_chrome_profile_dir()
    port = 9224
    launch_chrome(profile_dir=profile_dir, port=port, headless=headless, copy_profile=True)
    driver = get_driver(port=port, wait=0.8)
    try:
        driver.set_page_load_timeout(max(10, int(timeout_seconds)))
        driver.get(f"https://live.nicovideo.jp/watch/{lv}")
        WebDriverWait(driver, timeout_seconds).until(lambda d: d.execute_script("return document.readyState") == "complete")
        apply_tags_with_dom(driver, tags, timeout_seconds=timeout_seconds)
    finally:
        try:
            driver.quit()
        finally:
            close_chrome()


def default_chrome_profile_dir() -> str:
    profiles = get_profiles()
    if not profiles:
        raise RuntimeError("Chromeプロファイルが見つからない")
    return str(profiles[0]["profile_dir"])


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
