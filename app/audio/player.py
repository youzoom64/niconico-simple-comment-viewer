from __future__ import annotations

from pathlib import Path


def play_wave_file(path: Path | str, wait: bool = False) -> None:
    """Play a WAV file when running on Windows."""

    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(str(target))
    try:
        import winsound
    except ImportError as exc:
        raise RuntimeError("WAV playback is only implemented for Windows winsound") from exc
    flags = winsound.SND_FILENAME
    if not wait:
        flags |= winsound.SND_ASYNC
    winsound.PlaySound(str(target), flags)
