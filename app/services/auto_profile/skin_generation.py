from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.core.logging import LogSink, log_error, log_execution, log_result
from app.services.codex_exec_runner import run_codex_exec

NullLogSink = lambda _level, _message: None
SkinRunner = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class SkinGenerationResult:
    path: Path
    font_id: int
    voice_id: int
    raw_response: str = ""
    prompt: str = ""


SKIN_PROMPT_ATTACHMENT_MARKDOWN = r"""
# スキン生成依頼
次の情報をもとに、このリスナーさんのイメージに合うフォントとボイスを選び、
さらにリスナーさんの特徴を反映させた背景画像を生成してください。
最終的な出力は、必ず次の形式の1行だけです。

背景画像は、本人のアイコン画像とコメント傾向に合う 1000x60 の背景として作ってください。
image-gen2の性能を最大まで活かした、細かく緻密に描かれた最高の背景画像を作ってください。
そしてあなたのセンスは最高に抜群なので、アーティストになった気分で思いっきり素敵な画像になるように思いながら描いてください。
フォントとボイスは、候補一覧の中から人物像に一番合うものを選んでください。

## 本人情報
### 本人のアイコン画像パス
{{icon_path}}

### 本人のコメント傾向の要約文
{{persona_summary}}

## スキン生成に関する指示
保存先は次のパスです。
{{output_path}}
必ずそのパスに PNG として保存してください。

## フォントとボイスの選定
フォントとボイスは、次の候補一覧から1つずつ選んでください。

### ボイスイメージ
- 四国めたん: 声=はっきりした芯のある声; 見た目=お嬢様/メイド/可憐/甘め; styles=V2ノーマル,V0あまあま,V6ツンツン,V4セクシー,V36ささやき,V37ヒソヒソ
- ずんだもん: 声=子供っぽい高めの声; 見た目=マスコット/子供っぽい/元気/軽い; styles=V3ノーマル,V1あまあま,V7ツンツン,V5セクシー,V22ささやき,V38ヒソヒソ,V75ヘロヘロ,V76なみだめ
- 春日部つむぎ: 声=元気な明るい声; 見た目=ギャル寄り/カジュアル/明るい/学生; styles=V8ノーマル
- 雨晴はう: 声=優しく可愛い声; 見た目=ナース/優しい/かわいい/癒し; styles=V10ノーマル
- 波音リツ: 声=低めのクールな声; 見た目=クール/ロック/舞台感/強め; styles=V9ノーマル,V65クイーン
- 玄野武宏: 声=爽やかな青年の声; 見た目=爽やか/落ち着き/青年/自然体; styles=V11ノーマル,V39喜び,V40ツンギレ,V41悲しみ
- 白上虎太郎: 声=声変わり直後の少年の声; 見た目=少年/活発/変声期/軽快; styles=V12ふつう,V32わーい,V34おこ,V33びくびく,V35びえーん
- 青山龍星: 声=重厚で低音な声; 見た目=低音/頼れる/兄貴分/重厚; styles=V13ノーマル,V81熱血,V82不機嫌,V83喜び,V84しっとり,V85かなしみ,V86囁き
- 冥鳴ひまり: 声=柔らかく温かい声; 見た目=ゴシック/柔らかい/影/上品; styles=V14ノーマル
- 九州そら: 声=気品のある大人な声; 見た目=大人/未来感/余裕/明るい; styles=V16ノーマル,V15あまあま,V18ツンツン,V17セクシー,V19ささやき
- もち子さん: 声=明瞭で穏やかな声; 見た目=穏やか/清潔感/案内役/精密; styles=V20ノーマル,V66セクシー／あん子,V77泣き,V78怒り,V79喜び,V80のんびり
- 剣崎雌雄: 声=安心感のある落ち着いた声; 見た目=変わり種/医者風/不思議/ネタ向き; styles=V21ノーマル
- WhiteCUL: 声=聞き心地のよい率直な声; 見た目=雪/清楚/涼しい/儚い; styles=V23ノーマル,V24たのしい,V25かなしい,V26びえーん
- 後鬼: 声=包容力のある奥ゆかしい声; 見た目=包容力/大人/妖艶/知的; styles=V27人間ver.,V28ぬいぐるみver.,V87人間（怒り）ver.,V88鬼ver.
- No.7: 声=しっかりした凛々しい声; 見た目=凛々しい/SF/冷静/シャープ; styles=V29ノーマル,V30アナウンス,V31読み聞かせ
- ちび式じい: 声=親しみのある嗄れ声; 見た目=マスコット/親しみ/和風/ゆるい; styles=V42ノーマル
- 櫻歌ミコ: 声=かわいらしい少女の声; 見た目=少女/かわいい/ふわふわ/甘い; styles=V43ノーマル,V44第二形態,V45ロリ
- 小夜/SAYO: 声=和やかで温厚な声; 見た目=猫/静か/温厚/夜; styles=V46ノーマル
- ナースロボ＿タイプT: 声=冷静で慎み深い声; 見た目=ナース/ロボ/慎重/冷静; styles=V47ノーマル,V48楽々,V49恐怖,V50内緒話
- †聖騎士 紅桜†: 声=快活でハキハキした声; 見た目=騎士/英雄/重厚/熱血; styles=V51ノーマル
- 雀松朱司: 声=物静かで安定した声; 見た目=穏やか/安定/日常/柔らかい; styles=V52ノーマル
- 麒ヶ島宗麟: 声=渋いおじさん声; 見た目=おじさん/和風/余裕/渋い; styles=V53ノーマル
- 春歌ナナ: 声=はつらつとした力強い声; 見た目=ポップ/元気/幼い/弾む; styles=V54ノーマル
- 猫使アル: 声=厚みのある気さくな声; 見た目=猫/気さく/厚み/赤/活発; styles=V55ノーマル,V56おちつき,V57うきうき,V110つよつよ,V111へろへろ
- 猫使ビィ: 声=ピュアであどけない声; 見た目=猫/ピュア/青/控えめ/透明感; styles=V58ノーマル,V59おちつき,V60人見知り,V112つよつよ
- 中国うさぎ: 声=幽玄で初々しい声; 見た目=うさぎ/幽玄/初々しい/静か; styles=V61ノーマル,V62おどろき,V63こわがり,V64へろへろ
- 栗田まろん: 声=深みのある中性的な声; 見た目=中性/深み/学生/控えめ; styles=V67ノーマル
- あいえるたん: 声=心地よい物柔らかな声; 見た目=テック/軽快/明るい/案内役; styles=V68ノーマル
- 満別花丸: 声=生き生きとした際立つ声; 見た目=民俗/元気/土着感/朗らか; styles=V69ノーマル,V70元気,V71ささやき,V72ぶりっ子,V73ボーイ
- 琴詠ニア: 声=滑らかで無機質な声; 見た目=神秘/無機質/和モダン/滑らか; styles=V74ノーマル
- Voidoll: 声=慎ましやかで電子的な声; 見た目=ロボ/電子/無機質/軽快; styles=V89ノーマル
- ぞん子: 声=熱血的でありありとした声; 見た目=ゾンビ/熱血/ありあり/派手; styles=V90ノーマル,V91低血圧,V92覚醒,V93実況風
- 中部つるぎ: 声=凛然とした存在感のある声; 見た目=武者/凛然/存在感/強い; styles=V94ノーマル,V95怒り,V96ヒソヒソ,V97おどおど,V98絶望と敗北
- 離途: 声=包み込む息遣いな声; 見た目=内省/息遣い/夜/包む; styles=V99ノーマル,V101シリアス
- 黒沢冴白: 声=強気で張りのある声; 見た目=張り/強気/ストリート/男性; styles=V100ノーマル
- ユーレイちゃん: 声=柔和な揺蕩う声; 見た目=幽霊/柔和/揺蕩う/淡い; styles=V102ノーマル,V103甘々,V104哀しみ,V105ささやき,V106ツクモちゃん
- 東北ずん子: 声=しとやかで愛嬌のある声; 見た目=和風/愛嬌/しとやか/緑; styles=V107ノーマル
- 東北きりたん: 声=淡麗でつづまやかな声; 見た目=淡麗/つづまやか/妹系/和風; styles=V108ノーマル
- 東北イタコ: 声=雅やかで余韻のある声; 見た目=雅/霊感/余韻/姉系; styles=V109ノーマル
- あんこもん: 声=抑えめで負けず嫌いな声; 見た目=負けず嫌い/子供/暗め/跳ねる; styles=V113ノーマル,V114つよつよ,V115よわよわ,V116けだるげ,V117ささやき
- 夜語トバリ: 声=理知的で輪郭のある声; 見た目=論理的/ミステリアス/夜/冷静; styles=V118ノーマル,V119明るい,V120哀しみ,V121呆れ
- 聴記ミタマ: 声=儚げで浮遊感のある声; 見た目=儚い/浮遊感/クラシカル/丁寧; styles=V122ノーマル,V123怒り,V124哀しみ,V125ささやき
- 里石ユカ: 声=開花スタイルは今後実装予定; 見た目=デュオ/学生/未実装感/対比; styles=V126つぼみ

### フォントイメージ
| F1 | Dela Gothic One | 極太で黒面積が大きい。角が強く、見出しとしてかなり目立つ。 | 強い、うるさい、主張が強い、ツッコミ役 |
| F2 | Hachi Maru Pop | 細めの丸い手書き。線がゆるく、かなり柔らかい。 | かわいい、ゆるい、天然、軽い雑談 |
| F3 | Klee One | ペン字寄りの手書き。細く整っていて落ち着く。 | 上品、静か、丁寧、文芸寄り |
| F4 | RocknRoll One | 太めで丸みのあるポップゴシック。勢いはあるが読みやすい。 | 元気、明るい、配信向け、標準ポップ |
| F5 | New Tegomin | 古い活字と手書きの中間。細く、和風で物語感がある。 | 和風、昔話、落ち着き、少し怪しい雰囲気 |
| F6 | Train One | 文字内部に縞が入る装飾フォント。本文より看板向け。 | 派手、ネタ、タイトル、特殊演出 |
| F7 | DotGothic16 | ドット表示風。直線とピクセル感が強い。 | レトロ、ゲーム、機械、昔のPC風 |
| F8 | Reggae One | 太く、角が削れたような癖がある。勢いとクセが強い。 | 陽気、クセ強、派手、荒めのキャラ |
| F9 | Yuji Syuku | 筆文字だが整っている。和風で硬すぎない。 | 和風、礼儀正しい、落ち着いた強さ |
| F10 | Yuji Boku | 筆跡がラフで揺れが大きい。手書き感がかなり強い。 | 荒い、感情的、勢い、野性味 |
| F11 | Mochiy Pop One | 極太で丸い。黒面積が大きく、かわいいが強く読める。 | かわいい、元気、強い、目立つコメント |
| F12 | Kaisei HarunoUmi | 明朝寄りで細め。余白があり、品がある。 | 文学的、落ち着き、真面目、知的 |
| F13 | Shippori Antique | アンティークな明朝。太さは中程度で読みやすい。 | 古風、上品、安定、落ち着いた常連 |
| F14 | Stick | 細く直線的で角張る。手書きより記号・棒文字に近い。 | 無機質、変わり者、機械的、クール |
| F15 | Rampart One | 輪郭と影のある装飾文字。本文には重いが一発で目立つ。 | 祭り、看板、強調、イベント通知 |
| F16 | Zen Antique | 太めの明朝系。和風で硬さがあり、読みやすい。 | 伝統、落ち着き、格式、真面目 |
| F17 | Mochiy Pop P One | Mochiy Pop 系の太丸文字。F11より詰まり方が少し自然。 | かわいい、親しみ、常用ポップ、強め |
| F18 | Zen Kurenaido | 細く丸い手書き。柔らかく、主張は控えめ。 | 優しい、静か、女性的、穏やか |
| F19 | Yusei Magic | マーカー手書き風。太さは中程度で会話文に使いやすい。 | 親しみ、手書き感、日常会話、自然体 |

##　返答json
返答は次のJSONだけにしてください。

{
  "ok": true,
  "path": "保存したPNGファイルの絶対パス",
  "font_id": 0,
  "voice_id": 0
}""".strip()


