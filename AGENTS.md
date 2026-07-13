# Simple Comment Viewer AGENTS.md

## 最重要

- このプロジェクトは `lab/simple_comment_viewer` のシンプルコメビュアプリで完結する。
- 監視アプリ本体には手を出さない。
- 親プロジェクトの都合で、コメビュ側の責務をぼかさない。
- 作業前に、このファイルと `DESIGN_MEMO.md` を読む。
- Git操作はこのディレクトリ内で行う。
- コミットするときは必ず `git add .` を使う。
- コミットメッセージは日本語にする。
- すべての読み書きはUTF-8で扱う。

## 介入API

- 介入APIはコメビュ機能の一部。起動cmdが親として一緒に起動する。
- 起動cmd上のGUIプロセス終了後に介入APIも停止する。
- GUI起動: `J:\utility\Niconico\niconico-simple-comment-viewer\start.cmd`
- API単体起動: `J:\utility\Niconico\niconico-simple-comment-viewer\start_intervention_api.cmd`
- URL: `http://127.0.0.1:8793`
- DB操作は直接SQLiteを書かず、原則このAPIを通す。
- 疎通確認: `GET /health`
- コメントNoから個人設定対象・過去コメント・本人アイコン確認: `GET /api/personal-settings/by-comment-no?no=551`
- コメントNoから個人設定保存: `POST /api/personal-settings/apply-by-comment-no`
- 監視アプリのスペシャルユーザー登録へ渡す: `POST /api/monitor/special-users/register-by-comment-no`

## この領域の責務

`app/main/` はアプリ起動入口の配線層である。

ここでいう「配線」とは、単に別関数へ丸投げすることではない。
アプリに存在する入口、将来追加される入口、入口ごとの責務境界を読める状態にすることを指す。

## 必須条件

- `main.py` はアプリ全体の入口構造を示す。
- GUI / tracker / CLI などの入口は、entrypointとして名前付きで管理する。
- デフォルト入口を明示する。
- 未実装の将来入口は、実行可能にせず、追加場所だけ分かる形で示す。
- 処理本体は `main.py` と `app/main/*.py` に置かない。
- `app/main/*.py` は dispatcher / registry / adapter / bridge の役割に限定する。
- 最初に `main.py` と配線先ディレクトリを作り、責務境界をファイル名で読める状態にする。
- 配線先でも責務が大きい場合は、さらに下位ディレクトリへ分ける。
- 中身は最初は空または薄いplaceholderでよい。先に構造を固定してから実装する。
- 1ファイルは300行から500行に収める。
- 500行を超えそうな場合は、実装前に責務を分割して別ファイルへ逃がす。
- 500行を超える見込みが出た時点で、その責務をさらに細分化し、下位ディレクトリや別スクリプトファイルへ分けて配置する。
- HTML資料、HTMLプレビュー、OBS表示検証用HTMLは500行ルールの対象外にする。
- HTMLは人間が読んで確認する成果物なので、無理に分割して見通しを悪くしない。

## 禁止

- `main.py` から単一の `main()` へ無説明で転送するだけの実装は禁止。
- GUI本体、tracker本体、DB処理、Selenium処理、録画処理を置くことは禁止。
- 「とりあえず呼ぶだけ」を配線完了扱いしてはいけない。
- 入口追加時に既存入口の責務を混ぜてはいけない。
- 500行を超えたファイルを「あとで分ける」と言って放置することは禁止。
- 複数責務を1ファイルに詰め込んで500行以内に収めたふりをすることは禁止。
- HTML資料やHTMLプレビューへ、実装スクリプト用の500行ルールを機械的に適用することは禁止。

## 合格例

```py
APP_DEFAULT_ENTRYPOINT = "gui"

APP_ENTRYPOINTS = {
    "gui": run_gui,
}

APP_FUTURE_ENTRYPOINTS = {
    "tracker": "planned",
    "cli": "planned",
}
```

## 不合格例

```py
from app.main.gui import main

if __name__ == "__main__":
    main()
```

理由:

これは入口構造を示していない。
単なる転送であり、配線層として不十分。

## 作業後確認

```powershell
python -m compileall -q main.py app tests tools
python -c "import main; import app.main.entrypoints"
python main.py --help
```

存在しないディレクトリがある場合は、その時点の構造に合わせて確認対象を調整する。
ただし、確認を省略した場合は完了報告で必ず言う。

## 完了報告に必ず含めること

- 入口一覧
- デフォルト入口
- 将来入口の追加場所
- `main.py` に処理本体がないこと
- `app/main/*.py` に処理本体がないこと
