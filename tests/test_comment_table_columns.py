from app.gui.comment_page import COMMENT_TABLE_COLUMNS, COMMENT_TABLE_STATE_KEY


def test_comment_table_default_columns_match_preferred_layout() -> None:
    assert COMMENT_TABLE_STATE_KEY == "comments_v2"
    assert COMMENT_TABLE_COLUMNS == [
        ("__icon__", "アイコン", 56),
        ("__display_name__", "名前", 53),
        ("no", "No", 70),
        ("content", "本文", 420),
        ("account_status", "状態", 90),
        ("user_id", "ユーザーID", 180),
        ("commands", "コマンド", 130),
        ("at", "投稿時刻", 180),
        ("raw_user_id", "raw", 140),
        ("kind", "種別", 90),
        ("vpos", "vpos", 90),
        ("hashed_user_id", "hash", 160),
        ("source", "source", 100),
        ("page_index", "page", 80),
    ]