def render_auto_profile_skin(
    plan: Any,
    output_path: Path,
    *,
    skin_spec: Any = None,
    icon_path: str = "",
    workdir: Path | None = None,
    model: str = "",
    effort: str = "",
    timeout_seconds: int | None = None,
    runner: SkinRunner | None = None,
    evidence_path: Path | None = None,
    log: LogSink = NullLogSink,
) -> SkinGenerationResult:
    return create_auto_profile_skin_with_codex(
        plan,
        output_path,
        skin_spec=skin_spec,
        icon_path=icon_path,
        workdir=workdir,
        model=model,
        effort=effort,
        timeout_seconds=timeout_seconds,
        runner=runner,
        evidence_path=evidence_path,
        log=log,
    )


def create_auto_profile_skin_with_codex(
    plan: Any,
    output_path: Path,
    *,
    skin_spec: Any = None,
    icon_path: str = "",
    workdir: Path | None = None,
    model: str = "",
    effort: str = "",
    timeout_seconds: int | None = None,
    runner: SkinRunner | None = None,
    evidence_path: Path | None = None,
    log: LogSink = NullLogSink,
) -> SkinGenerationResult:
    width = int(getattr(skin_spec, "width", 512) or 512)
    height = int(getattr(skin_spec, "height", 32) or 32)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prompt = build_codex_skin_prompt(
        plan,
        output_path=output_path,
        width=width,
        height=height,
        icon_path=icon_path,
    )
    log_execution(log, "CodexスキンPNG生成", level="INFO", path=output_path, width=width, height=height)
    command: list[str] = []
    stderr = ""
    returncode = 0
    if runner is not None:
        text = runner(prompt)
    else:
        result = run_codex_exec(prompt, cwd=workdir, timeout_seconds=timeout_seconds, model=model, effort=effort)
        command = result.command
        stderr = result.stderr
        returncode = result.returncode
        if not result.ok:
            log_error(log, "CodexスキンPNG生成失敗", code=result.returncode, stderr=result.stderr[-300:])
            detail = result.stderr.strip() or f"returncode={result.returncode}"
            raise RuntimeError(f"skin generation Codex failed: {detail}")
        text = result.text
    generation_result = parse_skin_generation_response(text, expected_path=output_path)
    original_path: Path | None = None
    actual_width, actual_height, mode = inspect_png(output_path)
    if (actual_width, actual_height) != (width, height):
        original_path = output_path.with_name(f"{output_path.stem}_original{output_path.suffix}")
        shutil.copy2(output_path, original_path)
        source_size = f"{actual_width}x{actual_height}"
        actual_width, actual_height, mode = resize_png_to_exact(output_path, width=width, height=height)
        log_result(
            log,
            "CodexスキンPNGリサイズ",
            expected=f"{width}x{height}",
            source=source_size,
            actual=f"{actual_width}x{actual_height}",
            original=original_path,
        )
    if evidence_path is not None:
        save_codex_skin_evidence(
            evidence_path,
            command=command,
            returncode=returncode,
            stderr=stderr,
            prompt=prompt,
            response=text,
            output_path=output_path,
            original_path=original_path,
            width=actual_width,
            height=actual_height,
            mode=mode,
        )
    log_result(log, "CodexスキンPNG生成", path=output_path, bytes=output_path.stat().st_size, mode=mode)
    return SkinGenerationResult(
        path=output_path,
        font_id=generation_result.font_id,
        voice_id=generation_result.voice_id,
        raw_response=text,
        prompt=prompt,
    )


