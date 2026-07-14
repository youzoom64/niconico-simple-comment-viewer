from __future__ import annotations

import math
import sys
import threading
import time
from array import array
from collections import defaultdict
from typing import Any


PCM16_SILENT_PEAK = 32


def pcm_s16le_levels(payload: bytes) -> dict[str, Any]:
    """Return signal levels without retaining or logging PCM samples."""
    if len(payload) % 2:
        raise ValueError("PCM16 payload length must be even")
    samples = array("h")
    samples.frombytes(payload)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        return {"samples": 0, "rms": 0.0, "peak": 0, "rmsDbfs": -120.0, "silent": True}
    peak = max(abs(value) for value in samples)
    rms = math.sqrt(sum(value * value for value in samples) / len(samples))
    rms_dbfs = 20.0 * math.log10(rms / 32768.0) if rms > 0 else -120.0
    return {
        "samples": len(samples),
        "rms": round(rms, 3),
        "peak": int(peak),
        "rmsDbfs": round(max(-120.0, rms_dbfs), 3),
        "silent": peak <= PCM16_SILENT_PEAK,
    }


class TransportMetrics:
    def __init__(self, role: str):
        self.role = role
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, Any] = {}
        self._last_error = ""
        self._last_error_at = ""
        self._last_rtt_ms: float | None = None
        self._jitter_ms = 0.0
        self._audio_boundaries: dict[str, dict[str, Any]] = {}
        self.started_ns = time.time_ns()

    def increment(self, name: str, amount: int = 1) -> int:
        with self._lock:
            self._counters[name] += amount
            return self._counters[name]

    def set_gauge(self, name: str, value: Any) -> None:
        with self._lock:
            self._gauges[name] = value

    def set_error(self, value: str) -> None:
        with self._lock:
            self._last_error = str(value)[:500]
            self._last_error_at = _utc_now()

    def clear_error(self) -> None:
        with self._lock:
            self._last_error = ""
            self._last_error_at = ""

    def record_rtt(self, rtt_ms: float) -> None:
        with self._lock:
            if self._last_rtt_ms is not None:
                delta = abs(rtt_ms - self._last_rtt_ms)
                self._jitter_ms = delta if self._jitter_ms == 0 else (self._jitter_ms * 0.8 + delta * 0.2)
            self._last_rtt_ms = rtt_ms

    def record_audio_boundary(self, name: str, payload: bytes) -> dict[str, Any]:
        levels = pcm_s16le_levels(payload)
        with self._lock:
            current = self._audio_boundaries.setdefault(
                str(name),
                {
                    "frames": 0,
                    "bytes": 0,
                    "silentFrames": 0,
                    "nonSilentFrames": 0,
                    "lastRms": 0.0,
                    "lastPeak": 0,
                    "maxPeak": 0,
                    "lastRmsDbfs": -120.0,
                    "lastUpdatedAt": "",
                },
            )
            current["frames"] += 1
            current["bytes"] += len(payload)
            counter = "silentFrames" if levels["silent"] else "nonSilentFrames"
            current[counter] += 1
            current["lastRms"] = levels["rms"]
            current["lastPeak"] = levels["peak"]
            current["maxPeak"] = max(int(current["maxPeak"]), int(levels["peak"]))
            current["lastRmsDbfs"] = levels["rmsDbfs"]
            current["lastUpdatedAt"] = _utc_now()
            return dict(current)

    def audio_boundaries(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {name: dict(value) for name, value in self._audio_boundaries.items()}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "role": self.role,
                "uptimeSeconds": round((time.time_ns() - self.started_ns) / 1_000_000_000, 3),
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "audioBoundaries": {name: dict(value) for name, value in self._audio_boundaries.items()},
                "rttMs": None if self._last_rtt_ms is None else round(self._last_rtt_ms, 3),
                "jitterMs": round(self._jitter_ms, 3),
                "lastError": self._last_error,
                "lastErrorAt": self._last_error_at,
            }


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
