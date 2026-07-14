from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QSlider, QSpinBox, QTabWidget, QTextEdit, QVBoxLayout, QWidget

from app.core.config import AppConfig
from app.gui.common.combo_box import NoWheelComboBox
from app.gui.common.error_notice import show_error_notice
from app.gui.common.font_combo import FontFamilyCombo
from app.gui.common.github_skin_picker import select_github_skin
from app.gui.common.voicevox_style_combo import VoicevoxStyleCombo
from app.services.chrome_debug import get_profiles
from app.settings.store import JsonSettingsStore


class BasicSettingsTab(QWidget):
    config_saved = pyqtSignal(object)

    def __init__(self, store: JsonSettingsStore, config: AppConfig) -> None:
        super().__init__()
        self.store = store
        self.config = config
        self.loading_config = False
        self.read_aloud_input = QCheckBox("基本設定で読み上げる")
        self.voicevox_base_url_input = QLineEdit()
        self.voicevox_timeout_input = QDoubleSpinBox()
        self.voicevox_timeout_input.setRange(1.0, 120.0)
        self.voicevox_timeout_input.setSingleStep(1.0)
        self.voicevox_worker_count_input = QSpinBox()
        self.voicevox_worker_count_input.setRange(1, 16)
        self.voicevox_style_input = VoicevoxStyleCombo()
        allow_combo_shrink(self.voicevox_style_input)
        self.reload_speakers_button = QPushButton("VOICEVOX話者を再読込")
        self.voice_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.voice_volume_slider.setRange(0, 200)
        self.voice_volume_slider.setSingleStep(5)
        self.voice_volume_slider.setPageStep(10)
        self.voice_volume_label = QLabel("100%")
        self.skin_path_input = QLineEdit()
        self.skin_github_button = QPushButton("GitHub")
        self.skin_browse_button = QPushButton("ローカル")
        self.skin_width_input = QSpinBox()
        self.skin_width_input.setRange(1, 4096)
        self.skin_height_input = QSpinBox()
        self.skin_height_input.setRange(1, 512)
        self.font_family_input = FontFamilyCombo()
        allow_combo_shrink(self.font_family_input)
        self.font_size_input = QSpinBox()
        self.font_size_input.setRange(6, 128)
        self.font_color_input = QLineEdit()
        self.speed_base_input = QDoubleSpinBox()
        self.speed_base_input.setRange(0.1, 10.0)
        self.speed_base_input.setDecimals(2)
        self.speed_base_input.setSingleStep(0.05)
        self.speed_first_queue_input = QDoubleSpinBox()
        self.speed_first_queue_input.setRange(0.1, 10.0)
        self.speed_first_queue_input.setDecimals(2)
        self.speed_first_queue_input.setSingleStep(0.05)
        self.speed_max_input = QDoubleSpinBox()
        self.speed_max_input.setRange(0.1, 10.0)
        self.speed_max_input.setDecimals(2)
        self.speed_max_input.setSingleStep(0.1)
        self.list_background_path_input = QLineEdit()
        self.list_background_browse_button = QPushButton("参照")
        self.list_background_opacity_input = QSlider(Qt.Orientation.Horizontal)
        self.list_background_opacity_input.setRange(0, 100)
        self.list_background_opacity_label = QLabel("")
        self.list_show_icons_input = QCheckBox("アイコンを表示")
        self.list_icon_size_input = QSpinBox()
        self.list_icon_size_input.setRange(12, 128)
        self.list_name_width_input = QSlider(Qt.Orientation.Horizontal)
        self.list_name_width_input.setRange(40, 600)
        self.list_name_width_input.setSingleStep(5)
        self.list_name_width_input.setPageStep(20)
        self.list_name_width_label = QLabel("")
        self.list_font_family_input = FontFamilyCombo()
        allow_combo_shrink(self.list_font_family_input)
        self.list_name_font_size_input = QComboBox()
        self.list_text_font_size_input = QComboBox()
        allow_combo_shrink(self.list_name_font_size_input)
        allow_combo_shrink(self.list_text_font_size_input)
        for size in list_font_size_options():
            self.list_name_font_size_input.addItem(str(size), size)
            self.list_text_font_size_input.addItem(str(size), size)
        self.list_name_color_input = QLineEdit()
        self.list_text_color_input = QLineEdit()
        self.list_row_background_color_input = QLineEdit()
        self.list_row_background_opacity_input = QSlider(Qt.Orientation.Horizontal)
        self.list_row_background_opacity_input.setRange(0, 100)
        self.list_row_background_opacity_label = QLabel("")
        self.list_row_gap_input = QSpinBox()
        self.list_row_gap_input.setRange(0, 80)
        self.list_max_rows_input = QSpinBox()
        self.list_max_rows_input.setRange(1, 80)
        self.ai_reply_enabled_input = QCheckBox("AI返信フックを使う")
        self.ai_reply_rules_input = QTextEdit()
        self.ai_reply_rules_input.setPlaceholderText("1行1ルール。例: おはよう=>おはようございます / 初見=>初見さんいらっしゃい")
        self.ai_reply_rules_input.setFixedHeight(120)
        self.ai_reply_trigger_prefix_input = QLineEdit()
        self.ai_reply_trigger_prefix_input.setPlaceholderText("例: >AI")
        self.ai_reply_timeout_input = QDoubleSpinBox()
        self.ai_reply_timeout_input.setRange(0.0, 3600.0)
        self.ai_reply_timeout_input.setSingleStep(10.0)
        self.ai_reply_model_input = QLineEdit()
        self.ai_reply_model_input.setPlaceholderText("空ならCodex既定")
        self.ai_reply_effort_input = QLineEdit()
        self.ai_reply_effort_input.setPlaceholderText("例: low / medium / high。空ならCodex既定")
        self.tag_change_enabled_input = QCheckBox("コメントでタグ変更する")
        self.tag_change_rules_input = QTextEdit()
        self.tag_change_rules_input.setPlaceholderText("1行1ルール。例: タグ変えて=>雑談,ゲーム,初見歓迎")
        self.tag_change_rules_input.setFixedHeight(120)
        self.tag_change_headless_input = QCheckBox("Seleniumを非表示で実行")
        self.tag_change_chrome_profile_input = QComboBox()
        allow_combo_shrink(self.tag_change_chrome_profile_input)
        self.tag_change_reload_profiles_button = QPushButton("再読込")
        self.tag_change_timeout_input = QDoubleSpinBox()
        self.tag_change_timeout_input.setRange(10.0, 180.0)
        self.tag_change_timeout_input.setSingleStep(5.0)
        self.youtube_accept_enabled_input = QCheckBox("YouTube動画受付モード")
        self.youtube_chrome_profile_input = NoWheelComboBox()
        allow_combo_shrink(self.youtube_chrome_profile_input)
        self.youtube_reload_profiles_button = QPushButton("再読込")
        self.voice_transcript_auto_broadcasters_input = QTextEdit()
        self.voice_transcript_auto_broadcasters_input.setPlaceholderText("放送者IDまたは放送者名を1行1件で入力。例:\n12345678\n配信者名")
        self.voice_transcript_auto_broadcasters_input.setFixedHeight(120)
        self.save_button = QPushButton("保存")
        self.status_label = QLabel("")
        self.list_auto_save_timer = QTimer(self)
        self.list_auto_save_timer.setSingleShot(True)
        self.list_auto_save_timer.setInterval(250)
        self._build_layout()
        self._connect()
        self.load_config(config)
        self.reload_speakers()

    def _build_layout(self) -> None:
        tabs = QTabWidget()
        tabs.addTab(self._build_response_tab(), "基本応答")
        tabs.addTab(self._build_speed_tab(), "再生速度")
        tabs.addTab(self._build_list_overlay_tab(), "通常リスト")
        tabs.addTab(self._build_ai_reply_tab(), "AI返信")
        tabs.addTab(self._build_voice_transcript_tab(), "文字起こし")
        tabs.addTab(self._build_tag_change_tab(), "タグ変更")
        tabs.addTab(self._build_youtube_accept_tab(), "YouTube受付")
        buttons = QHBoxLayout()
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.status_label, 1)
        layout = QVBoxLayout()
        layout.addWidget(tabs)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def _build_response_tab(self) -> QWidget:
        form = QFormLayout()
        form.addRow("", self.read_aloud_input)
        form.addRow("VOICEVOX URL", self.voicevox_base_url_input)
        form.addRow("VOICEVOX timeout秒", self.voicevox_timeout_input)
        form.addRow("VOICEVOX worker数", self.voicevox_worker_count_input)
        style_row = QHBoxLayout()
        style_row.addWidget(self.voicevox_style_input, 1)
        style_row.addWidget(self.reload_speakers_button)
        form.addRow("基本VOICEVOX話者", style_row)
        volume_row = QHBoxLayout()
        volume_row.addWidget(self.voice_volume_slider, 1)
        volume_row.addWidget(self.voice_volume_label)
        form.addRow("読み上げ音量", volume_row)
        skin_row = QHBoxLayout()
        skin_row.addWidget(self.skin_path_input, 1)
        skin_row.addWidget(self.skin_github_button)
        skin_row.addWidget(self.skin_browse_button)
        form.addRow("基本スキン", skin_row)
        form.addRow("基本スキン幅", self.skin_width_input)
        form.addRow("基本スキン高さ", self.skin_height_input)
        form.addRow("基本フォント", self.font_family_input)
        form.addRow("基本フォントサイズ", self.font_size_input)
        form.addRow("基本フォント色", self.font_color_input)
        widget = QWidget()
        widget.setLayout(form)
        return widget

    def _build_speed_tab(self) -> QWidget:
        form = QFormLayout()
        form.addRow("待機0件の倍率", self.speed_base_input)
        form.addRow("待機1件時の倍率", self.speed_first_queue_input)
        form.addRow("最大倍率", self.speed_max_input)
        note = QLabel("読む直前のキュー件数で倍率を決める。例: 1件時1.1なら 1.1 / 1.2 / 1.3")
        note.setWordWrap(True)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch(1)
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _build_tag_change_tab(self) -> QWidget:
        form = QFormLayout()
        form.addRow("", self.tag_change_enabled_input)
        form.addRow("タグ変更ルール", self.tag_change_rules_input)
        form.addRow("", self.tag_change_headless_input)
        profile_row = QHBoxLayout()
        profile_row.addWidget(self.tag_change_chrome_profile_input, 1)
        profile_row.addWidget(self.tag_change_reload_profiles_button)
        form.addRow("Chromeアカウント", profile_row)
        form.addRow("Selenium timeout秒", self.tag_change_timeout_input)
        note = QLabel("コメントにキーワードが含まれたら、Seleniumで放送ページを開いてタグ編集UIを操作する。")
        note.setWordWrap(True)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch(1)
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _build_ai_reply_tab(self) -> QWidget:
        form = QFormLayout()
        form.addRow("", self.ai_reply_enabled_input)
        form.addRow("個別反応ルール", self.ai_reply_rules_input)
        form.addRow("AI呼び出し接頭辞", self.ai_reply_trigger_prefix_input)
        form.addRow("Codex timeout秒 (0=なし)", self.ai_reply_timeout_input)
        form.addRow("Codex model", self.ai_reply_model_input)
        form.addRow("Codex effort", self.ai_reply_effort_input)
        note = QLabel("キーワード一致、または接頭辞で始まるコメントにCodexで返信を作り、同じセッション履歴を保存して投稿する。")
        note.setWordWrap(True)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch(1)
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _build_voice_transcript_tab(self) -> QWidget:
        form = QFormLayout()
        form.addRow("自動紐づけ放送者", self.voice_transcript_auto_broadcasters_input)
        note = QLabel("ここに設定した放送者IDまたは放送者名に一致した現在放送中タブは、「文字起こし紐づけ」が自動ONになる。手動ON/OFFは各放送タブのチェックボックスで行う。")
        note.setWordWrap(True)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch(1)
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _build_youtube_accept_tab(self) -> QWidget:
        form = QFormLayout()
        form.addRow("", self.youtube_accept_enabled_input)
        profile_row = QHBoxLayout()
        profile_row.addWidget(self.youtube_chrome_profile_input, 1)
        profile_row.addWidget(self.youtube_reload_profiles_button)
        form.addRow("Chromeアカウント", profile_row)
        note = QLabel("有効中、最初に流れたYouTube URLだけをSelenium Chromeで開く。以後は受付リセットまで無視する。")
        note.setWordWrap(True)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch(1)
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _build_list_overlay_tab(self) -> QWidget:
        form = QFormLayout()
        background_row = QHBoxLayout()
        background_row.addWidget(self.list_background_path_input, 1)
        background_row.addWidget(self.list_background_browse_button)
        form.addRow("背景画像", background_row)
        background_opacity_row = QHBoxLayout()
        background_opacity_row.addWidget(self.list_background_opacity_input, 1)
        background_opacity_row.addWidget(self.list_background_opacity_label)
        form.addRow("背景透明度", background_opacity_row)
        form.addRow("", self.list_show_icons_input)
        form.addRow("アイコンサイズ", self.list_icon_size_input)
        name_width_row = QHBoxLayout()
        name_width_row.addWidget(self.list_name_width_input, 1)
        name_width_row.addWidget(self.list_name_width_label)
        form.addRow("名前幅", name_width_row)
        form.addRow("フォント", self.list_font_family_input)
        form.addRow("名前サイズ", self.list_name_font_size_input)
        form.addRow("本文サイズ", self.list_text_font_size_input)
        form.addRow("名前色", self.list_name_color_input)
        form.addRow("本文色", self.list_text_color_input)
        form.addRow("行背景色", self.list_row_background_color_input)
        row_opacity_row = QHBoxLayout()
        row_opacity_row.addWidget(self.list_row_background_opacity_input, 1)
        row_opacity_row.addWidget(self.list_row_background_opacity_label)
        form.addRow("行背景透明度", row_opacity_row)
        form.addRow("行間", self.list_row_gap_input)
        form.addRow("最大行数", self.list_max_rows_input)
        note = QLabel("このタブの変更は自動保存され、OBS の /list 表示へ約1秒以内に反映する。")
        note.setWordWrap(True)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(note)
        layout.addStretch(1)
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def _connect(self) -> None:
        self.reload_speakers_button.clicked.connect(self.reload_speakers)
        self.tag_change_reload_profiles_button.clicked.connect(self.reload_chrome_profiles)
        self.youtube_reload_profiles_button.clicked.connect(self.reload_youtube_chrome_profiles)
        self.skin_github_button.clicked.connect(self.select_github_skin)
        self.skin_browse_button.clicked.connect(self.browse_skin)
        self.list_background_browse_button.clicked.connect(self.browse_list_background)
        self.list_auto_save_timer.timeout.connect(self.save_config)
        self._connect_list_realtime_save()
        self.voice_volume_slider.valueChanged.connect(self.update_voice_volume_label)
        self.save_button.clicked.connect(self.save_config)

    def _connect_list_realtime_save(self) -> None:
        self.list_background_path_input.textChanged.connect(self.schedule_list_auto_save)
        self.list_background_opacity_input.valueChanged.connect(self.update_list_background_opacity_label)
        self.list_background_opacity_input.valueChanged.connect(self.schedule_list_auto_save)
        self.list_show_icons_input.toggled.connect(self.schedule_list_auto_save)
        self.list_icon_size_input.valueChanged.connect(self.schedule_list_auto_save)
        self.list_name_width_input.valueChanged.connect(self.update_list_name_width_label)
        self.list_name_width_input.valueChanged.connect(self.schedule_list_auto_save)
        self.list_font_family_input.currentTextChanged.connect(self.schedule_list_auto_save)
        self.list_name_font_size_input.currentIndexChanged.connect(self.schedule_list_auto_save)
        self.list_text_font_size_input.currentIndexChanged.connect(self.schedule_list_auto_save)
        self.list_name_color_input.textChanged.connect(self.schedule_list_auto_save)
        self.list_text_color_input.textChanged.connect(self.schedule_list_auto_save)
        self.list_row_background_color_input.textChanged.connect(self.schedule_list_auto_save)
        self.list_row_background_opacity_input.valueChanged.connect(self.update_list_row_background_opacity_label)
        self.list_row_background_opacity_input.valueChanged.connect(self.schedule_list_auto_save)
        self.list_row_gap_input.valueChanged.connect(self.schedule_list_auto_save)
        self.list_max_rows_input.valueChanged.connect(self.schedule_list_auto_save)

    def schedule_list_auto_save(self) -> None:
        if self.loading_config:
            return
        self.list_auto_save_timer.start()

    def load_config(self, config: AppConfig) -> None:
        self.loading_config = True
        self.config = config
        try:
            self.read_aloud_input.setChecked(config.default_read_aloud_enabled)
            self.voicevox_base_url_input.setText(config.voicevox_base_url)
            self.voicevox_timeout_input.setValue(float(config.voicevox_timeout_seconds))
            self.voicevox_worker_count_input.setValue(int(config.voicevox_worker_count))
            self.voicevox_style_input.set_current_style_id(config.default_voicevox_style)
            self.voice_volume_slider.setValue(int(round(float(config.voice_volume_scale) * 100)))
            self.update_voice_volume_label(self.voice_volume_slider.value())
            self.skin_path_input.setText(config.skin_path)
            self.skin_width_input.setValue(int(config.skin_width))
            self.skin_height_input.setValue(int(config.skin_height))
            self.font_family_input.set_current_font_family(config.font_family)
            self.font_size_input.setValue(int(config.font_size))
            self.font_color_input.setText(config.font_color)
            self.speed_base_input.setValue(float(config.voice_speed_base_scale))
            self.speed_first_queue_input.setValue(float(config.voice_speed_first_queue_scale))
            self.speed_max_input.setValue(float(config.voice_speed_max_scale))
            self.list_background_path_input.setText(config.list_background_path)
            self.list_background_opacity_input.setValue(opacity_to_slider(config.list_background_opacity))
            self.update_list_background_opacity_label(self.list_background_opacity_input.value())
            self.list_show_icons_input.setChecked(bool(config.list_show_icons))
            self.list_icon_size_input.setValue(int(config.list_icon_size))
            self.list_name_width_input.setValue(int(config.list_name_width))
            self.update_list_name_width_label(int(config.list_name_width))
            self.list_font_family_input.set_current_font_family(config.list_font_family)
            set_combo_int(self.list_name_font_size_input, int(config.list_name_font_size))
            set_combo_int(self.list_text_font_size_input, int(config.list_text_font_size))
            self.list_name_color_input.setText(config.list_name_color)
            self.list_text_color_input.setText(config.list_text_color)
            self.list_row_background_color_input.setText(config.list_row_background_color)
            self.list_row_background_opacity_input.setValue(opacity_to_slider(config.list_row_background_opacity))
            self.update_list_row_background_opacity_label(self.list_row_background_opacity_input.value())
            self.list_row_gap_input.setValue(int(config.list_row_gap))
            self.list_max_rows_input.setValue(int(config.list_max_rows))
            self.ai_reply_enabled_input.setChecked(bool(config.ai_reply_enabled))
            self.ai_reply_rules_input.setPlainText(config.ai_reply_rules or config.ai_reply_keywords)
            self.ai_reply_trigger_prefix_input.setText(config.ai_reply_trigger_prefix)
            self.ai_reply_timeout_input.setValue(float(config.ai_reply_timeout_seconds))
            self.ai_reply_model_input.setText(config.ai_reply_model)
            self.ai_reply_effort_input.setText(config.ai_reply_effort)
            self.tag_change_enabled_input.setChecked(bool(config.tag_change_enabled))
            self.tag_change_rules_input.setPlainText(config.tag_change_rules)
            self.tag_change_headless_input.setChecked(bool(config.tag_change_headless))
            self.reload_chrome_profiles(config.tag_change_chrome_profile)
            self.tag_change_timeout_input.setValue(float(config.tag_change_timeout_seconds))
            self.youtube_accept_enabled_input.setChecked(bool(config.youtube_accept_enabled))
            self.reload_youtube_chrome_profiles(config.youtube_chrome_profile or config.tag_change_chrome_profile)
            self.voice_transcript_auto_broadcasters_input.setPlainText(config.voice_transcript_auto_broadcasters)
        finally:
            self.loading_config = False

    def browse_skin(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "基本スキンを選択",
            self.skin_path_input.text().strip() or "",
            "Image Files (*.png *.jpg *.jpeg *.webp *.gif);;All Files (*)",
        )
        if path:
            self.skin_path_input.setText(path)

    def select_github_skin(self) -> None:
        skin_url = select_github_skin(self.skin_path_input.text().strip(), self)
        if skin_url:
            self.skin_path_input.setText(skin_url)

    def browse_list_background(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "通常リスト背景を選択",
            self.list_background_path_input.text().strip() or "",
            "Image Files (*.png *.jpg *.jpeg *.webp *.gif);;All Files (*)",
        )
        if path:
            self.list_background_path_input.setText(path)

    def update_voice_volume_label(self, value: int) -> None:
        self.voice_volume_label.setText(f"{int(value)}%")

    def update_list_name_width_label(self, value: int) -> None:
        self.list_name_width_label.setText(f"{int(value)}px")

    def update_list_background_opacity_label(self, value: int) -> None:
        self.list_background_opacity_label.setText(f"{int(value)}%")

    def update_list_row_background_opacity_label(self, value: int) -> None:
        self.list_row_background_opacity_label.setText(f"{int(value)}%")

    def reload_speakers(self) -> None:
        try:
            count = self.voicevox_style_input.reload_from_engine(
                self.voicevox_base_url_input.text().strip() or "http://127.0.0.1:50021",
                float(self.voicevox_timeout_input.value()),
                self.voicevox_style_input.current_style_id(),
            )
        except Exception as exc:
            self.voicevox_style_input.add_fallback_items()
            self.voicevox_style_input.set_current_style_id(self.config.default_voicevox_style)
            self.status_label.setText("VOICEVOX話者読込失敗")
            show_error_notice(self, "VOICEVOX話者読込エラー", exc)
            return
        self.status_label.setText(f"VOICEVOX話者読込: {count}件")

    def reload_chrome_profiles(self, selected_profile: str = "") -> None:
        current = selected_profile or self.current_tag_change_chrome_profile()
        self.tag_change_chrome_profile_input.clear()
        try:
            profiles = get_profiles()
        except Exception as exc:
            self.status_label.setText("Chromeアカウント読込失敗")
            show_error_notice(self, "Chromeアカウント読込エラー", exc)
            return
        for profile in profiles:
            profile_dir = str(profile.get("profile_dir") or "")
            email = str(profile.get("email") or "(未ログイン)")
            name = str(profile.get("name") or "")
            label = f"{profile_dir} / {email}"
            if name:
                label = f"{label} / {name}"
            self.tag_change_chrome_profile_input.addItem(label, profile_dir)
        if current:
            index = self.tag_change_chrome_profile_input.findData(current)
            if index >= 0:
                self.tag_change_chrome_profile_input.setCurrentIndex(index)
        self.status_label.setText(f"Chromeアカウント読込: {len(profiles)}件")

    def reload_youtube_chrome_profiles(self, selected_profile: str = "") -> None:
        current = selected_profile or self.current_youtube_chrome_profile()
        self.youtube_chrome_profile_input.clear()
        try:
            profiles = get_profiles()
        except Exception as exc:
            self.status_label.setText("YouTubeアカウント読込失敗")
            show_error_notice(self, "YouTubeアカウント読込エラー", exc)
            return
        for profile in profiles:
            profile_dir = str(profile.get("profile_dir") or "")
            email = str(profile.get("email") or "(未ログイン)")
            name = str(profile.get("name") or "")
            label = f"{profile_dir} / {email}"
            if name:
                label = f"{label} / {name}"
            self.youtube_chrome_profile_input.addItem(label, profile_dir)
        if current:
            index = self.youtube_chrome_profile_input.findData(current)
            if index >= 0:
                self.youtube_chrome_profile_input.setCurrentIndex(index)
        self.status_label.setText(f"YouTube Chromeアカウント読込: {len(profiles)}件")

    def current_tag_change_chrome_profile(self) -> str:
        value = self.tag_change_chrome_profile_input.currentData()
        return str(value or "")

    def current_youtube_chrome_profile(self) -> str:
        value = self.youtube_chrome_profile_input.currentData()
        return str(value or "")

    def save_config(self) -> None:
        data = self.config.to_dict()
        data.update(
            {
                "voicevox_base_url": self.voicevox_base_url_input.text().strip() or "http://127.0.0.1:50021",
                "voicevox_timeout_seconds": float(self.voicevox_timeout_input.value()),
                "voicevox_worker_count": int(self.voicevox_worker_count_input.value()),
                "default_read_aloud_enabled": self.read_aloud_input.isChecked(),
                "default_voicevox_speaker": "",
                "default_voicevox_style": self.voicevox_style_input.current_style_id(),
                "voice_volume_scale": float(self.voice_volume_slider.value()) / 100.0,
                "skin_path": self.skin_path_input.text().strip() or "assets/skin_5.png",
                "skin_width": int(self.skin_width_input.value()),
                "skin_height": int(self.skin_height_input.value()),
                "font_family": self.font_family_input.current_font_family() or "Yu Gothic UI",
                "font_size": int(self.font_size_input.value()),
                "font_color": self.font_color_input.text().strip() or "#ffffff",
                "voice_speed_base_scale": float(self.speed_base_input.value()),
                "voice_speed_first_queue_scale": float(self.speed_first_queue_input.value()),
                "voice_speed_max_scale": float(self.speed_max_input.value()),
                "list_background_path": self.list_background_path_input.text().strip(),
                "list_background_opacity": slider_to_opacity(self.list_background_opacity_input.value()),
                "list_show_icons": self.list_show_icons_input.isChecked(),
                "list_icon_size": int(self.list_icon_size_input.value()),
                "list_name_width": int(self.list_name_width_input.value()),
                "list_font_family": self.list_font_family_input.current_font_family() or "Yu Gothic UI",
                "list_name_font_size": combo_int(self.list_name_font_size_input, 20),
                "list_text_font_size": combo_int(self.list_text_font_size_input, 22),
                "list_name_color": self.list_name_color_input.text().strip() or "#8fd3ff",
                "list_text_color": self.list_text_color_input.text().strip() or "#ffffff",
                "list_row_background_color": self.list_row_background_color_input.text().strip() or "#000000",
                "list_row_background_opacity": slider_to_opacity(self.list_row_background_opacity_input.value()),
                "list_row_gap": int(self.list_row_gap_input.value()),
                "list_max_rows": int(self.list_max_rows_input.value()),
                "ai_reply_enabled": self.ai_reply_enabled_input.isChecked(),
                "ai_reply_keywords": self.ai_reply_rules_input.toPlainText().strip(),
                "ai_reply_rules": self.ai_reply_rules_input.toPlainText().strip(),
                "ai_reply_trigger_prefix": self.ai_reply_trigger_prefix_input.text().strip() or ">AI",
                "ai_reply_timeout_seconds": float(self.ai_reply_timeout_input.value()),
                "ai_reply_model": self.ai_reply_model_input.text().strip(),
                "ai_reply_effort": self.ai_reply_effort_input.text().strip(),
                "tag_change_enabled": self.tag_change_enabled_input.isChecked(),
                "tag_change_rules": self.tag_change_rules_input.toPlainText().strip(),
                "tag_change_headless": self.tag_change_headless_input.isChecked(),
                "tag_change_timeout_seconds": float(self.tag_change_timeout_input.value()),
                "tag_change_chrome_profile": self.current_tag_change_chrome_profile(),
                "youtube_accept_enabled": self.youtube_accept_enabled_input.isChecked(),
                "youtube_chrome_profile": self.current_youtube_chrome_profile(),
                "voice_transcript_auto_broadcasters": self.voice_transcript_auto_broadcasters_input.toPlainText().strip(),
            }
        )
        self.config = AppConfig.from_dict(data)
        self.store.save_config(self.config)
        self.status_label.setText("保存済み")
        self.config_saved.emit(self.config)


def list_font_size_options() -> list[int]:
    return [10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 36, 40, 44, 48, 56, 64, 72, 84, 96]


def set_combo_int(combo: QComboBox, value: int) -> None:
    index = combo.findData(int(value))
    if index < 0:
        combo.addItem(str(int(value)), int(value))
        index = combo.findData(int(value))
    combo.setCurrentIndex(index)


def combo_int(combo: QComboBox, default: int) -> int:
    try:
        return int(combo.currentData())
    except (TypeError, ValueError):
        return default


def allow_combo_shrink(combo: QComboBox) -> None:
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(0)
    combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)


def opacity_to_slider(value: float) -> int:
    return max(0, min(100, int(round(float(value) * 100))))


def slider_to_opacity(value: int) -> float:
    return max(0.0, min(1.0, float(value) / 100.0))
