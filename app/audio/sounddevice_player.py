"""VOICEVOX WAVを除外可能な子プロセスとして再生する。"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from pathlib import Path

import sounddevice as sd
import soundfile as sf


def play(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(path)
    print(f"audio_player start path={path}", file=sys.stderr, flush=True)
    audio, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
    with sd.OutputStream(samplerate=int(sample_rate), channels=audio.shape[1], dtype="float32") as stream:
        stream.write(audio)
    print(f"audio_player complete frames={len(audio)} rate={sample_rate}", file=sys.stderr, flush=True)


def serve() -> int:
    reply_lock = threading.Lock()

    def run_request(request: dict) -> None:
        request_id = str(request.get("id", ""))
        reply = bool(request.get("reply", False))
        try:
            play(Path(str(request["path"])).resolve())
            response = {"id": request_id, "status": "complete"}
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            response = {"id": request_id, "status": "error", "error": error}
            if not reply:
                print(f"audio_player error detail={error}", file=sys.stderr, flush=True)
        if reply:
            with reply_lock:
                print(json.dumps(response), flush=True)

    print(json.dumps({"status": "ready", "pid": os.getpid()}), flush=True)
    for line in sys.stdin:
        try:
            request = json.loads(line)
        except Exception as exc:
            print(f"audio_player request error detail={type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            continue
        worker = threading.Thread(target=run_request, args=(request,), daemon=True)
        worker.start()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Play one WAV through sounddevice")
    parser.add_argument("wav", type=Path, nargs="?")
    parser.add_argument("--server", action="store_true")
    args = parser.parse_args()
    if args.server:
        return serve()
    if args.wav is None:
        parser.error("wav is required unless --server is used")
    try:
        play(args.wav.resolve())
    except Exception as exc:
        print(f"audio_player error type={type(exc).__name__} detail={exc}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
