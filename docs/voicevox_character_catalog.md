# VOICEVOX キャラクター/スタイル一覧

生成日: 2026-07-08 20:49:52

## この資料の位置づけ

このアプリの個別設定で選ぶボイスは、VOICEVOX Engine のスタイルIDを `voicevox_style` として保存して使う。
この資料では、公式 VOICEVOX サイトから取得したキャラクター名、声質説明、公式サンプルURLと、ローカル VOICEVOX Engine の `GET /speakers` から取得した style_id を対応付けている。
アプリ内の `V3` や `V126` のような指定は、ここにある `Engine style_id` を指定する想定。

## 取得結果

- 公式参照元: https://voicevox.hiroshiba.jp/
- Engine URL: `http://127.0.0.1:50021`
- Engine: VOICEVOX / version `0.25.2`
- 公式キャラクター数: 43
- Engine話者数: 43
- 公式スタイル数: 127
- Engineスタイル数: 127
- 公式サンプル数: 381
- 声質説明取得数: 43
- Engine style_id 未対応数: 0

## アプリ側での扱い

- GUI のボイス選択は `GET /speakers` の返却値をフラット化して表示する。
- 実際の音声合成APIでは、引数名は `speaker` だが渡す値はキャラクターIDではなく style_id。
- 個別設定では、リスナーごとに `voicevox_speaker` と `voicevox_style` を保存する。現行実装では `voicevox_style` が優先される。
- デフォルト設定では `default_voicevox_style` が `3`。このEngineでは `ずんだもん / ノーマル`。

## 全体一覧

