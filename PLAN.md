# Simple Comment Viewer Refactor Plan

この計画は `lab/simple_comment_viewer` の中だけを対象にする。
監視アプリ本体には手を出さない。

## 現状

- 旧GUI本体は `app.py` に残っている。
- `app.py` は300行まで分割済みで、GUI/Worker側の旧入口として残っている。
- `main.py` と `app/main/` は入口配線として作成済み。
- `app/` 以下に責務別ディレクトリの骨格を作成済み。
- まだ処理本体は新構造へ移していない。

## 目的

- `main.py` はアプリ全体の入口構造を示すだけにする。
- `app/main/` は dispatcher / registry / adapter / bridge に限定する。
- 処理本体は責務ごとの下位ディレクトリに置く。
- 1ファイルは300行から500行に収める。
- 500行を超える見込みが出たら、さらに責務を細分化して別ファイルへ分ける。

## フェーズ1: 入口配線

目的:

- アプリ入口を名前付きentrypointとして管理する。
- デフォルト入口を明示する。
- 将来入口の追加場所を示す。

対象:

- `main.py`
- `app/main/entrypoints.py`
- `app/main/dispatcher.py`
- `app/main/adapters.py`
- `app/main/help.py`

合格条件:

- `python main.py --help` が通る。
- `python main.py --list-entrypoints` が入口一覧を出す。
- `main.py` にGUI本体、DB処理、NDGR処理、OBS処理、VOICEVOX処理がない。
- `app/main/*.py` に処理本体がない。

## フェーズ2: 共通基盤

目的:

- ログ、パス、設定、ランタイム制御を共通化する。

対象:

- `app/core/logging.py`
- `app/core/config.py`
- `app/core/paths.py`
- `app/core/runtime.py`
- `app/settings/store.py`
- `app/settings/ui_state.py`

合格条件:

- ログは5段階に統一する。
- ログ出力箇所は分岐、実行、エラー、結果に限定する。
- 設定保存とGUI状態保存の入口が分かれている。
- 監視アプリ本体に依存しない。

## フェーズ3: DB基盤

目的:

- 全イベント保存を前提にDBスキーマを作る。

対象:

- `app/db/connection.py`
- `app/db/schema.py`
- `app/db/repositories/events.py`
- `app/db/repositories/profiles.py`
- `app/db/repositories/presets.py`

必要テーブル:

- raw events
- normalized events
- 生IDユーザープロファイル
- event_kind別プリセット
- 正規表現変換ルール
- VOICEVOX速度ルール

合格条件:

- raw payloadを失わない。
- 表示/読み上げ用に正規化した値も保存できる。
- DB保存は全イベントで必須として扱う。

## フェーズ4: NDGR受信

目的:

- 接続、全件取得、分類、DB保存の流れを一本化する。

対象:

- `app/ndgr/client.py`
- `app/ndgr/fetcher.py`
- `app/ndgr/streamer.py`
- `app/events/classifier.py`
- `app/events/normalizer.py`
- `app/events/pipeline.py`

合格条件:

- 通常コメント、184、生ID、主コメ、広告、ギフト、来場通知、ゲーム系、運営コメント、未知イベントを分類できる。
- unknownでもraw保存する。
- GUIに出すログはうるさくしない。
- CMD DEBUGには調査に必要な情報を出せる。

## フェーズ5: GUI基本ルール

目的:

- 監視アプリで使っていた基本GUIルールをコメビュへ移す。

対象:

- `app/gui/main_window.py`
- `app/gui/common/table_state.py`
- `app/gui/common/scroll_guard.py`
- `app/gui/common/context_menu.py`
- `app/gui/common/window_state.py`

合格条件:

- ウィンドウサイズを記憶する。
- カラム幅とカラム順序を記憶する。
- カラム移動ができる。
- 更新で縦横スクロールが飛ばない。
- 長文でウィンドウや表が横に壊れない。
- 右クリックコピーができる。

## フェーズ6: 生IDユーザー設定

目的:

- 生IDごとに演出プロファイルを登録できるようにする。

対象:

- `app/profiles/live_users.py`
- `app/gui/tabs/live_users.py`
- `app/db/repositories/profiles.py`

設定項目:

- 生ID
- 表示名
- スキン
- フォント
- VOICEVOXボイス
- 有効/無効

合格条件:

- 生IDコメントが来た時、そのユーザーのスキン、フォント、ボイスを解決できる。

## フェーズ7: 運営コマンド設定

目的:

- event_kindごとに音声ファイルと表示変換ルールを設定できるようにする。

対象:

- `app/profiles/event_presets.py`
- `app/gui/tabs/event_presets.py`
- `app/audio/sound_registry.py`
- `app/db/repositories/presets.py`

対象イベント:

- nicoad
- gift
- visitor
- operator_comment
- game
- system
- unknown

合格条件:

- event_kindごとに固定音声ファイルを選べる。
- payloadから表示文へ変換できる。
- 音声ファイル再生とVOICEVOX読み上げを混同しない。

## フェーズ8: 正規表現変換

目的:

- URL、www、888などを読み上げ前に変換する。

対象:

- `app/profiles/regex_rules.py`
- `app/voicevox/text_transform.py`

合格条件:

- ルールを複数登録できる。
- 適用対象をVOICEVOXのみ、OBSのみ、両方から選べる。
- 有効/無効を切り替えられる。

## フェーズ9: VOICEVOXキュー

目的:

- コメントを全部キューに入れ、3ワーカー程度でVOICEVOX生成する。

対象:

- `app/voicevox/queue.py`
- `app/voicevox/workers.py`
- `app/voicevox/speed_rules.py`

合格条件:

- コメントを取りこぼさない。
- 生成処理は複数ワーカーで捌ける。
- 最終的に流す順序はキューで制御する。
- 待機コメント数に応じて読み上げ速度を変えられる。

## フェーズ10: OBS透明HTML

目的:

- OBS Browser Source向けの透明HTMLを出す。

対象:

- `app/obs/overlay_server.py`
- `app/obs/renderer.py`
- `app/obs/animation.py`
- `app/obs/lanes.py`
- `app/obs/skins.py`

合格条件:

- 背景は透明。
- 横長スキンとフォントを同時に流せる。
- コメントは右から左へ減速移動する。
- 20秒ごとに一段上へ移動する。
- 新着コメントでも既存コメントが一段上へ移動する。
- スキン初期サイズは高さ32px、横51pxで、設定変更できる。

## フェーズ11: 統合

目的:

- NDGR受信からDB保存、GUI表示、OBS表示、音声再生までつなぐ。

流れ:

```text
NDGR受信
  -> raw DB保存
  -> event_kind分類
  -> 正規化DB保存
  -> 生IDプロファイル or event_kindプリセット解決
  -> GUI表示
  -> OBS HTML表示
  -> 固定音声/VOICEVOXキュー
```

合格条件:

- 通常コメントと運営コマンドが同じキューで詰まらない。
- 運営コマンドのSE再生中でもコメント読み上げを待たせない。
- GUIとOBSの表示が別責務として分かれている。

## フェーズ12: 検証とコミット

確認:

```powershell
python -m compileall -q main.py app tests tools
python -c "import main; import app.main.entrypoints"
python main.py --help
python main.py --list-entrypoints
```

コミット:

```powershell
git add .
git commit -m "日本語のコミットメッセージ"
```

完了報告:

- 入口一覧
- デフォルト入口
- 将来入口の追加場所
- `main.py` に処理本体がないこと
- `app/main/*.py` に処理本体がないこと
- 500行超えのファイルがある場合、その扱い
