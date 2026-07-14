from __future__ import annotations

import os
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from app.services.rtfw_api import RtfwApiClient


class RtfwServiceRestartError(RuntimeError):
    pass


class RtfwServiceManager:
    ROOT = Path(r"J:\tools\scripts\rtfw_lan_client")
    START_CMD = ROOT / "start_service.cmd"
    PORT = 8801

    @staticmethod
    def _powershell(script: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
        )

    def _listener_info(self) -> dict[str, Any] | None:
        script = (
            f"$c=Get-NetTCPConnection -State Listen -LocalPort {self.PORT} -ErrorAction SilentlyContinue | "
            "Where-Object {$_.LocalAddress -in @('127.0.0.1','::1')} | Select-Object -First 1; "
            "if($c){$p=Get-CimInstance Win32_Process -Filter ('ProcessId='+$c.OwningProcess); "
            "[pscustomobject]@{pid=[int]$c.OwningProcess;commandLine=[string]$p.CommandLine}|ConvertTo-Json -Compress}"
        )
        result = self._powershell(script)
        text = result.stdout.strip()
        if not text and not result.stderr.strip():
            return None
        if result.returncode != 0:
            raise RtfwServiceRestartError((result.stderr or "8801の所有確認に失敗しました").strip())
        return json.loads(text) if text else None

    def _listener_pid(self) -> int | None:
        info = self._listener_info()
        return int(info["pid"]) if info else None

    def restart(self, base_url: str) -> dict[str, Any]:
        info = self._listener_info()
        if info is not None:
            pid = int(info["pid"])
            if "run_client.py" not in str(info.get("commandLine") or "").lower():
                raise RtfwServiceRestartError(f"8801は別プロセスが使用中です: PID {pid}")
            stopped = self._powershell(f"Stop-Process -Id {pid} -Force -ErrorAction Stop")
            if stopped.returncode != 0 and self._listener_pid() is not None:
                raise RtfwServiceRestartError((stopped.stderr or f"RTFWサービス PID {pid} を停止できません").strip())

        deadline = time.monotonic() + 8.0
        while self._listener_pid() is not None and time.monotonic() < deadline:
            time.sleep(0.1)
        if self._listener_pid() is not None:
            raise RtfwServiceRestartError("RTFWサービスの8801解放を確認できません")
        if not self.START_CMD.is_file():
            raise RtfwServiceRestartError(f"RTFW起動ファイルがありません: {self.START_CMD}")

        result_path = Path(tempfile.gettempdir()) / f"niconico_scv_rtfw_restart_{os.getpid()}.state"
        command = [os.environ.get("ComSpec", r"C:\Windows\System32\cmd.exe"), "/d", "/s", "/c", str(self.START_CMD), "-ResultPath", str(result_path)]
        completed = subprocess.run(
            command,
            cwd=self.ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20.0,
            check=False,
        )
        if completed.returncode != 0:
            raise RtfwServiceRestartError(f"RTFW起動処理が失敗しました: exit {completed.returncode}")

        client = RtfwApiClient(base_url, timeout_seconds=1.0)
        deadline = time.monotonic() + 12.0
        last_error = ""
        while time.monotonic() < deadline:
            try:
                health = client.health()
                if health.get("ok"):
                    return {"ok": True, "pid": self._listener_pid(), "health": health}
            except Exception as exc:
                last_error = str(exc)
            time.sleep(0.2)
        raise RtfwServiceRestartError(f"RTFWサービスの復帰を確認できません: {last_error}")