| No. | キャラクター | 声質説明 | speaker_uuid | スタイル数 | style_id一覧 |
| ---: | --- | --- | --- | ---: | --- |
| 1 | [四国めたん](https://voicevox.hiroshiba.jp/product/shikoku_metan/) | はっきりした芯のある声 | `7ffcb7ce-00ec-4bdc-82cd-45a8889e43ff` | 6 | ノーマル: 2, あまあま: 0, ツンツン: 6, セクシー: 4, ささやき: 36, ヒソヒソ: 37 |
| 2 | [ずんだもん](https://voicevox.hiroshiba.jp/product/zundamon/) | 子供っぽい高めの声 | `388f246b-8c41-4ac1-8e2d-5d79f3ff56d9` | 8 | ノーマル: 3, あまあま: 1, ツンツン: 7, セクシー: 5, ささやき: 22, ヒソヒソ: 38, ヘロヘロ: 75, なみだめ: 76 |
| 3 | [春日部つむぎ](https://voicevox.hiroshiba.jp/product/kasukabe_tsumugi/) | 元気な明るい声 | `35b2c544-660e-401e-b503-0e14c635303a` | 1 | ノーマル: 8 |
| 4 | [雨晴はう](https://voicevox.hiroshiba.jp/product/amehare_hau/) | 優しく可愛い声 | `3474ee95-c274-47f9-aa1a-8322163d96f1` | 1 | ノーマル: 10 |
| 5 | [波音リツ](https://voicevox.hiroshiba.jp/product/namine_ritsu/) | 低めのクールな声 | `b1a81618-b27b-40d2-b0ea-27a9ad408c4b` | 2 | ノーマル: 9, クイーン: 65 |
| 6 | [玄野武宏](https://voicevox.hiroshiba.jp/product/kurono_takehiro/) | 爽やかな青年の声 | `c30dc15a-0992-4f8d-8bb8-ad3b314e6a6f` | 4 | ノーマル: 11, 喜び: 39, ツンギレ: 40, 悲しみ: 41 |
| 7 | [白上虎太郎](https://voicevox.hiroshiba.jp/product/shirakami_kotarou/) | 声変わり直後の少年の声 | `e5020595-5c5d-4e87-b849-270a518d0dcf` | 5 | ふつう: 12, わーい: 32, おこ: 34, びくびく: 33, びえーん: 35 |
| 8 | [青山龍星](https://voicevox.hiroshiba.jp/product/aoyama_ryusei/) | 重厚で低音な声 | `4f51116a-d9ee-4516-925d-21f183e2afad` | 7 | ノーマル: 13, 熱血: 81, 不機嫌: 82, 喜び: 83, しっとり: 84, かなしみ: 85, 囁き: 86 |
| 9 | [冥鳴ひまり](https://voicevox.hiroshiba.jp/product/meimei_himari/) | 柔らかく温かい声 | `8eaad775-3119-417e-8cf4-2a10bfd592c8` | 1 | ノーマル: 14 |
| 10 | [九州そら](https://voicevox.hiroshiba.jp/product/kyushu_sora/) | 気品のある大人な声 | `481fb609-6446-4870-9f46-90c4dd623403` | 5 | ノーマル: 16, あまあま: 15, ツンツン: 18, セクシー: 17, ささやき: 19 |
| 11 | [もち子さん](https://voicevox.hiroshiba.jp/product/mochikosan/) | 明瞭で穏やかな声 | `9f3ee141-26ad-437e-97bd-d22298d02ad2` | 6 | ノーマル: 20, セクシー／あん子: 66, 泣き: 77, 怒り: 78, 喜び: 79, のんびり: 80 |
| 12 | [剣崎雌雄](https://voicevox.hiroshiba.jp/product/kenzaki_mesuo/) | 安心感のある落ち着いた声 | `1a17ca16-7ee5-4ea5-b191-2f02ace24d21` | 1 | ノーマル: 21 |
| 13 | [WhiteCUL](https://voicevox.hiroshiba.jp/product/white_cul/) | 聞き心地のよい率直な声 | `67d5d8da-acd7-4207-bb10-b5542d3a663b` | 4 | ノーマル: 23, たのしい: 24, かなしい: 25, びえーん: 26 |
| 14 | [後鬼](https://voicevox.hiroshiba.jp/product/goki/) | 包容力のある奥ゆかしい声 | `0f56c2f2-644c-49c9-8989-94e11f7129d0` | 4 | 人間ver.: 27, ぬいぐるみver.: 28, 人間（怒り）ver.: 87, 鬼ver.: 88 |
| 15 | [No.7](https://voicevox.hiroshiba.jp/product/number_seven/) | しっかりした凛々しい声 | `044830d2-f23b-44d6-ac0d-b5d733caa900` | 3 | ノーマル: 29, アナウンス: 30, 読み聞かせ: 31 |
| 16 | [ちび式じい](https://voicevox.hiroshiba.jp/product/chibishikiji/) | 親しみのある嗄れ声 | `468b8e94-9da4-4f7a-8715-a22a48844f9e` | 1 | ノーマル: 42 |
| 17 | [櫻歌ミコ](https://voicevox.hiroshiba.jp/product/ouka_miko/) | かわいらしい少女の声 | `0693554c-338e-4790-8982-b9c6d476dc69` | 3 | ノーマル: 43, 第二形態: 44, ロリ: 45 |
| 18 | [小夜/SAYO](https://voicevox.hiroshiba.jp/product/sayo/) | 和やかで温厚な声 | `a8cc6d22-aad0-4ab8-bf1e-2f843924164a` | 1 | ノーマル: 46 |
| 19 | [ナースロボ＿タイプＴ](https://voicevox.hiroshiba.jp/product/nurserobo_typet/) | 冷静で慎み深い声 | `882a636f-3bac-431a-966d-c5e6bba9f949` | 4 | ノーマル: 47, 楽々: 48, 恐怖: 49, 内緒話: 50 |
| 20 | [†聖騎士 紅桜†](https://voicevox.hiroshiba.jp/product/horinaito_benizakura/) | 快活でハキハキした声 | `471e39d2-fb11-4c8c-8d89-4b322d2498e0` | 1 | ノーマル: 51 |
| 21 | [雀松朱司](https://voicevox.hiroshiba.jp/product/wakamatsu_akashi/) | 物静かで安定した声 | `0acebdee-a4a5-4e12-a695-e19609728e30` | 1 | ノーマル: 52 |
| 22 | [麒ヶ島宗麟](https://voicevox.hiroshiba.jp/product/kigashima_sourin/) | 渋いおじさん声 | `7d1e7ba7-f957-40e5-a3fc-da49f769ab65` | 1 | ノーマル: 53 |
| 23 | [春歌ナナ](https://voicevox.hiroshiba.jp/product/haruka_nana/) | はつらつとした力強い声 | `ba5d2428-f7e0-4c20-ac41-9dd56e9178b4` | 1 | ノーマル: 54 |
| 24 | [猫使アル](https://voicevox.hiroshiba.jp/product/nekotsuka_aru/) | 厚みのある気さくな声 | `00a5c10c-d3bd-459f-83fd-43180b521a44` | 5 | ノーマル: 55, おちつき: 56, うきうき: 57, つよつよ: 110, へろへろ: 111 |
| 25 | [猫使ビィ](https://voicevox.hiroshiba.jp/product/nekotsuka_bi/) | ピュアであどけない声 | `c20a2254-0349-4470-9fc8-e5c0f8cf3404` | 4 | ノーマル: 58, おちつき: 59, 人見知り: 60, つよつよ: 112 |
| 26 | [中国うさぎ](https://voicevox.hiroshiba.jp/product/chugoku_usagi/) | 幽玄で初々しい声 | `1f18ffc3-47ea-4ce0-9829-0576d03a7ec8` | 4 | ノーマル: 61, おどろき: 62, こわがり: 63, へろへろ: 64 |
| 27 | [栗田まろん](https://voicevox.hiroshiba.jp/product/kurita_maron/) | 深みのある中性的な声 | `04dbd989-32d0-40b4-9e71-17c920f2a8a9` | 1 | ノーマル: 67 |
| 28 | [あいえるたん](https://voicevox.hiroshiba.jp/product/aierutan/) | 心地よい物柔らかな声 | `dda44ade-5f9c-4a3a-9d2c-2a976c7476d9` | 1 | ノーマル: 68 |
| 29 | [満別花丸](https://voicevox.hiroshiba.jp/product/manbetsu_hanamaru/) | 生き生きとした際立つ声 | `287aa49f-e56b-4530-a469-855776c84a8d` | 5 | ノーマル: 69, 元気: 70, ささやき: 71, ぶりっ子: 72, ボーイ: 73 |
| 30 | [琴詠ニア](https://voicevox.hiroshiba.jp/product/kotoyomi_nia/) | 滑らかで無機質な声 | `97a4af4b-086e-4efd-b125-7ae2da85e697` | 1 | ノーマル: 74 |
| 31 | [Voidoll](https://voicevox.hiroshiba.jp/product/voidoll/) | 慎ましやかで電子的な声 | `0ebe2c7d-96f3-4f0e-a2e3-ae13fe27c403` | 1 | ノーマル: 89 |
| 32 | [ぞん子](https://voicevox.hiroshiba.jp/product/zonko/) | 熱血的でありありとした声 | `0156da66-4300-474a-a398-49eb2e8dd853` | 4 | ノーマル: 90, 低血圧: 91, 覚醒: 92, 実況風: 93 |
| 33 | [中部つるぎ](https://voicevox.hiroshiba.jp/product/chubu_tsurugi/) | 凛然とした存在感のある声 | `4614a7de-9829-465d-9791-97eb8a5f9b86` | 5 | ノーマル: 94, 怒り: 95, ヒソヒソ: 96, おどおど: 97, 絶望と敗北: 98 |
| 34 | [離途](https://voicevox.hiroshiba.jp/product/rito/) | 包み込む息遣いな声 | `3b91e034-e028-4acb-a08d-fbdcd207ea63` | 2 | ノーマル: 99, シリアス: 101 |
| 35 | [黒沢冴白](https://voicevox.hiroshiba.jp/product/kurosawa_kohaku/) | 強気で張りのある声 | `0b466290-f9b6-4718-8d37-6c0c81e824ac` | 1 | ノーマル: 100 |
| 36 | [ユーレイちゃん](https://voicevox.hiroshiba.jp/product/yureichan/) | 柔和な揺蕩う声 | `462cd6b4-c088-42b0-b357-3816e24f112e` | 5 | ノーマル: 102, 甘々: 103, 哀しみ: 104, ささやき: 105, ツクモちゃん: 106 |
| 37 | [東北ずん子](https://voicevox.hiroshiba.jp/product/tohoku_zunko/) | しとやかで愛嬌のある声 | `80802b2d-8c75-4429-978b-515105017010` | 1 | ノーマル: 107 |
| 38 | [東北きりたん](https://voicevox.hiroshiba.jp/product/tohoku_kiritan/) | 淡麗でつづまやかな声 | `1bd6b32b-d650-4072-bbe5-1d0ef4aaa28b` | 1 | ノーマル: 108 |
| 39 | [東北イタコ](https://voicevox.hiroshiba.jp/product/tohoku_itako/) | 雅やかで余韻のある声 | `ab4c31a3-8769-422a-b412-708f5ae637e8` | 1 | ノーマル: 109 |
| 40 | [あんこもん](https://voicevox.hiroshiba.jp/product/ankomon/) | 抑えめで負けず嫌いな声 | `3be49e15-34bb-48a0-9e2f-9b80c96e9905` | 5 | ノーマル: 113, つよつよ: 114, よわよわ: 115, けだるげ: 116, ささやき: 117 |
| 41 | [夜語トバリ](https://voicevox.hiroshiba.jp/product/yogatari_tobari/) | 理知的で輪郭のある声 | `d3be2066-205b-47f6-8818-1d93a9ca9cef` | 4 | ノーマル: 118, 明るい: 119, 哀しみ: 120, 呆れ: 121 |
| 42 | [暁記ミタマ](https://voicevox.hiroshiba.jp/product/akatsuki_mitama/) | 儚げで浮遊感のある声 | `aca7de06-9ff9-49a3-9f08-9d3bc19689e5` | 4 | ノーマル: 122, 怒り: 123, 哀しみ: 124, ささやき: 125 |
| 43 | [里石ユカ](https://voicevox.hiroshiba.jp/product/satoishi_yuka/) | 開花スタイルは今後実装予定 | `cc7baa71-6c74-4399-803b-b60576176a08` | 1 | つぼみ: 126 |

## キャラクター別詳細

### 1. [四国めたん](https://voicevox.hiroshiba.jp/product/shikoku_metan/)

- 声質説明: はっきりした芯のある声
- speaker_uuid: `7ffcb7ce-00ec-4bdc-82cd-45a8889e43ff`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `SELF_ONLY`
- スタイル数: 6

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 2 | talk | [1](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-normal-001.D9FQX0-3.wav) [2](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-normal-002.B7UuYf3e.wav) [3](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-normal-003.BJPS0TKT.wav) |
| あまあま | 0 | talk | [1](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-ama-001.KKvbT7OM.wav) [2](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-ama-002.Nt-wEV5V.wav) [3](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-ama-003.CjtgfN57.wav) |
| ツンツン | 6 | talk | [1](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-tsun-001.GCrVVgJt.wav) [2](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-tsun-002.Dtcpq8Ij.wav) [3](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-tsun-003.klK43oj2.wav) |
| セクシー | 4 | talk | [1](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-sexy-001.rOtE_ZRW.wav) [2](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-sexy-002.BQDOpXyn.wav) [3](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-sexy-003.BxvqGdA8.wav) |
| ささやき | 36 | talk | [1](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-whis-001.ChD63mOT.wav) [2](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-whis-002.DlLa1nNM.wav) [3](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-whis-003.DJAtLH7S.wav) |
| ヒソヒソ | 37 | talk | [1](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-hiso-001.DUx1hQEm.wav) [2](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-hiso-002.O1huLp8G.wav) [3](https://voicevox.hiroshiba.jp/_astro/shikoku_metan-hiso-003.MYI0D3XY.wav) |

### 2. [ずんだもん](https://voicevox.hiroshiba.jp/product/zundamon/)

- 声質説明: 子供っぽい高めの声
- speaker_uuid: `388f246b-8c41-4ac1-8e2d-5d79f3ff56d9`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `SELF_ONLY`
- スタイル数: 8

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 3 | talk | [1](https://voicevox.hiroshiba.jp/_astro/zundamon-normal-001.DlxPrwB-.wav) [2](https://voicevox.hiroshiba.jp/_astro/zundamon-normal-002.kPSKU_VH.wav) [3](https://voicevox.hiroshiba.jp/_astro/zundamon-normal-003.BKjvVfSJ.wav) |
| あまあま | 1 | talk | [1](https://voicevox.hiroshiba.jp/_astro/zundamon-ama-001.CdtTsG9B.wav) [2](https://voicevox.hiroshiba.jp/_astro/zundamon-ama-002.BFarXSE_.wav) [3](https://voicevox.hiroshiba.jp/_astro/zundamon-ama-003.WxzmDG_P.wav) |
| ツンツン | 7 | talk | [1](https://voicevox.hiroshiba.jp/_astro/zundamon-tsun-001.CTIZb6DG.wav) [2](https://voicevox.hiroshiba.jp/_astro/zundamon-tsun-002.BtBSwxw1.wav) [3](https://voicevox.hiroshiba.jp/_astro/zundamon-tsun-003.D77rQ-o_.wav) |
| セクシー | 5 | talk | [1](https://voicevox.hiroshiba.jp/_astro/zundamon-sexy-001.BxRHwP5J.wav) [2](https://voicevox.hiroshiba.jp/_astro/zundamon-sexy-002.D_5j0pTM.wav) [3](https://voicevox.hiroshiba.jp/_astro/zundamon-sexy-003.6rAajlHp.wav) |
| ささやき | 22 | talk | [1](https://voicevox.hiroshiba.jp/_astro/zundamon-whis-001.AzNBvU4F.wav) [2](https://voicevox.hiroshiba.jp/_astro/zundamon-whis-002.BcayvpjD.wav) [3](https://voicevox.hiroshiba.jp/_astro/zundamon-whis-003.B-D47CxC.wav) |
| ヒソヒソ | 38 | talk | [1](https://voicevox.hiroshiba.jp/_astro/zundamon-hiso-001.BGNoTvtX.wav) [2](https://voicevox.hiroshiba.jp/_astro/zundamon-hiso-002.BM4wZNiE.wav) [3](https://voicevox.hiroshiba.jp/_astro/zundamon-hiso-003.DHoiWJf2.wav) |
| ヘロヘロ | 75 | talk | [1](https://voicevox.hiroshiba.jp/_astro/zundamon-herohero-001.BsFu9HLT.wav) [2](https://voicevox.hiroshiba.jp/_astro/zundamon-herohero-002.Dtscd8Pd.wav) [3](https://voicevox.hiroshiba.jp/_astro/zundamon-herohero-003.nzIexrrt.wav) |
| なみだめ | 76 | talk | [1](https://voicevox.hiroshiba.jp/_astro/zundamon-namidame-001.CfbdERVG.wav) [2](https://voicevox.hiroshiba.jp/_astro/zundamon-namidame-002.C96m58jO.wav) [3](https://voicevox.hiroshiba.jp/_astro/zundamon-namidame-003.C3fcrikP.wav) |

### 3. [春日部つむぎ](https://voicevox.hiroshiba.jp/product/kasukabe_tsumugi/)

- 声質説明: 元気な明るい声
- speaker_uuid: `35b2c544-660e-401e-b503-0e14c635303a`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 8 | talk | [1](https://voicevox.hiroshiba.jp/_astro/kasukabe_tsumugi-normal-001.BwyhSI7J.wav) [2](https://voicevox.hiroshiba.jp/_astro/kasukabe_tsumugi-normal-002.BVavXUVF.wav) [3](https://voicevox.hiroshiba.jp/_astro/kasukabe_tsumugi-normal-003.DYL_VA8c.wav) |

### 4. [雨晴はう](https://voicevox.hiroshiba.jp/product/amehare_hau/)

- 声質説明: 優しく可愛い声
- speaker_uuid: `3474ee95-c274-47f9-aa1a-8322163d96f1`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 10 | talk | [1](https://voicevox.hiroshiba.jp/_astro/amehare_hau-normal-001.DpTlIWjq.wav) [2](https://voicevox.hiroshiba.jp/_astro/amehare_hau-normal-002.DBSWo9Xo.wav) [3](https://voicevox.hiroshiba.jp/_astro/amehare_hau-normal-003.DTOtYKy_.wav) |

### 5. [波音リツ](https://voicevox.hiroshiba.jp/product/namine_ritsu/)

- 声質説明: 低めのクールな声
- speaker_uuid: `b1a81618-b27b-40d2-b0ea-27a9ad408c4b`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 2

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 9 | talk | [1](https://voicevox.hiroshiba.jp/_astro/namine_ritsu-normal-001.CgP7yWbM.wav) [2](https://voicevox.hiroshiba.jp/_astro/namine_ritsu-normal-002.CpK7ytjx.wav) [3](https://voicevox.hiroshiba.jp/_astro/namine_ritsu-normal-003.cD5mKJrx.wav) |
| クイーン | 65 | talk | [1](https://voicevox.hiroshiba.jp/_astro/namine_ritsu-queen-001.D37WV45p.wav) [2](https://voicevox.hiroshiba.jp/_astro/namine_ritsu-queen-002.DjVoZomE.wav) [3](https://voicevox.hiroshiba.jp/_astro/namine_ritsu-queen-003.DjZYNRSt.wav) |

### 6. [玄野武宏](https://voicevox.hiroshiba.jp/product/kurono_takehiro/)

- 声質説明: 爽やかな青年の声
- speaker_uuid: `c30dc15a-0992-4f8d-8bb8-ad3b314e6a6f`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 4

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 11 | talk | [1](https://voicevox.hiroshiba.jp/_astro/kurono_takehiro-normal-001.DrXPwsem.wav) [2](https://voicevox.hiroshiba.jp/_astro/kurono_takehiro-normal-002.C1b-3iv6.wav) [3](https://voicevox.hiroshiba.jp/_astro/kurono_takehiro-normal-003.D31F6SSq.wav) |
| 喜び | 39 | talk | [1](https://voicevox.hiroshiba.jp/_astro/kurono_takehiro-fun-001.BgjinPY4.wav) [2](https://voicevox.hiroshiba.jp/_astro/kurono_takehiro-fun-002.B86j7oau.wav) [3](https://voicevox.hiroshiba.jp/_astro/kurono_takehiro-fun-003.BHif1KaD.wav) |
| ツンギレ | 40 | talk | [1](https://voicevox.hiroshiba.jp/_astro/kurono_takehiro-angry-001.3YW08Nkm.wav) [2](https://voicevox.hiroshiba.jp/_astro/kurono_takehiro-angry-002.BMWClVNN.wav) [3](https://voicevox.hiroshiba.jp/_astro/kurono_takehiro-angry-003.CGGBiF_s.wav) |
| 悲しみ | 41 | talk | [1](https://voicevox.hiroshiba.jp/_astro/kurono_takehiro-sad-001.44h1EIw5.wav) [2](https://voicevox.hiroshiba.jp/_astro/kurono_takehiro-sad-002.BiQtHwaW.wav) [3](https://voicevox.hiroshiba.jp/_astro/kurono_takehiro-sad-003.BZhZdOGi.wav) |

### 7. [白上虎太郎](https://voicevox.hiroshiba.jp/product/shirakami_kotarou/)

- 声質説明: 声変わり直後の少年の声
- speaker_uuid: `e5020595-5c5d-4e87-b849-270a518d0dcf`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 5

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ふつう | 12 | talk | [1](https://voicevox.hiroshiba.jp/_astro/shirakami_kotarou-normal-001.UMB0FK_4.wav) [2](https://voicevox.hiroshiba.jp/_astro/shirakami_kotarou-normal-002.BGQ61Wee.wav) [3](https://voicevox.hiroshiba.jp/_astro/shirakami_kotarou-normal-003.Dl-Z4nQA.wav) |
| わーい | 32 | talk | [1](https://voicevox.hiroshiba.jp/_astro/shirakami_kotarou-joy-001.BCq5M9Nk.wav) [2](https://voicevox.hiroshiba.jp/_astro/shirakami_kotarou-joy-002.2ws_k8fT.wav) [3](https://voicevox.hiroshiba.jp/_astro/shirakami_kotarou-joy-003.uhGvTcr7.wav) |
| おこ | 34 | talk | [1](https://voicevox.hiroshiba.jp/_astro/shirakami_kotarou-angry-001.DQpGU7_h.wav) [2](https://voicevox.hiroshiba.jp/_astro/shirakami_kotarou-angry-002.CLRJANI5.wav) [3](https://voicevox.hiroshiba.jp/_astro/shirakami_kotarou-angry-003.DGNbZJtO.wav) |
| びくびく | 33 | talk | [1](https://voicevox.hiroshiba.jp/_astro/shirakami_kotarou-biku-001.CCU47fyl.wav) [2](https://voicevox.hiroshiba.jp/_astro/shirakami_kotarou-biku-002.DkgKgd5D.wav) [3](https://voicevox.hiroshiba.jp/_astro/shirakami_kotarou-biku-003.GsQyPXgg.wav) |
| びえーん | 35 | talk | [1](https://voicevox.hiroshiba.jp/_astro/shirakami_kotarou-cry-001.CFAXWf_G.wav) [2](https://voicevox.hiroshiba.jp/_astro/shirakami_kotarou-cry-002.CjuRoN82.wav) [3](https://voicevox.hiroshiba.jp/_astro/shirakami_kotarou-cry-003.BNQ8VyHX.wav) |

### 8. [青山龍星](https://voicevox.hiroshiba.jp/product/aoyama_ryusei/)

- 声質説明: 重厚で低音な声
- speaker_uuid: `4f51116a-d9ee-4516-925d-21f183e2afad`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 7

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 13 | talk | [1](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-normal-001.DBorMSZv.wav) [2](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-normal-002.BDwy398X.wav) [3](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-normal-003.Bp81_6i3.wav) |
| 熱血 | 81 | talk | [1](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-eager-001.D218lO0F.wav) [2](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-eager-002.DFZhmgH4.wav) [3](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-eager-003.B7DyOZzo.wav) |
| 不機嫌 | 82 | talk | [1](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-grumpy-001.BOSylGBS.wav) [2](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-grumpy-002.C-HxmKM9.wav) [3](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-grumpy-003.C-lPkmOk.wav) |
| 喜び | 83 | talk | [1](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-happy-001.DtJzbNJG.wav) [2](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-happy-002.JGwSaUOO.wav) [3](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-happy-003.qkxbmmVq.wav) |
| しっとり | 84 | talk | [1](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-mellow-001.cjr88y5t.wav) [2](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-mellow-002.f19yGSJ6.wav) [3](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-mellow-003.CyhR8blu.wav) |
| かなしみ | 85 | talk | [1](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-sad-001.DRBSnweL.wav) [2](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-sad-002.Ck829rBO.wav) [3](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-sad-003.B7re6DVx.wav) |
| 囁き | 86 | talk | [1](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-whisper-001.CqQO66NM.wav) [2](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-whisper-002.BVVHIV7J.wav) [3](https://voicevox.hiroshiba.jp/_astro/aoyama_ryusei-whisper-003.EbWKksjI.wav) |

### 9. [冥鳴ひまり](https://voicevox.hiroshiba.jp/product/meimei_himari/)

- 声質説明: 柔らかく温かい声
- speaker_uuid: `8eaad775-3119-417e-8cf4-2a10bfd592c8`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 14 | talk | [1](https://voicevox.hiroshiba.jp/_astro/meimei_himari-normal-001.D5oqbi3_.wav) [2](https://voicevox.hiroshiba.jp/_astro/meimei_himari-normal-002.D2FN91p9.wav) [3](https://voicevox.hiroshiba.jp/_astro/meimei_himari-normal-003.DnWtslWg.wav) |

### 10. [九州そら](https://voicevox.hiroshiba.jp/product/kyushu_sora/)

- 声質説明: 気品のある大人な声
- speaker_uuid: `481fb609-6446-4870-9f46-90c4dd623403`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `SELF_ONLY`
- スタイル数: 5

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 16 | talk | [1](https://voicevox.hiroshiba.jp/_astro/kyushu_sora-normal-001.Bon0IOOx.wav) [2](https://voicevox.hiroshiba.jp/_astro/kyushu_sora-normal-002.Bg2lfvwi.wav) [3](https://voicevox.hiroshiba.jp/_astro/kyushu_sora-normal-003.CGzGNW4z.wav) |
| あまあま | 15 | talk | [1](https://voicevox.hiroshiba.jp/_astro/kyushu_sora-ama-001.CnapkNlH.wav) [2](https://voicevox.hiroshiba.jp/_astro/kyushu_sora-ama-002.rk_iMjXr.wav) [3](https://voicevox.hiroshiba.jp/_astro/kyushu_sora-ama-003.BtQE5bFL.wav) |
| ツンツン | 18 | talk | [1](https://voicevox.hiroshiba.jp/_astro/kyushu_sora-tsun-001.BOdGXgkQ.wav) [2](https://voicevox.hiroshiba.jp/_astro/kyushu_sora-tsun-002.CT-ObLUt.wav) [3](https://voicevox.hiroshiba.jp/_astro/kyushu_sora-tsun-003.CGsplBu0.wav) |
| セクシー | 17 | talk | [1](https://voicevox.hiroshiba.jp/_astro/kyushu_sora-sexy-001.CZvZV7VM.wav) [2](https://voicevox.hiroshiba.jp/_astro/kyushu_sora-sexy-002.CwD-IsYk.wav) [3](https://voicevox.hiroshiba.jp/_astro/kyushu_sora-sexy-003.CKQNDoy3.wav) |
| ささやき | 19 | talk | [1](https://voicevox.hiroshiba.jp/_astro/kyushu_sora-whis-001.BMFHAWtw.wav) [2](https://voicevox.hiroshiba.jp/_astro/kyushu_sora-whis-002.DOy1PAmv.wav) [3](https://voicevox.hiroshiba.jp/_astro/kyushu_sora-whis-003.Lv0WVtYT.wav) |

### 11. [もち子さん](https://voicevox.hiroshiba.jp/product/mochikosan/)

- 声質説明: 明瞭で穏やかな声
- speaker_uuid: `9f3ee141-26ad-437e-97bd-d22298d02ad2`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `SELF_ONLY`
- スタイル数: 6

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 20 | talk | [1](https://voicevox.hiroshiba.jp/_astro/mochikosan-normal-001.3NwFJxH5.wav) [2](https://voicevox.hiroshiba.jp/_astro/mochikosan-normal-002.tfnV6L4m.wav) [3](https://voicevox.hiroshiba.jp/_astro/mochikosan-normal-003.rNoBeAQB.wav) |
| セクシー／あん子 | 66 | talk | [1](https://voicevox.hiroshiba.jp/_astro/mochikosan-sexy-001.Byp81nXy.wav) [2](https://voicevox.hiroshiba.jp/_astro/mochikosan-sexy-002.BNy8gF1Y.wav) [3](https://voicevox.hiroshiba.jp/_astro/mochikosan-sexy-003.C9qYNob8.wav) |
| 泣き | 77 | talk | [1](https://voicevox.hiroshiba.jp/_astro/mochikosan-cry-001.BSomxUoH.wav) [2](https://voicevox.hiroshiba.jp/_astro/mochikosan-cry-002.Cw0bbXdO.wav) [3](https://voicevox.hiroshiba.jp/_astro/mochikosan-cry-003.CcjofpZz.wav) |
| 怒り | 78 | talk | [1](https://voicevox.hiroshiba.jp/_astro/mochikosan-angry-001.Dwk8o9aD.wav) [2](https://voicevox.hiroshiba.jp/_astro/mochikosan-angry-002.ZoW4PIgd.wav) [3](https://voicevox.hiroshiba.jp/_astro/mochikosan-angry-003.D0ZGzE-y.wav) |
| 喜び | 79 | talk | [1](https://voicevox.hiroshiba.jp/_astro/mochikosan-joy-001.DYDSWo7z.wav) [2](https://voicevox.hiroshiba.jp/_astro/mochikosan-joy-002.CUb3DOHh.wav) [3](https://voicevox.hiroshiba.jp/_astro/mochikosan-joy-003.Du8qIBA3.wav) |
| のんびり | 80 | talk | [1](https://voicevox.hiroshiba.jp/_astro/mochikosan-relax-001.FB2oclPv.wav) [2](https://voicevox.hiroshiba.jp/_astro/mochikosan-relax-002.vfrqz9cg.wav) [3](https://voicevox.hiroshiba.jp/_astro/mochikosan-relax-003.DqT_iyJt.wav) |

### 12. [剣崎雌雄](https://voicevox.hiroshiba.jp/product/kenzaki_mesuo/)

- 声質説明: 安心感のある落ち着いた声
- speaker_uuid: `1a17ca16-7ee5-4ea5-b191-2f02ace24d21`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 21 | talk | [1](https://voicevox.hiroshiba.jp/_astro/kenzaki_mesuo-normal-001.BR4giqW7.wav) [2](https://voicevox.hiroshiba.jp/_astro/kenzaki_mesuo-normal-002.LkD0CLnH.wav) [3](https://voicevox.hiroshiba.jp/_astro/kenzaki_mesuo-normal-003.YfxmjtL0.wav) |

### 13. [WhiteCUL](https://voicevox.hiroshiba.jp/product/white_cul/)

- 声質説明: 聞き心地のよい率直な声
- speaker_uuid: `67d5d8da-acd7-4207-bb10-b5542d3a663b`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 4

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 23 | talk | [1](https://voicevox.hiroshiba.jp/_astro/white_cul-normal-001.9MPrFlt_.wav) [2](https://voicevox.hiroshiba.jp/_astro/white_cul-normal-002.D5IU_rJT.wav) [3](https://voicevox.hiroshiba.jp/_astro/white_cul-normal-003.Drtrlgky.wav) |
| たのしい | 24 | talk | [1](https://voicevox.hiroshiba.jp/_astro/white_cul-joy-001.BAa96ACt.wav) [2](https://voicevox.hiroshiba.jp/_astro/white_cul-joy-002.D5ovnvu5.wav) [3](https://voicevox.hiroshiba.jp/_astro/white_cul-joy-003.BvkVD-Xs.wav) |
| かなしい | 25 | talk | [1](https://voicevox.hiroshiba.jp/_astro/white_cul-sad-001.BAao_QT2.wav) [2](https://voicevox.hiroshiba.jp/_astro/white_cul-sad-002.D7FBx1yp.wav) [3](https://voicevox.hiroshiba.jp/_astro/white_cul-sad-003.BIBy0g_A.wav) |
| びえーん | 26 | talk | [1](https://voicevox.hiroshiba.jp/_astro/white_cul-cry-001.BG2K49F7.wav) [2](https://voicevox.hiroshiba.jp/_astro/white_cul-cry-002.CE6cfJmb.wav) [3](https://voicevox.hiroshiba.jp/_astro/white_cul-cry-003.hWqZ2DLI.wav) |

### 14. [後鬼](https://voicevox.hiroshiba.jp/product/goki/)

- 声質説明: 包容力のある奥ゆかしい声
- speaker_uuid: `0f56c2f2-644c-49c9-8989-94e11f7129d0`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 4

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| 人間ver. | 27 | talk | [1](https://voicevox.hiroshiba.jp/_astro/goki-normal-001.DyVxvlA3.wav) [2](https://voicevox.hiroshiba.jp/_astro/goki-normal-002.Cp1vH42k.wav) [3](https://voicevox.hiroshiba.jp/_astro/goki-normal-003.DNGZ0lAu.wav) |
| ぬいぐるみver. | 28 | talk | [1](https://voicevox.hiroshiba.jp/_astro/goki-nuigurumi-001.CaY6figA.wav) [2](https://voicevox.hiroshiba.jp/_astro/goki-nuigurumi-002.kg7oUQwS.wav) [3](https://voicevox.hiroshiba.jp/_astro/goki-nuigurumi-003.D-DudoSk.wav) |
| 人間（怒り）ver. | 87 | talk | [1](https://voicevox.hiroshiba.jp/_astro/goki-angry-001.-G63l_cd.wav) [2](https://voicevox.hiroshiba.jp/_astro/goki-angry-002.Bae8AVeD.wav) [3](https://voicevox.hiroshiba.jp/_astro/goki-angry-003.BOnAzB2Q.wav) |
| 鬼ver. | 88 | talk | [1](https://voicevox.hiroshiba.jp/_astro/goki-oni-001.BxEwLkN7.wav) [2](https://voicevox.hiroshiba.jp/_astro/goki-oni-002.ByJ0vmEQ.wav) [3](https://voicevox.hiroshiba.jp/_astro/goki-oni-003.BUmeIEHc.wav) |

### 15. [No.7](https://voicevox.hiroshiba.jp/product/number_seven/)

- 声質説明: しっかりした凛々しい声
- speaker_uuid: `044830d2-f23b-44d6-ac0d-b5d733caa900`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 3

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 29 | talk | [1](https://voicevox.hiroshiba.jp/_astro/number_seven-normal-001.BahX7GIQ.wav) [2](https://voicevox.hiroshiba.jp/_astro/number_seven-normal-002.OPv30o-e.wav) [3](https://voicevox.hiroshiba.jp/_astro/number_seven-normal-003.ds1JG_8N.wav) |
| アナウンス | 30 | talk | [1](https://voicevox.hiroshiba.jp/_astro/number_seven-announce-001.2glzAQjK.wav) [2](https://voicevox.hiroshiba.jp/_astro/number_seven-announce-002.NJ-8tJQw.wav) [3](https://voicevox.hiroshiba.jp/_astro/number_seven-announce-003.tHmA87q8.wav) |
| 読み聞かせ | 31 | talk | [1](https://voicevox.hiroshiba.jp/_astro/number_seven-reading-001.11m5tWib.wav) [2](https://voicevox.hiroshiba.jp/_astro/number_seven-reading-002.BNZIckXN.wav) [3](https://voicevox.hiroshiba.jp/_astro/number_seven-reading-003.Dwo8uSiN.wav) |

### 16. [ちび式じい](https://voicevox.hiroshiba.jp/product/chibishikiji/)

- 声質説明: 親しみのある嗄れ声
- speaker_uuid: `468b8e94-9da4-4f7a-8715-a22a48844f9e`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 42 | talk | [1](https://voicevox.hiroshiba.jp/_astro/chibishikiji-normal-001.DSVUU3d9.wav) [2](https://voicevox.hiroshiba.jp/_astro/chibishikiji-normal-002.C97NKDzP.wav) [3](https://voicevox.hiroshiba.jp/_astro/chibishikiji-normal-003.BJl7tbi4.wav) |

### 17. [櫻歌ミコ](https://voicevox.hiroshiba.jp/product/ouka_miko/)

- 声質説明: かわいらしい少女の声
- speaker_uuid: `0693554c-338e-4790-8982-b9c6d476dc69`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 3

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 43 | talk | [1](https://voicevox.hiroshiba.jp/_astro/ouka_miko-normal-001.oXjhcDJ0.wav) [2](https://voicevox.hiroshiba.jp/_astro/ouka_miko-normal-002.BJQ5IY2o.wav) [3](https://voicevox.hiroshiba.jp/_astro/ouka_miko-normal-003.CAA7YVAd.wav) |
| 第二形態 | 44 | talk | [1](https://voicevox.hiroshiba.jp/_astro/ouka_miko-2nd-001.DzN4usKR.wav) [2](https://voicevox.hiroshiba.jp/_astro/ouka_miko-2nd-002.BG_wz4OM.wav) [3](https://voicevox.hiroshiba.jp/_astro/ouka_miko-2nd-003.BhGfKEjv.wav) |
| ロリ | 45 | talk | [1](https://voicevox.hiroshiba.jp/_astro/ouka_miko-loli-001.4F3lpGvY.wav) [2](https://voicevox.hiroshiba.jp/_astro/ouka_miko-loli-002.CywujGLz.wav) [3](https://voicevox.hiroshiba.jp/_astro/ouka_miko-loli-003.BocPX_mC.wav) |

### 18. [小夜/SAYO](https://voicevox.hiroshiba.jp/product/sayo/)

- 声質説明: 和やかで温厚な声
- speaker_uuid: `a8cc6d22-aad0-4ab8-bf1e-2f843924164a`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 46 | talk | [1](https://voicevox.hiroshiba.jp/_astro/sayo-normal-001.CuUywNuw.wav) [2](https://voicevox.hiroshiba.jp/_astro/sayo-normal-002.tG60IxRK.wav) [3](https://voicevox.hiroshiba.jp/_astro/sayo-normal-003.Bka85fEl.wav) |

### 19. [ナースロボ＿タイプＴ](https://voicevox.hiroshiba.jp/product/nurserobo_typet/)

- 声質説明: 冷静で慎み深い声
- speaker_uuid: `882a636f-3bac-431a-966d-c5e6bba9f949`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 4

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 47 | talk | [1](https://voicevox.hiroshiba.jp/_astro/nurserobo_typet-normal-001.CXxGLTvZ.wav) [2](https://voicevox.hiroshiba.jp/_astro/nurserobo_typet-normal-002.CYzPGBqy.wav) [3](https://voicevox.hiroshiba.jp/_astro/nurserobo_typet-normal-003.C-tPKx2I.wav) |
| 楽々 | 48 | talk | [1](https://voicevox.hiroshiba.jp/_astro/nurserobo_typet-fun-001.D_RAnRET.wav) [2](https://voicevox.hiroshiba.jp/_astro/nurserobo_typet-fun-002.DYcLzRNy.wav) [3](https://voicevox.hiroshiba.jp/_astro/nurserobo_typet-fun-003.CRePgRF2.wav) |
| 恐怖 | 49 | talk | [1](https://voicevox.hiroshiba.jp/_astro/nurserobo_typet-fear-001.DlOi-upK.wav) [2](https://voicevox.hiroshiba.jp/_astro/nurserobo_typet-fear-002.DFYj9RVV.wav) [3](https://voicevox.hiroshiba.jp/_astro/nurserobo_typet-fear-003.CJ0-9XLq.wav) |
| 内緒話 | 50 | talk | [1](https://voicevox.hiroshiba.jp/_astro/nurserobo_typet-whis-001.M2dZbbJy.wav) [2](https://voicevox.hiroshiba.jp/_astro/nurserobo_typet-whis-002.DER0yqC7.wav) [3](https://voicevox.hiroshiba.jp/_astro/nurserobo_typet-whis-003.CB9DgAx3.wav) |

### 20. [†聖騎士 紅桜†](https://voicevox.hiroshiba.jp/product/horinaito_benizakura/)

- 声質説明: 快活でハキハキした声
- speaker_uuid: `471e39d2-fb11-4c8c-8d89-4b322d2498e0`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 51 | talk | [1](https://voicevox.hiroshiba.jp/_astro/horinaito_benizakura-normal-001.BKcpJfg4.wav) [2](https://voicevox.hiroshiba.jp/_astro/horinaito_benizakura-normal-002.CGs4sfOS.wav) [3](https://voicevox.hiroshiba.jp/_astro/horinaito_benizakura-normal-003.r84m2G0X.wav) |

### 21. [雀松朱司](https://voicevox.hiroshiba.jp/product/wakamatsu_akashi/)

- 声質説明: 物静かで安定した声
- speaker_uuid: `0acebdee-a4a5-4e12-a695-e19609728e30`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 52 | talk | [1](https://voicevox.hiroshiba.jp/_astro/wakamatsu_akashi-normal-001.DhfXzKmi.wav) [2](https://voicevox.hiroshiba.jp/_astro/wakamatsu_akashi-normal-002.CGLZyLYm.wav) [3](https://voicevox.hiroshiba.jp/_astro/wakamatsu_akashi-normal-003.DxKaToJd.wav) |

### 22. [麒ヶ島宗麟](https://voicevox.hiroshiba.jp/product/kigashima_sourin/)

- 声質説明: 渋いおじさん声
- speaker_uuid: `7d1e7ba7-f957-40e5-a3fc-da49f769ab65`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 53 | talk | [1](https://voicevox.hiroshiba.jp/_astro/kigashima_sourin-normal-001.eR4fqU3e.wav) [2](https://voicevox.hiroshiba.jp/_astro/kigashima_sourin-normal-002.CKthhz0s.wav) [3](https://voicevox.hiroshiba.jp/_astro/kigashima_sourin-normal-003.CH7o-s_d.wav) |

### 23. [春歌ナナ](https://voicevox.hiroshiba.jp/product/haruka_nana/)

- 声質説明: はつらつとした力強い声
- speaker_uuid: `ba5d2428-f7e0-4c20-ac41-9dd56e9178b4`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 54 | talk | [1](https://voicevox.hiroshiba.jp/_astro/haruka_nana-normal-001.Djz35eHj.wav) [2](https://voicevox.hiroshiba.jp/_astro/haruka_nana-normal-002.BX5gkL57.wav) [3](https://voicevox.hiroshiba.jp/_astro/haruka_nana-normal-003.ROg1yyuJ.wav) |

### 24. [猫使アル](https://voicevox.hiroshiba.jp/product/nekotsuka_aru/)

- 声質説明: 厚みのある気さくな声
- speaker_uuid: `00a5c10c-d3bd-459f-83fd-43180b521a44`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 5

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 55 | talk | [1](https://voicevox.hiroshiba.jp/_astro/nekotsuka_aru-normal-001.ChdMH455.wav) [2](https://voicevox.hiroshiba.jp/_astro/nekotsuka_aru-normal-002.CTAfp-W1.wav) [3](https://voicevox.hiroshiba.jp/_astro/nekotsuka_aru-normal-003.B8ap1iRq.wav) |
| おちつき | 56 | talk | [1](https://voicevox.hiroshiba.jp/_astro/nekotsuka_aru-ochitsuki-001.DZbsNpv3.wav) [2](https://voicevox.hiroshiba.jp/_astro/nekotsuka_aru-ochitsuki-002.KtsT7dCq.wav) [3](https://voicevox.hiroshiba.jp/_astro/nekotsuka_aru-ochitsuki-003.eeLtRUEi.wav) |
| うきうき | 57 | talk | [1](https://voicevox.hiroshiba.jp/_astro/nekotsuka_aru-fun-001.BAbw7K_4.wav) [2](https://voicevox.hiroshiba.jp/_astro/nekotsuka_aru-fun-002.fTl4L2o0.wav) [3](https://voicevox.hiroshiba.jp/_astro/nekotsuka_aru-fun-003.BOJuuT6d.wav) |
| つよつよ | 110 | talk | [1](https://voicevox.hiroshiba.jp/_astro/nekotsuka_aru-tsuyotsuyo-001.D62DVTjY.wav) [2](https://voicevox.hiroshiba.jp/_astro/nekotsuka_aru-tsuyotsuyo-002.CLL-lel9.wav) [3](https://voicevox.hiroshiba.jp/_astro/nekotsuka_aru-tsuyotsuyo-003.fQK0k7-4.wav) |
| へろへろ | 111 | talk | [1](https://voicevox.hiroshiba.jp/_astro/nekotsuka_aru-herohero-001.CYP1N5T6.wav) [2](https://voicevox.hiroshiba.jp/_astro/nekotsuka_aru-herohero-002.LihZQVlt.wav) [3](https://voicevox.hiroshiba.jp/_astro/nekotsuka_aru-herohero-003.CveDpagu.wav) |

### 25. [猫使ビィ](https://voicevox.hiroshiba.jp/product/nekotsuka_bi/)

- 声質説明: ピュアであどけない声
- speaker_uuid: `c20a2254-0349-4470-9fc8-e5c0f8cf3404`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 4

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 58 | talk | [1](https://voicevox.hiroshiba.jp/_astro/nekotsuka_bi-normal-001.BsAxW9BH.wav) [2](https://voicevox.hiroshiba.jp/_astro/nekotsuka_bi-normal-002.TuM75gnW.wav) [3](https://voicevox.hiroshiba.jp/_astro/nekotsuka_bi-normal-003.BYu3G7zm.wav) |
| おちつき | 59 | talk | [1](https://voicevox.hiroshiba.jp/_astro/nekotsuka_bi-ochitsuki-001.DL2P3JH6.wav) [2](https://voicevox.hiroshiba.jp/_astro/nekotsuka_bi-ochitsuki-002.BOQ3eRsf.wav) [3](https://voicevox.hiroshiba.jp/_astro/nekotsuka_bi-ochitsuki-003.BHaqGvTu.wav) |
| 人見知り | 60 | talk | [1](https://voicevox.hiroshiba.jp/_astro/nekotsuka_bi-shy-001.Bt_kThzx.wav) [2](https://voicevox.hiroshiba.jp/_astro/nekotsuka_bi-shy-002.A0GBuZjj.wav) [3](https://voicevox.hiroshiba.jp/_astro/nekotsuka_bi-shy-003.F35HM4Zp.wav) |
| つよつよ | 112 | talk | [1](https://voicevox.hiroshiba.jp/_astro/nekotsuka_bi-tsuyotsuyo-001.DHacAjeX.wav) [2](https://voicevox.hiroshiba.jp/_astro/nekotsuka_bi-tsuyotsuyo-002.Bn_wIMyw.wav) [3](https://voicevox.hiroshiba.jp/_astro/nekotsuka_bi-tsuyotsuyo-003.B9fpOqu-.wav) |

### 26. [中国うさぎ](https://voicevox.hiroshiba.jp/product/chugoku_usagi/)

- 声質説明: 幽玄で初々しい声
- speaker_uuid: `1f18ffc3-47ea-4ce0-9829-0576d03a7ec8`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `SELF_ONLY`
- スタイル数: 4

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 61 | talk | [1](https://voicevox.hiroshiba.jp/_astro/chugoku_usagi-normal-001.C3EN6jm8.wav) [2](https://voicevox.hiroshiba.jp/_astro/chugoku_usagi-normal-002.Brl_Vkzn.wav) [3](https://voicevox.hiroshiba.jp/_astro/chugoku_usagi-normal-003.DGudv14w.wav) |
| おどろき | 62 | talk | [1](https://voicevox.hiroshiba.jp/_astro/chugoku_usagi-surprise-001.BGhoJzvw.wav) [2](https://voicevox.hiroshiba.jp/_astro/chugoku_usagi-surprise-002.CYuKuGc3.wav) [3](https://voicevox.hiroshiba.jp/_astro/chugoku_usagi-surprise-003.B4VuBv_w.wav) |
| こわがり | 63 | talk | [1](https://voicevox.hiroshiba.jp/_astro/chugoku_usagi-fear-001.F_ssXqFX.wav) [2](https://voicevox.hiroshiba.jp/_astro/chugoku_usagi-fear-002.rZ1flEMg.wav) [3](https://voicevox.hiroshiba.jp/_astro/chugoku_usagi-fear-003.Bzb3om3K.wav) |
| へろへろ | 64 | talk | [1](https://voicevox.hiroshiba.jp/_astro/chugoku_usagi-tired-001.Bl6IHm9b.wav) [2](https://voicevox.hiroshiba.jp/_astro/chugoku_usagi-tired-002.o3G7PQxy.wav) [3](https://voicevox.hiroshiba.jp/_astro/chugoku_usagi-tired-003.BJ8_QQEs.wav) |

### 27. [栗田まろん](https://voicevox.hiroshiba.jp/product/kurita_maron/)

- 声質説明: 深みのある中性的な声
- speaker_uuid: `04dbd989-32d0-40b4-9e71-17c920f2a8a9`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 67 | talk | [1](https://voicevox.hiroshiba.jp/_astro/kurita_maron-normal-001.BnsdCAWe.wav) [2](https://voicevox.hiroshiba.jp/_astro/kurita_maron-normal-002.ZF-rFjND.wav) [3](https://voicevox.hiroshiba.jp/_astro/kurita_maron-normal-003.DMSlkdFA.wav) |

### 28. [あいえるたん](https://voicevox.hiroshiba.jp/product/aierutan/)

- 声質説明: 心地よい物柔らかな声
- speaker_uuid: `dda44ade-5f9c-4a3a-9d2c-2a976c7476d9`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 68 | talk | [1](https://voicevox.hiroshiba.jp/_astro/aierutan-normal-001.B0uhQfzg.wav) [2](https://voicevox.hiroshiba.jp/_astro/aierutan-normal-002.Bdj-lrYT.wav) [3](https://voicevox.hiroshiba.jp/_astro/aierutan-normal-003.BNvIssAd.wav) |

### 29. [満別花丸](https://voicevox.hiroshiba.jp/product/manbetsu_hanamaru/)

- 声質説明: 生き生きとした際立つ声
- speaker_uuid: `287aa49f-e56b-4530-a469-855776c84a8d`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 5

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 69 | talk | [1](https://voicevox.hiroshiba.jp/_astro/manbetsu_hanamaru-normal-001.DMP8RS9N.wav) [2](https://voicevox.hiroshiba.jp/_astro/manbetsu_hanamaru-normal-002.DffM8nIa.wav) [3](https://voicevox.hiroshiba.jp/_astro/manbetsu_hanamaru-normal-003.BKALQEeL.wav) |
| 元気 | 70 | talk | [1](https://voicevox.hiroshiba.jp/_astro/manbetsu_hanamaru-fun-001.KwRnJ5Jj.wav) [2](https://voicevox.hiroshiba.jp/_astro/manbetsu_hanamaru-fun-002.BHw0tG_q.wav) [3](https://voicevox.hiroshiba.jp/_astro/manbetsu_hanamaru-fun-003.D9BwjB-u.wav) |
| ささやき | 71 | talk | [1](https://voicevox.hiroshiba.jp/_astro/manbetsu_hanamaru-whis-001.m8Q8_T66.wav) [2](https://voicevox.hiroshiba.jp/_astro/manbetsu_hanamaru-whis-002.CbrgJhbT.wav) [3](https://voicevox.hiroshiba.jp/_astro/manbetsu_hanamaru-whis-003.BnaeAM6N.wav) |
| ぶりっ子 | 72 | talk | [1](https://voicevox.hiroshiba.jp/_astro/manbetsu_hanamaru-cute-001.CHLhmsBh.wav) [2](https://voicevox.hiroshiba.jp/_astro/manbetsu_hanamaru-cute-002.BK_aO2Zt.wav) [3](https://voicevox.hiroshiba.jp/_astro/manbetsu_hanamaru-cute-003.BKGVAYa7.wav) |
| ボーイ | 73 | talk | [1](https://voicevox.hiroshiba.jp/_astro/manbetsu_hanamaru-boy-001.BcHkLYR_.wav) [2](https://voicevox.hiroshiba.jp/_astro/manbetsu_hanamaru-boy-002.IuYHTKBm.wav) [3](https://voicevox.hiroshiba.jp/_astro/manbetsu_hanamaru-boy-003.CFGV4KKI.wav) |

### 30. [琴詠ニア](https://voicevox.hiroshiba.jp/product/kotoyomi_nia/)

- 声質説明: 滑らかで無機質な声
- speaker_uuid: `97a4af4b-086e-4efd-b125-7ae2da85e697`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 74 | talk | [1](https://voicevox.hiroshiba.jp/_astro/kotoyomi_nia-normal-001.WUPMD6gE.wav) [2](https://voicevox.hiroshiba.jp/_astro/kotoyomi_nia-normal-002.CsjzAEth.wav) [3](https://voicevox.hiroshiba.jp/_astro/kotoyomi_nia-normal-003.DMtxOPMA.wav) |

### 31. [Voidoll](https://voicevox.hiroshiba.jp/product/voidoll/)

- 声質説明: 慎ましやかで電子的な声
- speaker_uuid: `0ebe2c7d-96f3-4f0e-a2e3-ae13fe27c403`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `NOTHING`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 89 | talk | [1](https://voicevox.hiroshiba.jp/_astro/voidoll-01.qTSjG2n3.wav) [2](https://voicevox.hiroshiba.jp/_astro/voidoll-02.COVow3UI.wav) [3](https://voicevox.hiroshiba.jp/_astro/voidoll-04.DqzqbTP3.wav) |

### 32. [ぞん子](https://voicevox.hiroshiba.jp/product/zonko/)

- 声質説明: 熱血的でありありとした声
- speaker_uuid: `0156da66-4300-474a-a398-49eb2e8dd853`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `SELF_ONLY`
- スタイル数: 4

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 90 | talk | [1](https://voicevox.hiroshiba.jp/_astro/zonko-normal-001.CZErT2gJ.wav) [2](https://voicevox.hiroshiba.jp/_astro/zonko-normal-002.kc_E8QTd.wav) [3](https://voicevox.hiroshiba.jp/_astro/zonko-normal-003.BRgd98ys.wav) |
| 低血圧 | 91 | talk | [1](https://voicevox.hiroshiba.jp/_astro/zonko-relax-001.BiI2ZFkC.wav) [2](https://voicevox.hiroshiba.jp/_astro/zonko-relax-002.D_WE71Wz.wav) [3](https://voicevox.hiroshiba.jp/_astro/zonko-relax-003.Ba8kOux-.wav) |
| 覚醒 | 92 | talk | [1](https://voicevox.hiroshiba.jp/_astro/zonko-eager-001.BNIa2Qpy.wav) [2](https://voicevox.hiroshiba.jp/_astro/zonko-eager-002.DpWmmdKf.wav) [3](https://voicevox.hiroshiba.jp/_astro/zonko-eager-003.DXNIqh7h.wav) |
| 実況風 | 93 | talk | [1](https://voicevox.hiroshiba.jp/_astro/zonko-jikkyo-001.B9xvwqtC.wav) [2](https://voicevox.hiroshiba.jp/_astro/zonko-jikkyo-002.C7VVldTC.wav) [3](https://voicevox.hiroshiba.jp/_astro/zonko-jikkyo-003.DSJTSCjj.wav) |

### 33. [中部つるぎ](https://voicevox.hiroshiba.jp/product/chubu_tsurugi/)

- 声質説明: 凛然とした存在感のある声
- speaker_uuid: `4614a7de-9829-465d-9791-97eb8a5f9b86`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `SELF_ONLY`
- スタイル数: 5

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 94 | talk | [1](https://voicevox.hiroshiba.jp/_astro/chubu_tsurugi-normal-001.ObiOfQfq.wav) [2](https://voicevox.hiroshiba.jp/_astro/chubu_tsurugi-normal-002.D_txtHu9.wav) [3](https://voicevox.hiroshiba.jp/_astro/chubu_tsurugi-normal-003.uFNZNHPU.wav) |
| 怒り | 95 | talk | [1](https://voicevox.hiroshiba.jp/_astro/chubu_tsurugi-angry-001.bjSPEPTF.wav) [2](https://voicevox.hiroshiba.jp/_astro/chubu_tsurugi-angry-002.BkEmevJA.wav) [3](https://voicevox.hiroshiba.jp/_astro/chubu_tsurugi-angry-003.Bn24Gx79.wav) |
| ヒソヒソ | 96 | talk | [1](https://voicevox.hiroshiba.jp/_astro/chubu_tsurugi-hiso-001.CTfU-TIh.wav) [2](https://voicevox.hiroshiba.jp/_astro/chubu_tsurugi-hiso-002.4uozmZP1.wav) [3](https://voicevox.hiroshiba.jp/_astro/chubu_tsurugi-hiso-003.Y7Rqonok.wav) |
| おどおど | 97 | talk | [1](https://voicevox.hiroshiba.jp/_astro/chubu_tsurugi-fear-001.RiCyCvDo.wav) [2](https://voicevox.hiroshiba.jp/_astro/chubu_tsurugi-fear-002.CSTVaF79.wav) [3](https://voicevox.hiroshiba.jp/_astro/chubu_tsurugi-fear-003.BGlXMe7V.wav) |
| 絶望と敗北 | 98 | talk | [1](https://voicevox.hiroshiba.jp/_astro/chubu_tsurugi-guttural-001.LB5uIXA6.wav) [2](https://voicevox.hiroshiba.jp/_astro/chubu_tsurugi-guttural-002.CP80kP1Z.wav) [3](https://voicevox.hiroshiba.jp/_astro/chubu_tsurugi-guttural-003.Crx6Y_MM.wav) |

### 34. [離途](https://voicevox.hiroshiba.jp/product/rito/)

- 声質説明: 包み込む息遣いな声
- speaker_uuid: `3b91e034-e028-4acb-a08d-fbdcd207ea63`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 2

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 99 | talk | [1](https://voicevox.hiroshiba.jp/_astro/rito-normal-001.ajMhwAku.wav) [2](https://voicevox.hiroshiba.jp/_astro/rito-normal-002.DjXq0kMl.wav) [3](https://voicevox.hiroshiba.jp/_astro/rito-normal-003.BiypJtHc.wav) |
| シリアス | 101 | talk | [1](https://voicevox.hiroshiba.jp/_astro/rito-serious-001.CBCRtV_d.wav) [2](https://voicevox.hiroshiba.jp/_astro/rito-serious-002.13esjEKL.wav) [3](https://voicevox.hiroshiba.jp/_astro/rito-serious-003.BJue72Yv.wav) |

### 35. [黒沢冴白](https://voicevox.hiroshiba.jp/product/kurosawa_kohaku/)

- 声質説明: 強気で張りのある声
- speaker_uuid: `0b466290-f9b6-4718-8d37-6c0c81e824ac`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 100 | talk | [1](https://voicevox.hiroshiba.jp/_astro/kurosawa_kohaku-normal-001.COe55NYP.wav) [2](https://voicevox.hiroshiba.jp/_astro/kurosawa_kohaku-normal-002.8Q_qAA5x.wav) [3](https://voicevox.hiroshiba.jp/_astro/kurosawa_kohaku-normal-003.NFQ9ZUlA.wav) |

### 36. [ユーレイちゃん](https://voicevox.hiroshiba.jp/product/yureichan/)

- 声質説明: 柔和な揺蕩う声
- speaker_uuid: `462cd6b4-c088-42b0-b357-3816e24f112e`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 5

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 102 | talk | [1](https://voicevox.hiroshiba.jp/_astro/yureichan-normal-001.D_4DJof6.wav) [2](https://voicevox.hiroshiba.jp/_astro/yureichan-normal-002.Bac_PDep.wav) [3](https://voicevox.hiroshiba.jp/_astro/yureichan-normal-003.DQTFPX2G.wav) |
| 甘々 | 103 | talk | [1](https://voicevox.hiroshiba.jp/_astro/yureichan-ama-001.Dx0MlFOl.wav) [2](https://voicevox.hiroshiba.jp/_astro/yureichan-ama-002.DJ5AUWuD.wav) [3](https://voicevox.hiroshiba.jp/_astro/yureichan-ama-003.FdcE4Q8s.wav) |
| 哀しみ | 104 | talk | [1](https://voicevox.hiroshiba.jp/_astro/yureichan-sad-001.BAY7rIAC.wav) [2](https://voicevox.hiroshiba.jp/_astro/yureichan-sad-002.t9PnRdTq.wav) [3](https://voicevox.hiroshiba.jp/_astro/yureichan-sad-003.Dy-DK3r5.wav) |
| ささやき | 105 | talk | [1](https://voicevox.hiroshiba.jp/_astro/yureichan-whisper-001.BFoUgzl6.wav) [2](https://voicevox.hiroshiba.jp/_astro/yureichan-whisper-002.B0jR1ePX.wav) [3](https://voicevox.hiroshiba.jp/_astro/yureichan-whisper-003.DwKGBBnY.wav) |
| ツクモちゃん | 106 | talk | [1](https://voicevox.hiroshiba.jp/_astro/yureichan-tsukumo-001.BkSO2X4V.wav) [2](https://voicevox.hiroshiba.jp/_astro/yureichan-tsukumo-002.DS90t8rB.wav) [3](https://voicevox.hiroshiba.jp/_astro/yureichan-tsukumo-003.DgTaNCO5.wav) |

### 37. [東北ずん子](https://voicevox.hiroshiba.jp/product/tohoku_zunko/)

- 声質説明: しとやかで愛嬌のある声
- speaker_uuid: `80802b2d-8c75-4429-978b-515105017010`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `SELF_ONLY`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 107 | talk | [1](https://voicevox.hiroshiba.jp/_astro/tohoku_zunko-normal-001.DtpH542d.wav) [2](https://voicevox.hiroshiba.jp/_astro/tohoku_zunko-normal-002.Dau9SZwX.wav) [3](https://voicevox.hiroshiba.jp/_astro/tohoku_zunko-normal-003.JrojRiRI.wav) |

### 38. [東北きりたん](https://voicevox.hiroshiba.jp/product/tohoku_kiritan/)

- 声質説明: 淡麗でつづまやかな声
- speaker_uuid: `1bd6b32b-d650-4072-bbe5-1d0ef4aaa28b`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `SELF_ONLY`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 108 | talk | [1](https://voicevox.hiroshiba.jp/_astro/tohoku_kiritan-normal-001.DKz_sLUJ.wav) [2](https://voicevox.hiroshiba.jp/_astro/tohoku_kiritan-normal-002.CyGA-X_u.wav) [3](https://voicevox.hiroshiba.jp/_astro/tohoku_kiritan-normal-003.C64wDy8k.wav) |

### 39. [東北イタコ](https://voicevox.hiroshiba.jp/product/tohoku_itako/)

- 声質説明: 雅やかで余韻のある声
- speaker_uuid: `ab4c31a3-8769-422a-b412-708f5ae637e8`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `SELF_ONLY`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 109 | talk | [1](https://voicevox.hiroshiba.jp/_astro/tohoku_itako-normal-001.BON5PKOM.wav) [2](https://voicevox.hiroshiba.jp/_astro/tohoku_itako-normal-002.BDSTu1Bn.wav) [3](https://voicevox.hiroshiba.jp/_astro/tohoku_itako-normal-003.Dl4ThFaH.wav) |

### 40. [あんこもん](https://voicevox.hiroshiba.jp/product/ankomon/)

- 声質説明: 抑えめで負けず嫌いな声
- speaker_uuid: `3be49e15-34bb-48a0-9e2f-9b80c96e9905`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `SELF_ONLY`
- スタイル数: 5

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 113 | talk | [1](https://voicevox.hiroshiba.jp/_astro/ankomon-normal-001.B0b14wwF.wav) [2](https://voicevox.hiroshiba.jp/_astro/ankomon-normal-002.LjHa3rMI.wav) [3](https://voicevox.hiroshiba.jp/_astro/ankomon-normal-003.mj4prNJU.wav) |
| つよつよ | 114 | talk | [1](https://voicevox.hiroshiba.jp/_astro/ankomon-power-001.CLZ43b_Y.wav) [2](https://voicevox.hiroshiba.jp/_astro/ankomon-power-002.DntRjmgs.wav) [3](https://voicevox.hiroshiba.jp/_astro/ankomon-power-003.DBTFFPjH.wav) |
| よわよわ | 115 | talk | [1](https://voicevox.hiroshiba.jp/_astro/ankomon-weak-001.DdI8Ie5i.wav) [2](https://voicevox.hiroshiba.jp/_astro/ankomon-weak-002.CCShQI0u.wav) [3](https://voicevox.hiroshiba.jp/_astro/ankomon-weak-003.Ch15jQVN.wav) |
| けだるげ | 116 | talk | [1](https://voicevox.hiroshiba.jp/_astro/ankomon-darui-001.jSuCJNVt.wav) [2](https://voicevox.hiroshiba.jp/_astro/ankomon-darui-002.CMjkcEDb.wav) [3](https://voicevox.hiroshiba.jp/_astro/ankomon-darui-003.B4u8jPiR.wav) |
| ささやき | 117 | talk | [1](https://voicevox.hiroshiba.jp/_astro/ankomon-whisper-001.7Z6EISdy.wav) [2](https://voicevox.hiroshiba.jp/_astro/ankomon-whisper-002.DW2nyamL.wav) [3](https://voicevox.hiroshiba.jp/_astro/ankomon-whisper-003.BHRKKL40.wav) |

### 41. [夜語トバリ](https://voicevox.hiroshiba.jp/product/yogatari_tobari/)

- 声質説明: 理知的で輪郭のある声
- speaker_uuid: `d3be2066-205b-47f6-8818-1d93a9ca9cef`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 4

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 118 | talk | [1](https://voicevox.hiroshiba.jp/_astro/yogatari_tobari-normal-001.B6aCRZEN.wav) [2](https://voicevox.hiroshiba.jp/_astro/yogatari_tobari-normal-002.D8y3mxFa.wav) [3](https://voicevox.hiroshiba.jp/_astro/yogatari_tobari-normal-003.Cf8pOhvY.wav) |
| 明るい | 119 | talk | [1](https://voicevox.hiroshiba.jp/_astro/yogatari_tobari-cheerful-001.bc48zy4D.wav) [2](https://voicevox.hiroshiba.jp/_astro/yogatari_tobari-cheerful-002.zwIZqEpp.wav) [3](https://voicevox.hiroshiba.jp/_astro/yogatari_tobari-cheerful-003.CNoKljLl.wav) |
| 哀しみ | 120 | talk | [1](https://voicevox.hiroshiba.jp/_astro/yogatari_tobari-sad-001.0iS9_WF_.wav) [2](https://voicevox.hiroshiba.jp/_astro/yogatari_tobari-sad-002.DcM97qsG.wav) [3](https://voicevox.hiroshiba.jp/_astro/yogatari_tobari-sad-003.DUKlk1o0.wav) |
| 呆れ | 121 | talk | [1](https://voicevox.hiroshiba.jp/_astro/yogatari_tobari-akire-001.BEVSIhLp.wav) [2](https://voicevox.hiroshiba.jp/_astro/yogatari_tobari-akire-002.COB62r0G.wav) [3](https://voicevox.hiroshiba.jp/_astro/yogatari_tobari-akire-003.Byg-1BmF.wav) |

### 42. [暁記ミタマ](https://voicevox.hiroshiba.jp/product/akatsuki_mitama/)

- 声質説明: 儚げで浮遊感のある声
- speaker_uuid: `aca7de06-9ff9-49a3-9f08-9d3bc19689e5`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 4

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| ノーマル | 122 | talk | [1](https://voicevox.hiroshiba.jp/_astro/akatsuki_mitama-normal-001.CyMpReWX.wav) [2](https://voicevox.hiroshiba.jp/_astro/akatsuki_mitama-normal-002.D0KLRXzW.wav) [3](https://voicevox.hiroshiba.jp/_astro/akatsuki_mitama-normal-003.D7DC5oI5.wav) |
| 怒り | 123 | talk | [1](https://voicevox.hiroshiba.jp/_astro/akatsuki_mitama-angry-001.LDfqiy94.wav) [2](https://voicevox.hiroshiba.jp/_astro/akatsuki_mitama-angry-002.KVePKFLu.wav) [3](https://voicevox.hiroshiba.jp/_astro/akatsuki_mitama-angry-003.Cer_Uz4y.wav) |
| 哀しみ | 124 | talk | [1](https://voicevox.hiroshiba.jp/_astro/akatsuki_mitama-sad-001.ToU1PiMk.wav) [2](https://voicevox.hiroshiba.jp/_astro/akatsuki_mitama-sad-002.C7Vrvy5y.wav) [3](https://voicevox.hiroshiba.jp/_astro/akatsuki_mitama-sad-003.nMdo9UJi.wav) |
| ささやき | 125 | talk | [1](https://voicevox.hiroshiba.jp/_astro/akatsuki_mitama-whisper-001.O-Ch6rOL.wav) [2](https://voicevox.hiroshiba.jp/_astro/akatsuki_mitama-whisper-002.4I-jBlmz.wav) [3](https://voicevox.hiroshiba.jp/_astro/akatsuki_mitama-whisper-003.OreY9_Yj.wav) |

### 43. [里石ユカ](https://voicevox.hiroshiba.jp/product/satoishi_yuka/)

- 声質説明: 開花スタイルは今後実装予定
- speaker_uuid: `cc7baa71-6c74-4399-803b-b60576176a08`
- speaker version: `0.16.0`
- permitted_synthesis_morphing: `ALL`
- スタイル数: 1

| スタイル | Engine style_id | type | 公式サンプル |
| --- | ---: | --- | --- |
| つぼみ | 126 | talk | [1](https://voicevox.hiroshiba.jp/_astro/satoishi_yuka-tsubomi-001.B3a31kz3.wav) [2](https://voicevox.hiroshiba.jp/_astro/satoishi_yuka-tsubomi-002.Cb2n5XxY.wav) [3](https://voicevox.hiroshiba.jp/_astro/satoishi_yuka-tsubomi-003.BaO26M_t.wav) |

## 更新メモ

- `Engine style_id` はローカル VOICEVOX Engine `GET /speakers` から取得した値。
- 公式サンプルURLと声質説明は `https://voicevox.hiroshiba.jp/` から取得した値。
- Engineや公式サイトの更新でキャラ/スタイル/IDが変わる可能性があるため、VOICEVOX更新後は再生成する。

## 公式画像由来の一行特徴

VOICEVOX公式サイトから取得したキャラクター画像を元に、三行特徴を一行へ圧縮した視覚メモ。公式設定の断定ではなく、コメントビューアの個別設定で声・スキン・フォントを合わせるための補助資料。

元一行版: `J:\agents\abc_canvas\.agent_codex_workspaces\基本パーツ作成作業-0143a283a057\.agent_workspace\agents\node-1df1057fa9\work\voicevox_character_image_analysis_one_line.md`

| No | キャラクター | 一行特徴 | 画像パス |
|---:|---|---|---|
| 1 | 四国めたん | ピンクの長いツインテールと白フリルのメイド服、赤リボンが映える華やかで人形めいた印象。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\01_shikoku_metan.webp` |
| 2 | ずんだもん | 緑髪・枝豆耳・緑サロペットの明るい豆マスコットで、子どもっぽく快活。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\02_zundamon.webp` |
| 3 | 春日部つむぎ | 薄茶ロングヘアに大きめ黄土色ジャケットを合わせた、自然体で今風のカジュアル少女。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\03_kasukabe_tsumugi.webp` |
| 4 | 雨晴はう | 青いツインテールとナース帽風飾り、白青赤の衣装が明るく可愛い医療モチーフ。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\04_amehare_hau.webp` |
| 5 | 波音リツ | 流れる赤い長髪と黒赤ゴシック衣装が強く、妖艶でドラマチックなステージ感。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\05_namine_ritsu.webp` |
| 6 | 玄野武宏 | 深緑がかった短髪と軽装ジャケットの落ち着いた青年で、爽やかで親しみやすい。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\06_kurono_takehiro.webp` |
| 7 | 白上虎太郎 | 銀白の跳ね髪と黄アクセントのスポーティ衣装で、やんちゃで軽快な少年感。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\07_shirakami_kotarou.webp` |
| 8 | 青山龍星 | 青髪・青ジャケット・がっしり体格の余裕ある男性像で、低音が似合う大人の存在感。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\08_aoyama_ryusei.webp` |
| 9 | 冥鳴ひまり | 灰色巻き髪と黒ワンピース、紫の瞳が上品で静かなゴシック少女の雰囲気。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\09_meimei_himari.webp` |
| 10 | 九州そら | 紫系グラデ髪と黒銀の近未来衣装で、明るく余裕のある大人っぽい印象。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\10_kyushu_sora.webp` |
| 11 | もち子さん | 白銀髪と黒白の整った制服風衣装、機械的な小物が清潔で穏やかな案内役感。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\11_mochikosan.webp` |
| 12 | 剣崎雌雄 | サメ頭に白衣と緑シャツという異形の研究者風で、不思議さとコミカルさが強い。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\12_kenzaki_mesuo.webp` |
| 13 | WhiteCUL | 白い長髪と白青の雪氷モチーフ衣装が透明感と涼しさを出す清楚な印象。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\13_white_cul.webp` |
| 14 | 後鬼 | 青いロングヘアと眼鏡、濃紺スーツ風の装いが知的で包容力ある大人女性感。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\14_goki.webp` |
| 15 | No.7 | 白銀髪と機械的アクセサリ、黒白紫のSF衣装で凛々しくシャープなクール系。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\15_number_seven.webp` |
| 16 | ちび式じい | 青い龍風の小柄キャラに和装と角が付き、親しみやすいゆるいマスコット感。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\16_chibishikiji.webp` |
| 17 | 櫻歌ミコ | ピンクの動物耳フードと淡い衣装の小柄な少女で、ふわふわ甘い可愛さが前面。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\17_ouka_miko.webp` |
| 18 | 小夜/SAYO | 白い猫耳風の髪と黒いセーラー調衣装、赤い瞳が静かで夜っぽい猫系少女。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\18_sayo.webp` |
| 19 | ナースロボ＿タイプＴ | ナース服の少女と浮遊ロボの組み合わせで、医療的な清潔感と無機質な慎重さがある。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\19_nurserobo_typet.webp` |
| 20 | †聖騎士 紅桜† | 白銀の全身甲冑と赤いマント、剣が目立つ重厚で英雄的なファンタジー騎士。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\20_horinaito_benizakura.webp` |
| 21 | 雀松朱司 | 赤髪に赤系ジャケットの穏やかな成人男性で、日常的で安定した親しみやすさ。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\21_wakamatsu_akashi.webp` |
| 22 | 麒ヶ島宗麟 | 金茶の髪と髭、黄色い和装の年長男性で、渋さと余裕のある落ち着いた印象。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\22_kigashima_sourin.webp` |
| 23 | 春歌ナナ | ピンクツインテールとカラフルなハート装飾の白パーカーで、ポップで弾む元気さ。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\23_haruka_nana.webp` |
| 24 | 猫使アル | 赤い猫耳と赤黒衣装、片目隠れの髪型が力強い気さくな猫系キャラ。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\24_nekotsuka_aru.webp` |
| 25 | 猫使ビィ | 青い猫耳と青黒衣装、長い水色髪が透明感と控えめなピュアさを出す猫系キャラ。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\25_nekotsuka_bi.webp` |
| 26 | 中国うさぎ | 長い黒髪に白い服とうさぎのぬいぐるみを合わせた、内向的で幽玄な静けさ。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\26_chugoku_usagi.webp` |
| 27 | 栗田まろん | 茶髪ボブと黒い制服風トップス、腕組み姿が中性的で落ち着いた学生感。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\27_kurita_maron.webp` |
| 28 | あいえるたん | オレンジ紫の髪と白黒の未来的衣装が明るく、テック系の軽快な案内役感。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\28_aierutan.webp` |
| 29 | 満別花丸 | 白い帽子と大きな黒袖、赤い目の民俗衣装風で、素朴だが生命感が強い。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\29_manbetsu_hanamaru.webp` |
| 30 | 琴詠ニア | 黒い巻き髪と和服ストリート風衣装、透明袖が神秘的で和モダンな雰囲気。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\30_kotoyomi_nia.webp` |
| 31 | Voidoll | 白とシアンのロボット体とモニター顔が特徴で、電子的で軽快な無機質さ。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\31_voidoll.webp` |
| 32 | ぞん子 | 白ツインテールと赤い目、黒い大きめジャケットが派手なゾンビ系ストリート感。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\32_zonko.webp` |
| 33 | 中部つるぎ | 紫黒の武者風衣装と刀、角飾りが堂々とした戦闘キャラの存在感を出す。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\33_chubu_tsurugi.webp` |
| 34 | 離途 | 薄紫髪と黒ジャケット、ケーブル小物が静かで繊細な夜寄りの内省感。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\34_rito.webp` |
| 35 | 黒沢冴白 | 褐色肌と白髪、白パーカーとファー上着の自信あるストリート系青年。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\35_kurosawa_kohaku.webp` |
| 36 | ユーレイちゃん | 淡い水色髪と白青の軽い衣装が透けるようで、柔和に揺れる幽霊感。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\36_yureichan.webp` |
| 37 | 東北ずん子 | 緑の長髪と和風衣装、明るい笑顔が柔らかい姉系の愛嬌を出す。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\37_tohoku_zunko.webp` |
| 38 | 東北きりたん | 黒紫ボブと和風袖、背中のきりたんぽ風パーツが小柄で淡麗な妹系。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\38_tohoku_kiritan.webp` |
| 39 | 東北イタコ | 白水色の長髪と巫女風衣装、霊的な装飾が雅で余韻ある神秘性を出す。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\39_tohoku_itako.webp` |
| 40 | あんこもん | 黒赤のうさぎ耳と暗色ワンピース、腕組み姿が強気で負けず嫌いな子供感。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\40_ankomon.webp` |
| 41 | 夜語トバリ | 黒いロングワンピースと青黒い短髪、静かな手振りが理知的で夜のミステリアスさ。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\41_yogatari_tobari.webp` |
| 42 | 暁記ミタマ | 白銀髪と白黒クラシカルドレス、控えめな表情が儚く丁寧な浮遊感を出す。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\42_akatsuki_mitama.webp` |
| 43 | 里石ユカ | 黒髪とピンク髪の二人組風構図と灰色制服が、学生的で対比のあるデュオ感を出す。 | `J:\utility\Niconico\niconico-simple-comment-viewer\assets\voicevox_characters\43_satoishi_yuka.webp` |
