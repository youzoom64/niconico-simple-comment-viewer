from __future__ import annotations

import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path


def run_gui_entrypoint(argv: Sequence[str]) -> int:
    legacy_app_path = Path(__file__).resolve().parents[2] / "app.py"
    spec = importlib.util.spec_from_file_location("simple_comment_viewer_legacy_app", legacy_app_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"legacy GUI app could not be loaded: {legacy_app_path}")
    module = importlib.util.module_from_spec(spec)
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(legacy_app_path), *argv]
        spec.loader.exec_module(module)
        return int(module.main())
    finally:
        sys.argv = old_argv
