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
    operation: "TagOperation | None" = None
    reason: str = ""


@dataclass(frozen=True)
class TagOperation:
    clear_all: bool = False
    remove_tags: tuple[str, ...] = ()
    add_tags: tuple[str, ...] = ()


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
    command = parse_tag_operation_command(text)
    if command:
        return TagChangeDecision(True, keyword="タグ:", tags=command.add_tags, operation=command)
    for rule in parse_tag_change_rules(config.tag_change_rules):
        if rule.keyword in text:
            return TagChangeDecision(True, keyword=rule.keyword, tags=rule.tags, operation=TagOperation(add_tags=rule.tags))
    return TagChangeDecision(False, reason="no_keyword")


def parse_tag_operation_command(text: str) -> TagOperation | None:
    stripped = str(text or "").strip()
    if not stripped.startswith("タグ:"):
        return None
    body = stripped.split(":", 1)[1].strip()
    if not body:
        return None
    clear_all = False
    remove_tags: list[str] = []
    add_tags: list[str] = []
    for token in body.split():
        token = token.strip()
        if not token:
            continue
        if token == "--":
            clear_all = True
            continue
        if token.startswith("+") and len(token) > 1:
            add_tags.append(token[1:].strip())
            continue
        if token.startswith("-") and len(token) > 1:
            remove_tags.append(token[1:].strip())
    add_tags = [tag for tag in add_tags if tag]
    remove_tags = [tag for tag in remove_tags if tag]
    if not clear_all and not remove_tags and not add_tags:
        return None
    return TagOperation(clear_all=clear_all, remove_tags=tuple(remove_tags), add_tags=tuple(add_tags))


def change_live_tags(
    lv: str,
    tags: tuple[str, ...],
    *,
    headless: bool = True,
    timeout_seconds: float = 30.0,
    profile_dir: str = "",
    operation: TagOperation | None = None,
) -> None:
    profile_dir = profile_dir or default_chrome_profile_dir()
    operation = operation or TagOperation(add_tags=tags)
    port = 9224
    launch_chrome(profile_dir=profile_dir, port=port, headless=headless, copy_profile=True)
    driver = get_driver(port=port, wait=0.8)
    try:
        driver.set_page_load_timeout(max(10, int(timeout_seconds)))
        driver.get(f"https://live.nicovideo.jp/watch/{lv}")
        WebDriverWait(driver, timeout_seconds).until(lambda d: d.execute_script("return document.readyState") == "complete")
        apply_tags_with_dom(driver, operation, timeout_seconds=timeout_seconds)
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


def apply_tags_with_dom(driver: webdriver.Chrome, operation: TagOperation, *, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    ensure_tag_panel_open(driver)
    time.sleep(0.5)
    try:
        while time.monotonic() < deadline:
            if driver.execute_script(remove_tags_script(), operation.clear_all, list(operation.remove_tags)):
                add_tags_with_keys(driver, operation.add_tags)
                if driver.execute_script(save_tags_script()):
                    return
            time.sleep(0.5)
        raise RuntimeError("タグ編集UIが見つからない、または保存できない")
    finally:
        close_tag_panel(driver)


def ensure_tag_panel_open(driver: webdriver.Chrome) -> None:
    opened = driver.execute_script(
        """
const textOf = el => (el.innerText || el.textContent || el.value || '').trim();
const input = Array.from(document.querySelectorAll('input[type="text"], textarea, [contenteditable="true"]'))
  .find(el => /追加するタグ|タグ|tag/i.test([el.placeholder, el.getAttribute('aria-label'), el.name, el.id].filter(Boolean).join(' ')));
if (input) return true;
const buttons = Array.from(document.querySelectorAll('button, [role="button"], a'));
const edit = buttons.find(el => textOf(el) === 'タグ編集' || /タグ.*(編集|設定)|編集.*タグ/.test(textOf(el)));
if (edit) {
  edit.click();
  return true;
}
return false;
"""
    )
    if not opened:
        raise RuntimeError("タグ編集ボタンが見つからない")


def remove_tags_script() -> str:
    return """
const clearAll = arguments[0];
const removeTags = arguments[1];
const textOf = el => (el.innerText || el.textContent || el.value || '').trim();
const currentRows = () => Array.from(document.querySelectorAll('button,[role="button"]'))
  .filter(el => (el.getAttribute('aria-label') || '') === '削除する')
  .map(btn => {
    let node = btn;
    for (let depth = 0; depth < 6 && node; depth++, node = node.parentElement) {
      const text = textOf(node).replace(/\s+/g, ' ');
      if (text && text.length < 80) return {button: btn, text};
    }
    return {button: btn, text: textOf(btn)};
  });
for (const row of currentRows()) {
  if (clearAll || removeTags.includes(row.text)) row.button.click();
}
return true;
"""


def add_tags_with_keys(driver: webdriver.Chrome, tags: tuple[str, ...]) -> None:
    for tag in tags:
        input_el = driver.find_element(By.CSS_SELECTOR, 'input[placeholder="追加するタグを入力"]')
        input_el.click()
        input_el.send_keys(Keys.CONTROL, "a")
        input_el.send_keys(Keys.BACKSPACE)
        input_el.send_keys(tag)
        time.sleep(0.2)
        driver.find_element(By.CSS_SELECTOR, "button.register-button").click()
        time.sleep(0.8)


def save_tags_script() -> str:
    return """
const textOf = el => (el.innerText || el.textContent || el.value || '').trim();
const buttons = Array.from(document.querySelectorAll('button, [role="button"], a'));
const save = buttons.find(el => /(設定を番組に反映する|保存|登録|変更|完了|更新)/.test(textOf(el)));
if (save) {
  save.click();
  return true;
}
return false;
"""


def close_tag_panel(driver: webdriver.Chrome) -> None:
    driver.execute_script(
        """
const textOf = el => (el.innerText || el.textContent || el.value || '').trim();
const close = Array.from(document.querySelectorAll('button,[role="button"],a')).find(el => textOf(el) === '閉じる');
if (close) close.click();
"""
    )
