from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.infra.voicevox_samples.official_catalog import (
    VoicevoxOfficialSample,
    build_direct_sample_mapping,
    fetch_official_voicevox_sample_catalog,
    flatten_official_voicevox_samples,
)


LogFunc = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class GitHubVoicevoxSampleUploadConfig:
    repository: str
    local_repo_dir: Path
    branch: str = "main"
    visibility: str = "public"
    asset_dir_name: str = "voicevox_official_samples"
    commit_message: str = "Update VOICEVOX official sample cache"
    timeout_seconds: float = 30.0
    create_repo_if_missing: bool = True


@dataclass(frozen=True, slots=True)
class GitHubVoicevoxSampleUploadResult:
    repository: str
    branch: str
    local_repo_dir: Path
    sample_count: int
    downloaded_count: int
    skipped_count: int
    mapping_path: Path
    direct_mapping_path: Path
    raw_base_url: str
    private_direct_playback: bool


@dataclass(frozen=True, slots=True)
class DownloadedVoicevoxSample:
    sample: VoicevoxOfficialSample
    local_path: Path
    skipped: bool
    byte_count: int


def sync_official_voicevox_samples_to_github(
    config: GitHubVoicevoxSampleUploadConfig,
    log: LogFunc | None = None,
) -> GitHubVoicevoxSampleUploadResult:
    """Fetch official VOICEVOX samples, save them locally, commit, and push to GitHub."""

    logger = log or (lambda _message: None)
    ensure_github_repository(config, logger)
    ensure_local_asset_repository(config, logger)

    logger("[実行] VOICEVOX公式サンプル一覧取得")
    catalog = fetch_official_voicevox_sample_catalog(timeout_seconds=config.timeout_seconds)
    samples = flatten_official_voicevox_samples(catalog)
    logger(f"[結果] VOICEVOX公式サンプル一覧取得: characters={len(catalog)} samples={len(samples)}")

    asset_dir = config.local_repo_dir / config.asset_dir_name
    downloaded = download_voicevox_samples(samples, asset_dir, config.timeout_seconds, logger)
    mapping_path = write_official_sample_catalog_files(config, catalog)

    commit_and_push_asset_repository(config, logger)
    downloaded_count = sum(1 for item in downloaded if not item.skipped)
    skipped_count = sum(1 for item in downloaded if item.skipped)
    raw_base_url = build_raw_github_base_url(config.repository, config.branch)
    return GitHubVoicevoxSampleUploadResult(
        repository=config.repository,
        branch=config.branch,
        local_repo_dir=config.local_repo_dir,
        sample_count=len(samples),
        downloaded_count=downloaded_count,
        skipped_count=skipped_count,
        mapping_path=mapping_path,
        direct_mapping_path=config.local_repo_dir / "voice_mapping_direct.json",
        raw_base_url=raw_base_url,
        private_direct_playback=config.visibility.lower() == "private",
    )


def download_voicevox_samples(
    samples: list[VoicevoxOfficialSample],
    destination_dir: Path,
    timeout_seconds: float = 30.0,
    log: LogFunc | None = None,
) -> list[DownloadedVoicevoxSample]:
    logger = log or (lambda _message: None)
    destination_dir.mkdir(parents=True, exist_ok=True)
    results: list[DownloadedVoicevoxSample] = []
    total = len(samples)
    for index, sample in enumerate(samples, start=1):
        target = destination_dir / sample.filename
        if target.exists() and target.stat().st_size > 0:
            results.append(DownloadedVoicevoxSample(sample=sample, local_path=target, skipped=True, byte_count=target.stat().st_size))
            continue
        logger(f"[実行] サンプル保存 {index}/{total}: {sample.character_name} / {sample.style_name} / {sample.filename}")
        request = Request(sample.url, headers={"User-Agent": "simple-comment-viewer/1.0"})
        with urlopen(request, timeout=timeout_seconds) as response:
            data = response.read()
        target.write_bytes(data)
        results.append(DownloadedVoicevoxSample(sample=sample, local_path=target, skipped=False, byte_count=len(data)))
    return results


