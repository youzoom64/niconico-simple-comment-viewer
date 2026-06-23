from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


VOICEVOX_OFFICIAL_URL = "https://voicevox.hiroshiba.jp/"


class VoicevoxOfficialSampleError(RuntimeError):
    """Raised when the official VOICEVOX sample catalog cannot be parsed."""


@dataclass(frozen=True, slots=True)
class VoicevoxOfficialSample:
    character_name: str
    style_name: str
    sample_index: int
    url: str
    filename: str


@dataclass(frozen=True, slots=True)
class VoicevoxOfficialStyleSamples:
    character_name: str
    style_name: str
    samples: tuple[VoicevoxOfficialSample, ...]


@dataclass(frozen=True, slots=True)
class VoicevoxOfficialCharacterSamples:
    character_name: str
    styles: tuple[VoicevoxOfficialStyleSamples, ...]


def fetch_official_voicevox_sample_catalog(
    source_url: str = VOICEVOX_OFFICIAL_URL,
    timeout_seconds: float = 20.0,
) -> list[VoicevoxOfficialCharacterSamples]:
    """Fetch and parse sample wav URLs from the official VOICEVOX site."""

    request = Request(source_url, headers={"User-Agent": "simple-comment-viewer/1.0"})
    with urlopen(request, timeout=timeout_seconds) as response:
        document = response.read().decode("utf-8", errors="replace")
    return parse_official_voicevox_sample_catalog(document, base_url=source_url)


def parse_official_voicevox_sample_catalog(
    document: str,
    base_url: str = VOICEVOX_OFFICIAL_URL,
) -> list[VoicevoxOfficialCharacterSamples]:
    """Parse Astro island props that contain official VOICEVOX sample wav URLs."""

    characters: list[VoicevoxOfficialCharacterSamples] = []
    for raw_props in _iter_audio_sample_props(document):
        props = _load_props(raw_props)
        character_name = _read_devalue_string(props.get("characterName"))
        if not character_name:
            continue
        styles = _parse_style_samples(props.get("audioSamples"), character_name, base_url)
        if styles:
            characters.append(VoicevoxOfficialCharacterSamples(character_name=character_name, styles=tuple(styles)))
    if not characters:
        raise VoicevoxOfficialSampleError("official VOICEVOX sample catalog was not found")
    return characters


def flatten_official_voicevox_samples(
    catalog: list[VoicevoxOfficialCharacterSamples],
) -> list[VoicevoxOfficialSample]:
    samples: list[VoicevoxOfficialSample] = []
    for character in catalog:
        for style in character.styles:
            samples.extend(style.samples)
    return samples


def build_direct_sample_mapping(catalog: list[VoicevoxOfficialCharacterSamples]) -> dict[str, Any]:
    """Build a direct-playback mapping that can replace local sample wav paths later."""

    mapping: dict[str, Any] = {}
    voice_id = 1
    for character in catalog:
        voices: dict[str, list[dict[str, Any]]] = {}
        for style in character.styles:
            entries: list[dict[str, Any]] = []
            for sample in style.samples:
                entries.append(
                    {
                        "voice_id": voice_id,
                        "character": sample.character_name,
                        "style": sample.style_name,
                        "sample_index": sample.sample_index,
                        "url": sample.url,
                        "filename": sample.filename,
                        "source": "voicevox_official",
                    }
                )
                voice_id += 1
            voices[style.style_name] = entries
        mapping[character.character_name] = {"voices": voices}
    return mapping


def _iter_audio_sample_props(document: str) -> list[str]:
    pattern = re.compile(r"<astro-island\b[^>]*component-export=\"default\"[^>]*\bprops=\"([^\"]*audioSamples[^\"]*)\"", re.DOTALL)
    return pattern.findall(document)


def _load_props(raw_props: str) -> dict[str, Any]:
    decoded = html.unescape(raw_props)
    try:
        loaded = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise VoicevoxOfficialSampleError(f"invalid official VOICEVOX sample props: {exc}") from exc
    return loaded if isinstance(loaded, dict) else {}


def _parse_style_samples(value: Any, character_name: str, base_url: str) -> list[VoicevoxOfficialStyleSamples]:
    styles: list[VoicevoxOfficialStyleSamples] = []
    for wrapped_style in _read_devalue_list(value):
        style_payload = wrapped_style[1] if _is_devalue_wrapped(wrapped_style) else wrapped_style
        if not isinstance(style_payload, dict):
            continue
        style_name = _read_devalue_string(style_payload.get("style"))
        urls = _read_devalue_list(style_payload.get("urls"))
        samples: list[VoicevoxOfficialSample] = []
        for index, wrapped_url in enumerate(urls, start=1):
            sample_path = _read_devalue_string(wrapped_url)
            if not sample_path:
                continue
            sample_url = urljoin(base_url, sample_path)
            samples.append(
                VoicevoxOfficialSample(
                    character_name=character_name,
                    style_name=style_name,
                    sample_index=index,
                    url=sample_url,
                    filename=PurePosixPath(urlparse(sample_url).path).name,
                )
            )
        if style_name and samples:
            styles.append(
                VoicevoxOfficialStyleSamples(
                    character_name=character_name,
                    style_name=style_name,
                    samples=tuple(samples),
                )
            )
    return styles


def _read_devalue_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    if _is_devalue_wrapped(value):
        inner = value[1]
        return inner if isinstance(inner, str) else ""
    return ""


def _read_devalue_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    if len(value) == 2 and isinstance(value[1], list):
        return value[1]
    return value


def _is_devalue_wrapped(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 2 and value[0] in (0, 1)
