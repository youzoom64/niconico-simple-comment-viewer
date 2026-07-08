from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.core.paths import APP_PATHS
from app.profiles.listener_identity import ListenerIdentity, resolve_listener_identity

RESULT_SCHEMA = "simple_comment_viewer/auto_profile_result/v1"


def auto_profile_results_dir(base_dir: Path | None = None) -> Path:
    return Path(base_dir or APP_PATHS.data / "auto_profile_results")


def auto_profile_result_key(identity: ListenerIdentity) -> str:
    source = identity.primary_value or identity.label
    text = re.sub(r"[^0-9A-Za-z_.-]+", "_", source.strip())
    return text.strip("._") or "unknown"


def auto_profile_result_path(identity: ListenerIdentity, *, base_dir: Path | None = None) -> Path:
    return auto_profile_results_dir(base_dir) / f"{auto_profile_result_key(identity)}.json"


def auto_profile_result_path_for_row(row: dict[str, Any], *, base_dir: Path | None = None) -> Path:
    return auto_profile_result_path(resolve_listener_identity(row), base_dir=base_dir)


def auto_profile_result_exists(identity: ListenerIdentity, *, base_dir: Path | None = None) -> bool:
    return auto_profile_result_path(identity, base_dir=base_dir).is_file()


def save_auto_profile_result(
    identity: ListenerIdentity,
    payload: dict[str, Any],
    *,
    base_dir: Path | None = None,
) -> Path:
    path = auto_profile_result_path(identity, base_dir=base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"schema": RESULT_SCHEMA, **payload}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def load_auto_profile_result(identity: ListenerIdentity, *, base_dir: Path | None = None) -> dict[str, Any] | None:
    path = auto_profile_result_path(identity, base_dir=base_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
