from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from app.services.rvc_worker_api import RvcModel, RvcWorkerOverview


class RvcMmvcDirectError(RuntimeError):
    pass


class RvcMmvcDirectClient:
    MMVC_ROOT = Path(r"J:\ai_tools\voice\rvc\app\MMVCServerSIO")
    MMVC_EXE = MMVC_ROOT / "MMVCServerSIO.exe"
    MMVC_LOG = MMVC_ROOT / "vcclient.log"
    MMVC_ARGS = (
        "-p", "18888",
        "--https", "true",
        "--httpsSelfSigned", "true",
        "--content_vec_500", "pretrain/checkpoint_best_legacy_500.pt",
        "--content_vec_500_onnx", "pretrain/content_vec_500.onnx",
        "--content_vec_500_onnx_on", "true",
        "--hubert_base", "pretrain/hubert_base.pt",
        "--hubert_base_jp", "pretrain/rinna_hubert_base_jp.pt",
        "--hubert_soft", "pretrain/hubert/hubert-soft-0d54a1f4.pt",
        "--nsf_hifigan", "pretrain/nsf_hifigan/model",
        "--crepe_onnx_full", "pretrain/crepe_onnx_full.onnx",
        "--crepe_onnx_tiny", "pretrain/crepe_onnx_tiny.onnx",
        "--rmvpe", "pretrain/rmvpe.pt",
        "--model_dir", "model_dir",
        "--samples", "samples.json",
    )

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        if self.base_url.startswith("http://"):
            alternate = "https://" + self.base_url.removeprefix("http://")
        elif self.base_url.startswith("https://"):
            alternate = "http://" + self.base_url.removeprefix("https://")
        else:
            alternate = self.base_url
        self._base_urls = tuple(dict.fromkeys((self.base_url, alternate)))
        self.last_ensure_started = False

    @staticmethod
    def _valid_info(value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict) and str(value.get("status") or "").upper() == "OK":
            return value
        return None

    def _info_if_ready(self, timeout: float = 1.0) -> dict[str, Any] | None:
        for candidate in self._base_urls:
            try:
                response = httpx.get(f"{candidate}/info", timeout=timeout, verify=False)
                response.raise_for_status()
                value = self._valid_info(response.json())
            except Exception:
                continue
            if value is not None:
                self.base_url = candidate
                return value
        return None

    def _info(self) -> dict[str, Any]:
        value = self._info_if_ready(timeout=4.0)
        if value is not None:
            return value
        targets = " / ".join(self._base_urls)
        raise RvcMmvcDirectError(f"ローカルMMVCへ接続できません: {targets}")

    def _process_running(self) -> bool:
        tasklist = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "tasklist.exe"
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            result = subprocess.run(
                [str(tasklist), "/FI", f"IMAGENAME eq {self.MMVC_EXE.name}", "/FO", "CSV", "/NH"],
                capture_output=True,
                encoding="mbcs",
                errors="replace",
                timeout=4.0,
                creationflags=creation_flags,
                check=False,
            )
        except Exception:
            return False
        return self.MMVC_EXE.name.lower() in (result.stdout or "").lower()

    def _launch(self) -> subprocess.Popen[Any]:
        if not self.MMVC_EXE.is_file():
            raise RvcMmvcDirectError(f"MMVC本体がありません: {self.MMVC_EXE}")
        creation_flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        try:
            return subprocess.Popen(
                [str(self.MMVC_EXE), *self.MMVC_ARGS],
                cwd=str(self.MMVC_ROOT),
                creationflags=creation_flags,
                close_fds=True,
            )
        except Exception as exc:
            raise RvcMmvcDirectError(f"MMVCを起動できません: {exc}") from None

    def ensure_running(self, timeout: float = 45.0) -> dict[str, Any]:
        self.last_ensure_started = False
        if ready := self._info_if_ready():
            return ready

        process: subprocess.Popen[Any] | None = None
        if not self._process_running():
            process = self._launch()
            self.last_ensure_started = True

        deadline = time.monotonic() + max(1.0, timeout)
        while time.monotonic() < deadline:
            if ready := self._info_if_ready():
                return ready
            if process is not None and process.poll() is not None and not self._process_running():
                raise RvcMmvcDirectError(
                    f"MMVCが起動直後に終了しました。ログ: {self.MMVC_LOG}"
                )
            time.sleep(0.5)
        raise RvcMmvcDirectError(
            f"MMVCは起動していますが、{self.base_url}が{int(timeout)}秒以内に応答しません。ログ: {self.MMVC_LOG}"
        )

    @staticmethod
    def _models(info: dict[str, Any]) -> tuple[tuple[RvcModel, ...], RvcModel | None]:
        active_index = int(info.get("modelSlotIndex", -1))
        models = tuple(
            RvcModel(
                slot_index=int(slot.get("slotIndex", -1)),
                name=str(slot.get("name") or f"slot {slot.get('slotIndex')}"),
                active=int(slot.get("slotIndex", -1)) == active_index,
            )
            for slot in info.get("modelSlots") or []
            if isinstance(slot, dict) and str(slot.get("voiceChangerType") or "").upper() == "RVC"
        )
        return models, next((model for model in models if model.active), None)

    def overview(self) -> RvcWorkerOverview:
        info = self._info()
        models, active = self._models(info)
        return RvcWorkerOverview(
            processor_ready=True,
            models=models,
            active_model=active,
            health={"ok": True, "service": "mmvc-direct"},
            status=info,
        )

    def probe(self) -> RvcWorkerOverview:
        return self.overview()

    def select_model(self, slot_index: int) -> RvcModel:
        current_info = self._info()
        current_tune = int(current_info.get("tran", 0))
        self._update_setting("modelSlotIndex", int(slot_index))
        self._update_setting("tran", current_tune)
        updated_info = self._info()
        models, active = self._models(updated_info)
        if active is None or active.slot_index != int(slot_index):
            raise RvcMmvcDirectError("ローカルMMVCがモデル切替を反映しませんでした")
        if int(updated_info.get("tran", current_tune)) != current_tune:
            raise RvcMmvcDirectError("ローカルMMVCがTUNEの引継ぎを反映しませんでした")
        return active

    def _update_setting(self, key: str, value: Any) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{self.base_url}/update_settings",
                files={"key": (None, key), "val": (None, str(value))},
                timeout=20.0,
                verify=False,
            )
            response.raise_for_status()
            result = response.json()
        except Exception as exc:
            raise RvcMmvcDirectError(f"ローカルMMVC設定に失敗しました（{key}）: {exc}") from None
        return result if isinstance(result, dict) else {}

    @staticmethod
    def _device_name(value: Any) -> str:
        return "".join(char.lower() for char in str(value or "") if char.isalnum())

    def _find_device(self, devices: Any, hint: str, *, output: bool) -> int:
        candidates = [item for item in devices or [] if isinstance(item, dict)]
        wasapi = [item for item in candidates if str(item.get("hostAPI") or "") == "Windows WASAPI"]
        pool = wasapi or candidates
        hint_key = self._device_name(hint)
        for item in pool:
            name_key = self._device_name(item.get("name"))
            if hint_key and (hint_key in name_key or name_key in hint_key):
                return int(item.get("index"))
        if output:
            for item in pool:
                if "cableinput" in self._device_name(item.get("name")) and "16ch" not in self._device_name(item.get("name")):
                    return int(item.get("index"))
        raise RvcMmvcDirectError(f"MMVCの{'出力' if output else '入力'}デバイスが見つかりません: {hint}")

    def start_audio(self, input_name: str) -> dict[str, Any]:
        info = self._info()
        input_id = self._find_device(info.get("serverAudioInputDevices"), input_name, output=False)
        output_id = self._find_device(info.get("serverAudioOutputDevices"), "CABLE Input", output=True)
        for key, value in (
            ("serverInputDeviceId", input_id),
            ("serverOutputDeviceId", output_id),
            ("serverMonitorDeviceId", -1),
            ("serverInputAudioSampleRate", 48000),
            ("serverOutputAudioSampleRate", 48000),
            ("serverAudioSampleRate", 48000),
            ("enableServerAudio", 1),
            ("serverAudioStated", 1),
        ):
            self._update_setting(key, value)
        info = self._info()
        if int(info.get("serverAudioStated", 0)) != 1:
            raise RvcMmvcDirectError("MMVC音声処理を開始できませんでした")
        return info

    def stop_audio(self) -> dict[str, Any]:
        self._info()
        self._update_setting("serverAudioStated", 0)
        return self._info()
