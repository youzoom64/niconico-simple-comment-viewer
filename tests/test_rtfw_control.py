from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QGroupBox, QScrollArea
from PyQt6.QtTest import QTest

from app.core.config import AppConfig
from app.gui.common.font_combo import FontFamilyCombo
from app.gui.tabs.rtfw_control import RtfwControlTab
from app.gui.tabs import rtfw_control
from app.settings.store import JsonSettingsStore


class RtfwControlTabTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        store = JsonSettingsStore(Path(self.temp_dir.name) / "config.json")
        self.tab = RtfwControlTab(store, AppConfig(), auto_connect=False)

    def tearDown(self) -> None:
        self.tab.shutdown()
        self.tab.deleteLater()
        self.app.processEvents()
        self.temp_dir.cleanup()

    def test_has_three_explicit_capture_controls(self) -> None:
        self.assertEqual("マイク開始", self.tab.mic_button.text())
        self.assertEqual("PC音声開始", self.tab.pc_button.text())
        self.assertEqual("停止", self.tab.stop_button.text())
        self.assertEqual("RTFWサービスを再起動", self.tab.restart_service_button.text())

    def test_task_error_detail_is_not_written_into_layout_label(self) -> None:
        shown = []
        original = rtfw_control.show_error_notice
        rtfw_control.show_error_notice = lambda _parent, title, detail: shown.append((title, detail))
        try:
            self.tab.handle_task_failed("service:restart", "RtfwApiError: very long raw exception")
        finally:
            rtfw_control.show_error_notice = original

        self.assertEqual("操作失敗", self.tab.connection_label.text())
        self.assertNotIn("RtfwApiError", self.tab.connection_label.text())
        self.assertEqual([("RTFW操作エラー", "RtfwApiError: very long raw exception")], shown)

    def test_contains_nested_capture_style_and_filter_tabs(self) -> None:
        self.assertEqual(3, self.tab.inner_tabs.count())
        self.assertEqual("音声・推論", self.tab.inner_tabs.tabText(0))
        self.assertEqual("字幕表示", self.tab.inner_tabs.tabText(1))
        self.assertEqual("フィルター設定", self.tab.inner_tabs.tabText(2))
        self.assertIsInstance(self.tab.caption_style_tab.japanese_font, FontFamilyCombo)
        self.assertIsInstance(self.tab.caption_style_tab.english_font, FontFamilyCombo)
        self.assertEqual(62, self.tab.caption_style_tab.japanese_size.value())
        self.assertEqual(8, self.tab.caption_style_tab.caption_gap.value())
        self.assertEqual(5, self.tab.caption_style_tab.translation_gap.value())
        self.assertEqual(1.25, self.tab.caption_style_tab.japanese_line_height.value())
        self.assertEqual(1.2, self.tab.caption_style_tab.english_line_height.value())
        self.assertEqual(0, self.tab.caption_style_tab.position_offset_x.value())
        self.assertEqual(0, self.tab.caption_style_tab.position_offset_y.value())
        self.assertEqual(12, self.tab.caption_style_tab.block_padding_top.value())
        self.assertEqual(24, self.tab.caption_style_tab.block_padding_horizontal.value())
        self.assertEqual(14, self.tab.caption_style_tab.block_padding_bottom.value())
        self.assertEqual(5, self.tab.caption_style_tab.outline_width.value())
        self.assertEqual(9, self.tab.caption_style_tab.shadow_blur.value())
        self.assertTrue(self.tab.caption_style_tab.translation_enabled.isChecked())

    def test_caption_settings_scroll_without_hiding_actions(self) -> None:
        style = self.tab.caption_style_tab
        self.assertIsInstance(style.settings_scroll, QScrollArea)
        self.assertTrue(style.settings_scroll.widgetResizable())
        self.assertIs(style.settings_content, style.settings_scroll.widget())
        self.assertCountEqual(
            ["フォント（スキンと共通）", "配置と折返し", "色・縁取り・影", "英訳"],
            [box.title() for box in style.settings_content.findChildren(QGroupBox)],
        )
        self.assertTrue(style.settings_scroll.isAncestorOf(style.japanese_font))
        self.assertTrue(style.settings_scroll.isAncestorOf(style.translation_note))
        self.assertFalse(style.settings_scroll.isAncestorOf(style.reload_button))
        self.assertFalse(style.settings_scroll.isAncestorOf(style.save_button))
        self.assertFalse(style.settings_scroll.isAncestorOf(style.status_label))

        previous_index = self.tab.inner_tabs.currentIndex()
        signals_were_blocked = self.tab.inner_tabs.blockSignals(True)
        self.tab.inner_tabs.setCurrentIndex(1)
        self.tab.inner_tabs.blockSignals(signals_were_blocked)
        self.tab.resize(900, 300)
        self.tab.show()
        self.app.processEvents()

        scroll_bar = style.settings_scroll.verticalScrollBar()
        self.assertGreater(scroll_bar.maximum(), 0)
        scroll_bar.setValue(0)
        style.settings_scroll.ensureWidgetVisible(style.translation_note)
        self.app.processEvents()
        self.assertGreater(scroll_bar.value(), 0)
        self.assertTrue(style.reload_button.isVisible())
        self.assertTrue(style.save_button.isVisible())
        self.assertLessEqual(style.reload_button.geometry().bottom(), style.rect().bottom())
        self.assertLess(style.minimumSizeHint().height(), 200)
        self.assertLess(self.tab.minimumSizeHint().height(), 500)

        self.tab.hide()
        signals_were_blocked = self.tab.inner_tabs.blockSignals(True)
        self.tab.inner_tabs.setCurrentIndex(previous_index)
        self.tab.inner_tabs.blockSignals(signals_were_blocked)

    def test_filter_tab_search_enable_and_manual_order(self) -> None:
        filters = self.tab.caption_filter_tab
        filters.set_rules([
            {"id": "first", "enabled": True, "match_mode": "exact", "pattern": "ご視聴ありがとうございました"},
            {"id": "second", "enabled": False, "match_mode": "contains", "pattern": "テスト"},
        ])
        self.assertEqual(2, filters.table.rowCount())
        filters.search.setText("テスト")
        self.assertTrue(filters.table.isRowHidden(0))
        self.assertFalse(filters.table.isRowHidden(1))
        filters.search.clear()
        filters.table.selectRow(1)
        filters.move_rule(-1)
        self.assertEqual("second", filters.rules[0]["id"])
        self.assertFalse(filters.rules[0]["enabled"])
        self.assertTrue(filters.table.isSortingEnabled())

    def test_caption_gap_and_free_translation_are_sent_to_caption_api(self) -> None:
        class FakeCaptionClient:
            overlay = None
            translator = None

            def update_overlay(self, overlay):
                self.overlay = dict(overlay)
                return {"overlay": self.overlay}

            def update_translation(self, translator, ollama_model=""):
                self.translator = translator
                return {"translator": translator, "freeLibrary": "deep-translator"}

        fake = FakeCaptionClient()
        style = self.tab.caption_style_tab
        style.client = fake
        style.caption_gap.setValue(23)
        style.translation_gap.setValue(-8)
        style.japanese_line_height.setValue(1.0)
        style.english_line_height.setValue(0.9)
        style.position_offset_x.setValue(120)
        style.position_offset_y.setValue(-60)
        style.block_padding_top.setValue(3)
        style.block_padding_horizontal.setValue(7)
        style.block_padding_bottom.setValue(4)
        style.translation_enabled.setChecked(True)
        style.save()
        for _ in range(100):
            self.app.processEvents()
            if not style.threads:
                break
            QTest.qWait(10)
        self.assertEqual(23, fake.overlay["caption_gap"])
        self.assertEqual(-8, fake.overlay["translation_gap"])
        self.assertEqual(1.0, fake.overlay["japanese_line_height"])
        self.assertEqual(0.9, fake.overlay["english_line_height"])
        self.assertEqual(120, fake.overlay["position_offset_x"])
        self.assertEqual(-60, fake.overlay["position_offset_y"])
        self.assertEqual(3, fake.overlay["block_padding_top"])
        self.assertEqual(7, fake.overlay["block_padding_horizontal"])
        self.assertEqual(4, fake.overlay["block_padding_bottom"])
        self.assertEqual("google", fake.translator)

    def test_uses_shared_dropdowns_and_exposes_remote_model_and_vad_settings(self) -> None:
        self.assertEqual("NoWheelClosedComboBox", type(self.tab.mic_devices).__name__)
        self.assertEqual("NoWheelClosedComboBox", type(self.tab.pc_devices).__name__)
        self.assertEqual("NoWheelClosedComboBox", type(self.tab.model_combo).__name__)
        self.assertEqual("large-v3", self.tab.model_combo.currentData())
        self.assertEqual(-38.0, self.tab.threshold_dbfs.value())
        self.assertEqual(0.8, self.tab.silence_seconds.value())

    def test_remote_configuration_updates_visible_controls(self) -> None:
        self.tab.apply_runtime_configuration({
            "settings": {
                "model": "small",
                "compute_type": "int8",
                "language": "ja",
                "beam_size": 2,
                "threshold_dbfs": -31.5,
                "silence_seconds": 1.1,
                "min_duration_seconds": 0.5,
                "max_duration_seconds": 15.0,
                "pre_roll_seconds": 0.2,
                "partial_interval_seconds": 2.0,
                "enable_partials": False,
            }
        })
        self.assertEqual("small", self.tab.model_combo.currentData())
        self.assertEqual(-31.5, self.tab.threshold_dbfs.value())
        self.assertEqual(1.1, self.tab.silence_seconds.value())
        self.assertFalse(self.tab.enable_partials.isChecked())

    def test_final_transcript_event_updates_visible_text(self) -> None:
        self.tab.handle_event_payload({"schemaVersion": 1, "type": "transcript.final", "source": "pc", "text": "字幕テスト"})
        self.assertEqual("字幕テスト", self.tab.latest_text.toPlainText())

    def test_live_api_snapshot_and_state_event_update_status(self) -> None:
        self.tab.handle_event_payload({"type": "snapshot", "status": {"state": "stopped", "source": None}})
        self.assertIn("停止", self.tab.status_label.text())
        self.tab.handle_event_payload({"type": "state.changed", "state": "recording", "source": "mic"})
        self.assertIn("録音中", self.tab.status_label.text())
        self.assertIn("マイク", self.tab.status_label.text())

    def test_connection_settings_are_saved_without_starting_capture(self) -> None:
        self.tab.api_url_input.setText("http://localhost:9876")
        self.tab.overlay_url_input.setText("http://127.0.0.1:9877/")
        self.tab.apply_connection_settings()
        data = self.tab.store.load_dict()
        self.assertEqual("http://localhost:9876", data["rtfw_base_url"])
        self.assertEqual("http://127.0.0.1:9877/", data["rtfw_overlay_url"])
        self.assertIsNone(self.tab.current_status)


if __name__ == "__main__":
    unittest.main()
