# シンプルコメビュ

NDGR の標準 `downloadBackwardComments()` は `chat` / `overflowed_chat` だけを `NDGRComment` に変換し、それ以外の `gift`、`nicoad`、`simple_notification` などを無視する。

このラボアプリは、NDGR の `PackedSegment.messages` に入っている `ChunkedMessage` を直接読み、取れる message 種別を全部表示・保存するための検証用コメビュ。

## 目的

- 通常コメント
- 184コメント
- overflowed / forwarded comment
- ギフト
- ニコニ広告
- 運営通知系
- タグ更新
- モデレーター更新
- その他 NDGR が返す message 種別

これらを捨てずに一覧化する。

## 操作

- `接続`: 現在放送中の番組に接続して、以後流れてくるNDGR messageを追加表示する。
- `全件取得`: Backward APIから過去分をまとめて取得する。
- `停止`: 接続中または取得中の処理を止め、取れている分を保存する。

## 参考メモ

`docs/special_user_gui_concept.html` には、投稿側の参考実装として Chrome 拡張「ニコ生コメビュ」v0.3.4 を参考にしたメモがある。

ただし、このラボアプリは NCV でも Chrome 拡張でもなく、NDGR の protobuf を直接読む。

このラボ内の `reference.html` に、参考対象と NDGR message 種別をまとめてある。

## 起動

```bat
start.cmd
```

または:

```powershell
..\..\.venv\Scripts\python.exe app.py
```

実際はリポジトリ直下の `.venv` を使う想定。

## ログ

ログレベルは UI で選べる。

- `INFO`: 取得開始、ページ取得、集計、保存先
- `DEBUG`: URI、ページ単位の詳細、種別集計
- `TRACE`: 1メッセージごとの raw 要約

大量コメントで `TRACE` にすると当然ログ量は増える。通常は `INFO` か `DEBUG` で見る。
