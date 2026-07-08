from __future__ import annotations

import hashlib
import json
from pathlib import Path
from textwrap import dedent
from typing import Any, Callable

from app.core.logging import LogSink, log_error, log_execution, log_result
from app.services.codex_exec_runner import run_codex_exec

NullLogSink = lambda _level, _message: None
SkinRunner = Callable[[str], str]


def render_auto_profile_skin(
    plan: Any,
    output_path: Path,
    *,
    skin_spec: Any = None,
    icon_path: str = "",
    icon_summary: dict[str, Any] | None = None,
    workdir: Path | None = None,
    model: str = "",
    effort: str = "",
    timeout_seconds: int = 300,
    runner: SkinRunner | None = None,
    evidence_path: Path | None = None,
    log: LogSink = NullLogSink,
) -> Path:
    return create_auto_profile_skin_with_codex(
        plan,
        output_path,
        skin_spec=skin_spec,
        icon_path=icon_path,
        icon_summary=icon_summary,
        workdir=workdir,
        model=model,
        effort=effort,
        timeout_seconds=timeout_seconds,
        runner=runner,
        evidence_path=evidence_path,
        log=log,
    )


def create_auto_profile_skin_with_codex(
    plan: Any,
    output_path: Path,
    *,
    skin_spec: Any = None,
    icon_path: str = "",
    icon_summary: dict[str, Any] | None = None,
    workdir: Path | None = None,
    model: str = "",
    effort: str = "",
    timeout_seconds: int = 300,
    runner: SkinRunner | None = None,
    evidence_path: Path | None = None,
    log: LogSink = NullLogSink,
) -> Path:
    width = int(getattr(skin_spec, "width", 512) or 512)
    height = int(getattr(skin_spec, "height", 32) or 32)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prompt = build_codex_skin_prompt(
        plan,
        output_path=output_path,
        width=width,
        height=height,
        icon_path=icon_path,
        icon_summary=icon_summary or {},
    )
    log_execution(log, "CodexスキンPNG生成", level="INFO", path=output_path, width=width, height=height)
    command: list[str] = []
    stderr = ""
    returncode = 0
    if runner is not None:
        text = runner(prompt)
    else:
        result = run_codex_exec(prompt, cwd=workdir, timeout_seconds=timeout_seconds, model=model, effort=effort)
        command = result.command
        stderr = result.stderr
        returncode = result.returncode
        if not result.ok:
            log_error(log, "CodexスキンPNG生成失敗", code=result.returncode, stderr=result.stderr[-300:])
            raise RuntimeError(f"skin generation Codex failed: {result.returncode}")
        text = result.text
    actual_width, actual_height, mode = inspect_png(output_path)
    if (actual_width, actual_height) != (width, height):
        log_error(log, "CodexスキンPNG寸法不一致", expected=f"{width}x{height}", actual=f"{actual_width}x{actual_height}")
        raise ValueError(f"generated skin size must be {width}x{height}: {actual_width}x{actual_height}")
    if evidence_path is not None:
        save_codex_skin_evidence(
            evidence_path,
            command=command,
            returncode=returncode,
            stderr=stderr,
            prompt=prompt,
            response=text,
            output_path=output_path,
            width=actual_width,
            height=actual_height,
            mode=mode,
        )
    log_result(log, "CodexスキンPNG生成", path=output_path, bytes=output_path.stat().st_size, mode=mode)
    return output_path


def build_codex_skin_prompt(
    plan: Any,
    *,
    output_path: Path,
    width: int,
    height: int,
    icon_path: str,
    icon_summary: dict[str, Any],
) -> str:
    payload = {
        "output_path": str(output_path),
        "width": width,
        "height": height,
        "display_name": getattr(plan, "display_name", ""),
        "persona_summary": getattr(plan, "persona_summary", ""),
        "skin_concept": getattr(plan, "skin_concept", ""),
        "skin_prompt": getattr(plan, "skin_prompt", ""),
        "palette": list(getattr(plan, "palette", ()) or ()),
        "icon_path": str(icon_path or ""),
        "icon_summary": icon_summary,
    }
    input_json = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    header = dedent(
        """
        依頼です。
        入力JSONには、対象ユーザーのコメント傾向、表示名、スキンサイズ、ユーザーアイコンのパス、フォント候補、ボイス候補が入っています。
        この情報をもとに、512x32 のニコニコ/OBSコメント用スキンPNGを作成してください。
        返答は次のJSONだけにしてください。
        {
          "path": "生成したPNGファイルのパス",
          "width": 512,
          "height": 32
        }
        """
    ).strip()
    return f"{header}\n\n入力JSON:\n{input_json}"


def inspect_png(path: Path) -> tuple[int, int, str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required to verify generated skins") from exc
    with Image.open(path) as image:
        return image.size[0], image.size[1], image.mode


def save_codex_skin_evidence(
    path: Path,
    *,
    command: list[str],
    returncode: int,
    stderr: str,
    prompt: str,
    response: str,
    output_path: Path,
    width: int,
    height: int,
    mode: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "codex_command": command,
        "codex_returncode": returncode,
        "stderr_tail": stderr[-1000:],
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "raw_ai_response": response,
        "raw_ai_response_sha256": hashlib.sha256(str(response or "").encode("utf-8")).hexdigest(),
        "png_path": str(output_path),
        "png_exists": output_path.is_file(),
        "png_size": output_path.stat().st_size if output_path.is_file() else 0,
        "width": width,
        "height": height,
        "mode": mode,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