def write_official_sample_catalog_files(
    config: GitHubVoicevoxSampleUploadConfig,
    catalog: list,
) -> Path:
    config.local_repo_dir.mkdir(parents=True, exist_ok=True)
    raw_base_url = build_raw_github_base_url(config.repository, config.branch)
    direct_mapping = build_direct_sample_mapping(catalog)
    direct_mapping = rewrite_mapping_urls_to_github(direct_mapping, raw_base_url, config.asset_dir_name)

    direct_mapping_path = config.local_repo_dir / "voice_mapping_direct.json"
    direct_mapping_path.write_text(json.dumps(direct_mapping, ensure_ascii=False, indent=2), encoding="utf-8")

    catalog_path = config.local_repo_dir / "voicevox_official_samples.json"
    serializable_catalog = [
        {
            "character": character.character_name,
            "styles": [
                {
                    "style": style.style_name,
                    "samples": [
                        {
                            "index": sample.sample_index,
                            "official_url": sample.url,
                            "github_url": build_raw_asset_url(raw_base_url, config.asset_dir_name, sample.filename),
                            "filename": sample.filename,
                        }
                        for sample in style.samples
                    ],
                }
                for style in character.styles
            ],
        }
        for character in catalog
    ]
    catalog_path.write_text(json.dumps(serializable_catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    return catalog_path


def rewrite_mapping_urls_to_github(mapping: dict, raw_base_url: str, asset_dir_name: str) -> dict:
    rewritten = json.loads(json.dumps(mapping, ensure_ascii=False))
    for character_data in rewritten.values():
        for entries in (character_data.get("voices") or {}).values():
            for entry in entries:
                entry["official_url"] = entry.get("url", "")
                entry["url"] = build_raw_asset_url(raw_base_url, asset_dir_name, str(entry.get("filename") or ""))
                entry["source"] = "github_voicevox_official_cache"
    return rewritten


def build_raw_github_base_url(repository: str, branch: str = "main") -> str:
    owner_repo = repository.strip().removeprefix("https://github.com/").removesuffix(".git").strip("/")
    return f"https://raw.githubusercontent.com/{owner_repo}/{quote(branch.strip(), safe='')}"


def build_raw_asset_url(raw_base_url: str, asset_dir_name: str, filename: str) -> str:
    encoded_asset_dir = "/".join(quote(part, safe="") for part in asset_dir_name.strip("/").split("/") if part)
    encoded_filename = quote(filename, safe="")
    return f"{raw_base_url.rstrip('/')}/{encoded_asset_dir}/{encoded_filename}"


def ensure_github_repository(config: GitHubVoicevoxSampleUploadConfig, log: LogFunc) -> None:
    if not config.create_repo_if_missing:
        return
    result = run_command(["gh", "repo", "view", config.repository], cwd=Path.cwd(), check=False)
    if result.returncode == 0:
        return
    visibility_arg = "--private" if config.visibility.lower() == "private" else "--public"
    log(f"[実行] GitHub repo作成: {config.repository} visibility={config.visibility}")
    run_command(
        [
            "gh",
            "repo",
            "create",
            config.repository,
            visibility_arg,
            "--description",
            "VOICEVOX official sample audio cache for direct browser playback",
        ],
        cwd=Path.cwd(),
    )


def ensure_local_asset_repository(config: GitHubVoicevoxSampleUploadConfig, log: LogFunc) -> None:
    config.local_repo_dir.mkdir(parents=True, exist_ok=True)
    git_dir = config.local_repo_dir / ".git"
    if not git_dir.exists():
        log(f"[実行] ローカルasset repo初期化: {config.local_repo_dir}")
        run_command(["git", "init", "-b", config.branch], cwd=config.local_repo_dir)
    remote_result = run_command(["git", "remote", "get-url", "origin"], cwd=config.local_repo_dir, check=False)
    remote_url = f"https://github.com/{config.repository}.git"
    if remote_result.returncode != 0:
        run_command(["git", "remote", "add", "origin", remote_url], cwd=config.local_repo_dir)
    elif remote_url not in remote_result.stdout:
        run_command(["git", "remote", "set-url", "origin", remote_url], cwd=config.local_repo_dir)
    gitignore = config.local_repo_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("__pycache__/\n*.py[cod]\n.DS_Store\nThumbs.db\n", encoding="utf-8")


def commit_and_push_asset_repository(config: GitHubVoicevoxSampleUploadConfig, log: LogFunc) -> None:
    status = run_command(["git", "status", "--porcelain"], cwd=config.local_repo_dir)
    if not status.stdout.strip():
        log("[結果] GitHub asset repo変更なし")
        return
    run_command(["git", "add", "."], cwd=config.local_repo_dir)
    run_command(["git", "commit", "-m", config.commit_message], cwd=config.local_repo_dir)
    log(f"[実行] GitHub asset repo push: {config.repository}/{config.branch}")
    run_command(["git", "push", "-u", "origin", config.branch], cwd=config.local_repo_dir)


def run_command(command: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    if shutil.which(command[0]) is None:
        raise RuntimeError(f"command not found: {command[0]}")
    result = subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"command failed: {' '.join(command)}\n{detail}")
    return result
