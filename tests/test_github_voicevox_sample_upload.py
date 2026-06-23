from __future__ import annotations

import unittest
from pathlib import Path

from app.infra.github_assets.voicevox_sample_upload import (
    GitHubVoicevoxSampleUploadConfig,
    build_raw_asset_url,
    build_raw_github_base_url,
    rewrite_mapping_urls_to_github,
    write_official_sample_catalog_files,
)
from app.infra.voicevox_samples.official_catalog import parse_official_voicevox_sample_catalog


class GitHubVoicevoxSampleUploadTests(unittest.TestCase):
    def test_raw_github_url_builder_encodes_branch_and_filename(self) -> None:
        base = build_raw_github_base_url("youzoom64/voicevox-sample-cache", "main")

        self.assertEqual(
            "https://raw.githubusercontent.com/youzoom64/voicevox-sample-cache/main/voicevox_official_samples/%E5%9B%9B%E5%9B%BD.wav",
            build_raw_asset_url(base, "voicevox_official_samples", "四国.wav"),
        )

    def test_write_catalog_files_rewrites_direct_mapping_to_github_urls(self) -> None:
        from tempfile import TemporaryDirectory

        document = """
        <astro-island component-export="default" props="{&quot;audioSamples&quot;:[1,[[0,{&quot;style&quot;:[0,&quot;ノーマル&quot;],&quot;urls&quot;:[1,[[0,&quot;/_astro/test-normal-001.wav&quot;]]]}]]],&quot;characterName&quot;:[0,&quot;テスト話者&quot;]}"></astro-island>
        """
        catalog = parse_official_voicevox_sample_catalog(document)
        with TemporaryDirectory() as temp_dir:
            config = GitHubVoicevoxSampleUploadConfig(
                repository="youzoom64/voicevox-sample-cache",
                local_repo_dir=Path(temp_dir),
            )
            catalog_path = write_official_sample_catalog_files(config, catalog)
            mapping_text = (Path(temp_dir) / "voice_mapping_direct.json").read_text(encoding="utf-8")

        self.assertEqual("voicevox_official_samples.json", catalog_path.name)
        self.assertIn("github_voicevox_official_cache", mapping_text)
        self.assertIn("raw.githubusercontent.com/youzoom64/voicevox-sample-cache", mapping_text)

    def test_rewrite_mapping_urls_to_github_preserves_official_url(self) -> None:
        mapping = {
            "テスト話者": {
                "voices": {
                    "ノーマル": [
                        {
                            "url": "https://voicevox.hiroshiba.jp/_astro/test.wav",
                            "filename": "test.wav",
                        }
                    ]
                }
            }
        }

        rewritten = rewrite_mapping_urls_to_github(mapping, "https://raw.githubusercontent.com/o/r/main", "samples")

        entry = rewritten["テスト話者"]["voices"]["ノーマル"][0]
        self.assertEqual("https://voicevox.hiroshiba.jp/_astro/test.wav", entry["official_url"])
        self.assertEqual("https://raw.githubusercontent.com/o/r/main/samples/test.wav", entry["url"])


if __name__ == "__main__":
    unittest.main()
