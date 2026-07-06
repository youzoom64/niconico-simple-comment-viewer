from __future__ import annotations

import json
import os
import subprocess
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

CHROME_USER_DATA = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
API_CHROME_DEBUG_USER_DATA = r"C:\project_root\app_workspaces\API\scripts\chrome_debug_data_9222"

_chrome_process = None


class _Logger:
    def info(self, message: str) -> None:
        print(f"[chrome_debug] INFO {message}", flush=True)

    def warning(self, message: str) -> None:
        print(f"[chrome_debug] WARN {message}", flush=True)

    def debug(self, message: str) -> None:
        print(f"[chrome_debug] DEBUG {message}", flush=True)


log = _Logger()


def _find_cached_chromedriver() -> str | None:
    cache_root = os.path.expandvars(r"%USERPROFILE%\.cache\selenium\chromedriver\win64")
    if not os.path.isdir(cache_root):
        return None
    candidates: list[tuple[tuple[int, ...], str]] = []
    for version in os.listdir(cache_root):
        driver_path = os.path.join(cache_root, version, "chromedriver.exe")
        if not os.path.exists(driver_path):
            continue
        parts = []
        for part in version.split("."):
            try:
                parts.append(int(part))
            except ValueError:
                parts.append(0)
        candidates.append((tuple(parts), driver_path))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def get_profiles() -> list[dict]:
    profiles = []

    if not os.path.exists(CHROME_USER_DATA):
        log.warning(f"Chrome User Dataが見つかりません: {CHROME_USER_DATA}")
        return profiles

    for item in os.listdir(CHROME_USER_DATA):
        item_path = os.path.join(CHROME_USER_DATA, item)

        if not os.path.isdir(item_path):
            continue
        if item != "Default" and not item.startswith("Profile "):
            continue

        prefs_path = os.path.join(item_path, "Preferences")
        if not os.path.exists(prefs_path):
            continue

        try:
            with open(prefs_path, "r", encoding="utf-8") as f:
                prefs = json.load(f)

            account_info = prefs.get("account_info", [{}])
            if account_info:
                info = account_info[0]
                email = info.get("email", "")
                name = info.get("full_name", "")
            else:
                email = ""
                name = ""

            profiles.append({
                "profile_dir": item,
                "name": name,
                "email": email,
            })
        except Exception as e:
            log.warning(f"プロファイル読み込み失敗: {item} - {e}")
            continue

    def sort_key(p):
        if p["profile_dir"] == "Default":
            return (0, 0)
        try:
            num = int(p["profile_dir"].replace("Profile ", ""))
            return (1, num)
        except Exception:
            return (2, p["profile_dir"])

    profiles.sort(key=sort_key)
    return profiles


def launch_chrome(
    profile_dir: str = "Default",
    port: int = 9222,
    headless: bool = False,
    extra_args: list[str] | None = None,
    copy_profile: bool = True,
) -> subprocess.Popen:
    global _chrome_process
    import shutil

    if not os.path.exists(CHROME_EXE):
        raise FileNotFoundError(f"Chromeが見つかりません: {CHROME_EXE}")

    profile_path = os.path.join(CHROME_USER_DATA, profile_dir)
    if not os.path.exists(profile_path):
        raise FileNotFoundError(f"プロファイルが見つかりません: {profile_path}")

    api_debug_profile_path = os.path.join(API_CHROME_DEBUG_USER_DATA, profile_dir)
    if os.path.exists(api_debug_profile_path):
        debug_user_data = API_CHROME_DEBUG_USER_DATA
        log.info(f"API側Chromeプロファイルを使用: {debug_user_data}")
    else:
        debug_user_data = os.path.join(os.path.dirname(__file__), f"chrome_debug_data_{port}")
    debug_profile_path = os.path.join(debug_user_data, profile_dir)

    if copy_profile and debug_user_data != API_CHROME_DEBUG_USER_DATA:
        prefs_dst = os.path.join(debug_profile_path, "Preferences")
        if os.path.exists(prefs_dst):
            log.info(f"プロファイルコピー済み、スキップ: {profile_dir}")
        else:
            os.makedirs(debug_profile_path, exist_ok=True)

            essential_files = [
                "Cookies",
                "Login Data",
                "Preferences",
                "Web Data",
                "Bookmarks",
                "Favicons",
            ]

            log.info(f"プロファイルコピー中: {profile_dir}")
            for filename in essential_files:
                src = os.path.join(profile_path, filename)
                dst = os.path.join(debug_profile_path, filename)
                if os.path.exists(src):
                    try:
                        shutil.copy2(src, dst)
                    except Exception as e:
                        log.warning(f"コピー失敗: {filename} - {e}")

            local_state_src = os.path.join(CHROME_USER_DATA, "Local State")
            local_state_dst = os.path.join(debug_user_data, "Local State")
            if os.path.exists(local_state_src) and not os.path.exists(local_state_dst):
                try:
                    shutil.copy2(local_state_src, local_state_dst)
                except Exception as e:
                    log.warning(f"Local Stateコピー失敗: {e}")
            log.info(f"プロファイルコピー完了: {profile_dir}")
    else:
        os.makedirs(debug_profile_path, exist_ok=True)
        log.info(f"プロファイルコピーなしで起動: {profile_dir}")

    args = [
        CHROME_EXE,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={debug_user_data}",
        f"--profile-directory={profile_dir}",
    ]

    if headless:
        args.append("--headless=new")

    if extra_args:
        args.extend(extra_args)

    log.info(f"Chrome起動: {profile_dir} (port={port})")
    log.debug(f"起動コマンド: {' '.join(args)}")

    _chrome_process = subprocess.Popen(args)
    time.sleep(0.8)
    return _chrome_process


def get_driver(port: int = 9222, wait: float = 0, performance_log: bool = False) -> webdriver.Chrome:
    if wait > 0:
        time.sleep(wait)

    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    if performance_log:
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    log.info(f"Selenium接続: port={port}")
    driver_path = _find_cached_chromedriver()
    if driver_path:
        log.info(f"cached chromedriver使用: {driver_path}")
        driver = webdriver.Chrome(service=Service(driver_path), options=options)
    else:
        driver = webdriver.Chrome(options=options)

    return driver


def close_chrome() -> None:
    global _chrome_process

    if _chrome_process:
        log.info("Chrome終了")
        _chrome_process.terminate()
        _chrome_process = None