def build_codex_skin_prompt(
    plan: Any,
    *,
    output_path: Path,
    width: int,
    height: int,
    icon_path: str,
) -> str:
    persona_summary = str(getattr(plan, "persona_summary", "") or "").strip()
    return (
        SKIN_PROMPT_ATTACHMENT_MARKDOWN.replace("{{icon_path}}", str(icon_path or "").strip())
        .replace("{{persona_summary}}", persona_summary)
        .replace("{{output_path}}", str(output_path))
    )


def object_to_public_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items() if not str(key).startswith("_")}
    result: dict[str, Any] = {}
    for key in ("id", "family", "label", "description"):
        if hasattr(value, key):
            result[key] = getattr(value, key)
    return result


def parse_skin_generation_response(text: str, *, expected_path: Path) -> SkinGenerationResult:
    source = extract_json_object(text)
    try:
        payload = json.loads(source)
    except json.JSONDecodeError as exc:
        raise ValueError("skin generation response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("skin generation response JSON must be an object")
    if payload.get("ok") is not True:
        raise ValueError("skin generation response ok must be true")
    response_path = Path(str(payload.get("path") or expected_path))
    return SkinGenerationResult(
        path=response_path,
        font_id=required_int(payload.get("font_id"), "font_id"),
        voice_id=required_int(payload.get("voice_id"), "voice_id"),
        raw_response=text,
    )


def extract_json_object(text: str) -> str:
    source = str(text or "").strip()
    if source.startswith("```"):
        lines = source.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        source = "\n".join(lines).strip()
    start = source.find("{")
    end = source.rfind("}")
    if start < 0 or end < start:
        raise ValueError("skin generation response JSON object was not found")
    return source[start : end + 1]


def required_int(value: Any, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"skin generation response requires integer {label}") from exc


def inspect_png(path: Path) -> tuple[int, int, str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required to verify generated skins") from exc
    with Image.open(path) as image:
        return image.size[0], image.size[1], image.mode


def crop_png_center(path: Path, *, width: int, height: int) -> tuple[int, int, str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required to crop generated skins") from exc
    with Image.open(path) as image:
        source_width, source_height = image.size
        if source_width < width or source_height < height:
            raise ValueError(f"generated skin size must be at least {width}x{height}: {source_width}x{source_height}")
        left = (source_width - width) // 2
        top = (source_height - height) // 2
        cropped = image.crop((left, top, left + width, top + height))
        cropped.save(path)
        return cropped.size[0], cropped.size[1], cropped.mode


def resize_png_to_exact(path: Path, *, width: int, height: int) -> tuple[int, int, str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required to resize generated skins") from exc
    with Image.open(path) as image:
        resized = image.resize((width, height), Image.Resampling.LANCZOS)
        resized.save(path)
        return resized.size[0], resized.size[1], resized.mode


def save_codex_skin_evidence(
    path: Path,
    *,
    command: list[str],
    returncode: int,
    stderr: str,
    prompt: str,
    response: str,
    output_path: Path,
    original_path: Path | None = None,
    width: int,
    height: int,
    mode: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "codex_command": command,
        "codex_returncode": returncode,
        "stderr_tail": stderr[-1000:],
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt": prompt,
        "raw_ai_response": response,
        "raw_ai_response_sha256": hashlib.sha256(str(response or "").encode("utf-8")).hexdigest(),
        "png_path": str(output_path),
        "original_png_path": str(original_path) if original_path is not None else "",
        "original_png_exists": bool(original_path and original_path.is_file()),
        "png_exists": output_path.is_file(),
        "png_size": output_path.stat().st_size if output_path.is_file() else 0,
        "width": width,
        "height": height,
        "mode": mode,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
