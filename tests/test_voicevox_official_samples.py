from __future__ import annotations

import unittest

from app.infra.voicevox_samples.official_catalog import (
    build_direct_sample_mapping,
    flatten_official_voicevox_samples,
    parse_official_voicevox_sample_catalog,
)


class VoicevoxOfficialSamplesTests(unittest.TestCase):
    def test_parse_official_astro_audio_sample_props(self) -> None:
        document = """
        <astro-island component-export="default" props="{&quot;audioSamples&quot;:[1,[[0,{&quot;style&quot;:[0,&quot;ノーマル&quot;],&quot;urls&quot;:[1,[[0,&quot;/_astro/test-normal-001.wav&quot;],[0,&quot;/_astro/test-normal-002.wav&quot;],[0,&quot;/_astro/test-normal-003.wav&quot;]]]}],[0,{&quot;style&quot;:[0,&quot;ささやき&quot;],&quot;urls&quot;:[1,[[0,&quot;/_astro/test-whis-001.wav&quot;]]]}]]],&quot;characterName&quot;:[0,&quot;テスト話者&quot;]}"></astro-island>
        """

        catalog = parse_official_voicevox_sample_catalog(document, base_url="https://voicevox.hiroshiba.jp/")

        self.assertEqual(1, len(catalog))
        self.assertEqual("テスト話者", catalog[0].character_name)
        self.assertEqual(["ノーマル", "ささやき"], [style.style_name for style in catalog[0].styles])
        samples = flatten_official_voicevox_samples(catalog)
        self.assertEqual(4, len(samples))
        self.assertEqual(1, samples[0].sample_index)
        self.assertEqual("https://voicevox.hiroshiba.jp/_astro/test-normal-001.wav", samples[0].url)

    def test_build_direct_sample_mapping(self) -> None:
        document = """
        <astro-island component-export="default" props="{&quot;audioSamples&quot;:[1,[[0,{&quot;style&quot;:[0,&quot;ノーマル&quot;],&quot;urls&quot;:[1,[[0,&quot;/_astro/test-normal-001.wav&quot;]]]}]]],&quot;characterName&quot;:[0,&quot;テスト話者&quot;]}"></astro-island>
        """

        mapping = build_direct_sample_mapping(parse_official_voicevox_sample_catalog(document))

        entry = mapping["テスト話者"]["voices"]["ノーマル"][0]
        self.assertEqual("voicevox_official", entry["source"])
        self.assertEqual("https://voicevox.hiroshiba.jp/_astro/test-normal-001.wav", entry["url"])
        self.assertEqual("test-normal-001.wav", entry["filename"])


if __name__ == "__main__":
    unittest.main()
