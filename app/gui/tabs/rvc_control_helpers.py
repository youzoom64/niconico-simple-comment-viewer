from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QSpinBox, QWidget

from app.gui.common.qt_dropdown import current_dropdown_value, set_dropdown_value


RVC_CONNECTION_PRESETS = {
    "main": ("127.0.0.1", 18888),
    "local_worker": ("127.0.0.1", 8770),
}


class RvcControlHelpers:
    @staticmethod
    def _port_spin(value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(1, 65535)
        spin.setValue(value)
        return spin

    def _sync_connection_preset(self) -> None:
        endpoint = (self.worker_host_input.text().strip(), self.worker_port_input.value())
        preset = next((key for key, value in RVC_CONNECTION_PRESETS.items() if value == endpoint), "")
        if not preset:
            preset = "lan_worker" if endpoint[1] == 8770 else "custom"
        set_dropdown_value(self.connection_preset_combo, preset)
        self.start_mmvc_button.setEnabled(endpoint == RVC_CONNECTION_PRESETS["main"])

    def _connection_preset_selected(self, _index: int) -> None:
        preset = str(current_dropdown_value(self.connection_preset_combo) or "custom")
        if preset == "lan_worker":
            self.worker_port_input.setValue(8770)
            self.save_settings()
            return
        endpoint = RVC_CONNECTION_PRESETS.get(preset)
        if endpoint is None:
            return
        self._loading = True
        try:
            self.worker_host_input.setText(endpoint[0])
            self.worker_port_input.setValue(endpoint[1])
        finally:
            self._loading = False
        self.save_settings()
        self.run_action("refresh")

    def _current_model_slot(self) -> int | None:
        value = current_dropdown_value(self.model_combo)
        try:
            return int(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _browse_row(line_edit: QLineEdit, button: QPushButton) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(line_edit, 1)
        row.addWidget(button)
        return widget

    def _set_path(self, line_edit: QLineEdit, value: str) -> None:
        if value:
            line_edit.setText(value)
            self.save_settings()

    def _browse_mmvc(self) -> None:
        value, _ = QFileDialog.getOpenFileName(
            self,
            "MMVCServerSIO.exeを選択",
            self.mmvc_executable_input.text(),
            "MMVCServerSIO.exe (MMVCServerSIO.exe);;実行ファイル (*.exe)",
        )
        self._set_path(self.mmvc_executable_input, value)

    def _browse_transport(self) -> None:
        value = QFileDialog.getExistingDirectory(
            self,
            "音声制御サービスのフォルダを選択",
            self.transport_root_input.text(),
        )
        self._set_path(self.transport_root_input, value)

    def _browse_python(self) -> None:
        value, _ = QFileDialog.getOpenFileName(
            self,
            "Python実行ファイルを選択",
            self.python_executable_input.text(),
            "Python (python.exe pythonw.exe);;実行ファイル (*.exe)",
        )
        self._set_path(self.python_executable_input, value)

    def _browse_token(self) -> None:
        value, _ = QFileDialog.getOpenFileName(
            self,
            "LANトークン設定ファイルを選択",
            self.token_env_path_input.text(),
            "環境設定 (*.env);;すべてのファイル (*)",
        )
        self._set_path(self.token_env_path_input, value)

    @staticmethod
    def _replace_combo(combo: Any, items: list[tuple[str, Any]], selected: Any) -> None:
        target = list(items)
        if selected not in (None, "") and all(value != selected for _label, value in target):
            target.append((f"未検出: {selected}", selected))
        current_items = [(combo.itemText(index), combo.itemData(index)) for index in range(combo.count())]
        current_selected = current_dropdown_value(combo)
        same_selection = current_selected == selected or (
            current_selected in (None, "") and selected in (None, "")
        )
        if current_items == target and same_selection:
            return
        combo.clear()
        for label, value in target:
            combo.addItem(label, value)
        if selected not in (None, ""):
            set_dropdown_value(combo, selected)
        else:
            combo.setCurrentIndex(-1)

    def _obs_device_label(self, device_id: str) -> str:
        if not self.snapshot:
            return ""
        for source in self.snapshot.obs_inputs:
            for device in source.devices:
                if device.id == device_id:
                    return device.label
        return ""

    @staticmethod
    def _pipeline_text(pipeline: dict[str, Any]) -> str:
        if not pipeline:
            return "音声経路: 未確認"
        boundaries = pipeline.get("boundaries") if isinstance(pipeline.get("boundaries"), dict) else {}
        labels = (
            ("captured", "入力取得"),
            ("sent", "サブへ送信"),
            ("received", "サブから受信"),
            ("outputWritten", "選択デバイスへ出力"),
        )
        values: list[str] = []
        for key, label in labels:
            raw = boundaries.get(key) if isinstance(boundaries.get(key), dict) else {}
            frames = int(raw.get("frames") or 0)
            non_silent = int(raw.get("nonSilentFrames") or 0)
            peak = int(raw.get("lastPeak") or 0)
            values.append(f"{label} {frames}（非無音 {non_silent} / peak {peak}）")
        states = {
            "waiting_input": "入力待ち",
            "input_silent": "入力が無音",
            "send_blocked": "送信前で停止",
            "return_missing": "サブから未返却",
            "return_silent": "返却音声が無音",
            "output_blocked": "選択デバイスへの出力で停止",
            "output_silent": "選択デバイスへの出力が無音",
            "flowing": "4境界すべて非無音で進行",
        }
        state = states.get(str(pipeline.get("state") or ""), str(pipeline.get("state") or "未確認"))
        return f"音声経路: {state} / " + " / ".join(values)
