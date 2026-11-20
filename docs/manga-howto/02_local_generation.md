# 2. ローカル生成（ComfyUI＋キャラ LoRA）

自分の PC の ComfyUI で、SDXL の土台にキャラ LoRA を重ねて描くやり方です。

> 先に読むもの：[skills/02_local_generation.md](../../skills/02_local_generation.md)（土台・LoRA の強さ・使える手の一覧・P-H3）と、README の「メンバーの PC でコマを描く」（`tools/studio.py` の `draw --engine sdxl` / `comfy` / `import`）。
> この章は、そこに**書いていない追加分**です。測った環境＝RTX 3050 6GB（ノート）・RAM 32GB。

## 2-1. いまの位置づけ

- **完成度は Codex の一発描きのほうが上**でした（設定どおりに描く・機械や服の描写・攻めた構図）〔実体験・同じ場面を並べて比べた〕。うちは当面、Codex で良い出力をためて、それを素材に LoRA を育てる方針です（[04_character_lora.md](04_character_lora.md)）。
- ローカルの強み＝枚数の上限がない・LoRA でキャラの顔を固定できる・構図の下ごしらえ・原寸の画質に近づける工程（[03](03_production_assembly.md)）。
- 比べるときは、同じ場面を横に並べて人の目で決める。ベタの量や胸もとの広さのような表面の差で「こっちが攻めている」と判断して外したことがあります〔実体験・1回〕。

## 2-2. 起動・停止・メモリ

- 起動用の `.bat` で窓が消えて応答がないときは、本体を直接起動すると上がった〔実測・1回〕（PowerShell・`<portable>` は ComfyUI portable のフォルダ）：

  ```powershell
  Start-Process -FilePath "<portable>\python_embeded\python.exe" `
    -ArgumentList '-s','ComfyUI\main.py','--windows-standalone-build','--disable-fast-disk','--disable-pinned-memory' `
    -WorkingDirectory "<portable>" -WindowStyle Minimized -RedirectStandardError "$env:TEMP\comfy_err.log"
  ```
  - 🔴 `-WorkingDirectory` を付ける（相対パスの `ComfyUI\main.py` を探せない）
  - 起動に約1分。`http://127.0.0.1:8188/system_stats` が返るまで待つ。待つ側は「何秒で諦めるか」を決めておく
- 🔴 **メモリ**：2人のコマ（2-6 の Hook）を描くと ComfyUI の python が RAM を **16〜18.5GB** 使い、PC の空きが 0.7GB まで落ちた〔実測〕。FP8（モデルの数値を8ビットに縮めて読み込む方式。メモリが減る）で描き直したら最大 11.6GB〔実測・1回〕。
  - 描く前に空きメモリを測り、**6GB 未満なら描かない**・1枚ずつ描く・描き終えたら止める
  - AI エージェント（Claude Code など）に描かせている場合、メモリが詰まると**エージェントが裏で動かしている別の処理を止める**ことがある〔実測・複数回〕
- **止めるときは、コマンドラインに `ComfyUI\main.py` を含む python だけ**を止める。広く止めて、関係のない別のアプリまで止めてしまったことがある〔実測・1回〕

## 2-3. プロンプトの型と設定

```
<LoRAの識別語>, 1girl, solo, adult, <構図>, <服>, <動き・表情>, <場所>, (<白黒なら> monochrome, greyscale, manga, screentone), <品質タグ>
```

- 識別語だけで髪・瞳・髪飾りが出るように学習しておくと、プロンプトに書かなくて済む（[04](04_character_lora.md)）
- 🔴 **服は必ず書く**。書かないと土台（Animagine）の癖で露出の多い服・体型の強調が出た〔実測〕
- 効かせたい語は重み付け `(chibi:1.4)`。1.3〜1.4 が目安で、上げすぎると崩れる〔実測〕
- 横向き・後ろ向きの素体（キャラの体と姿勢だけを描いた、服や背景を決める前の土台の絵）は、人が2人に増えたりお尻のアップになったりした → ネガティブに `multiple views, ass focus`〔実測〕
- 設定の目安：832×1216・28 step・cfg 5.0・euler_ancestral・normal。1枚 約30〜40秒〔実測〕

## 2-4. 白黒のコマを描くとき

〔実測・各1〜3枚〕

| 手 | 結果 |
|---|---|
| `monochrome, greyscale, manga, lineart, white background`＋ネガティブ `black hair, dark hair, colored, spot color, grey background` | バストアップの横長コマは線がすっきり、襟も閉じた（1枚） |
| `high contrast` を足す | 髪が黒ベタになって本人でなくなった（1枚）＝使わない |
| 全身＋`white background` | 背景に色がつく（3枚中3枚）。組むときに白黒化すれば消える |
| 白黒のコマで服を `dark teal dress` と色で書く | 服も色つきになる（2枚中2枚）＝白黒では `black dress` のように書く |
| `chibi, dot eyes` | ちびにならず、ちびの人形を持った絵になった（2枚中2枚） |
| `(chibi:1.4)`（重み付け） | ちびになった（6枚中6枚・1回の比較） |
| `from behind` | 背中の開いた服になった（2枚中2枚）→ 下絵で閉じる（2-5） |
| 下絵なしの顔のアップ | 崩れやすい（1回の比較）→ 下絵（canny か I2I）を使う |

## 2-5. 下絵を使う（ControlNet canny・顔の描き直し）

- **canny（線を写す）は効いた**：seed を変えても、元の絵のポーズ・服の形・髪の流れが残った〔実測・2枚〕。うちは ControlNet-LLLite（kohya-ss・GPL-3.0）の `canny_anime` モデル（Apache-2.0）を使っています〔調査（一次）：ノード https://github.com/kohya-ss/ControlNet-LLLite-ComfyUI ・モデル https://huggingface.co/kohya-ss/controlnet-lllite （リポジトリ全体の表示）〕。元の絵にない背景は成り行き。
- **後ろ姿の「背中の開いた服」は、背中を塗りつぶした下絵を強さ 1.0・100% で写すと閉じた**〔実測・1枚〕。強さ 0.7・50% では肌が戻った〔実測・1枚〕。`closed back` と書くだけでは開いたまま〔実測・2枚中2枚〕。
- **pose（棒人間）はほとんど効かなかった**〔実測・3枚中1枚だけ寄った〕。ポーズを決めたいときは canny で下絵を写すほうがよい。
- 🔴 OpenPose の検出器は**非商用研究限定のライセンス**のものがある（ControlNet 同梱の OpenPose）。本に使う絵では確認してから〔調査（一次）：https://github.com/lllyasviel/ControlNet/blob/main/annotator/openpose/LICENSE 〕。
- 顔の描き直し（FaceDetailer）：全身の小さい顔のにごりが3枚中3枚で直り、髪飾りは変わらなかった。1枚 約25秒増える〔実測〕。
  - **全身の見せ場は hires（1.5倍）、枚数を回す下描きは顔の描き直しだけ**。両方かけるのは目がまだ崩れているときだけ（hires の上に重ねると口の形が変わった・3枚中1枚）〔実測〕。
  - Impact-Pack の `install.py` は実行しない（大きなモデルを自動で落とす）。ultralytics の利用統計の送信は設定で切れる（`settings.json` の `sync: false`）〔調査（一次）〕。

## 2-6. I2I（元の絵を LoRA のタッチで描き直す）の強さ

元の絵を `VAEEncode` して、KSampler の denoise を下げて描き直します。〔実測・各1〜4枚〕

| denoise | 何に向くか |
|---|---|
| **0.45〜0.5** | Codex の決めゴマを元に、**構図・あおり・迫力を残してタッチだけ LoRA に寄せる**。ページのタッチをそろえる用途。0.6 で武器が2本になりかけ、0.75 で構図が崩れた |
| **0.55** | 2人のコマ（下の Hook）で構図と武器の形が残る（安定）。0.7 では武器が崩れた（4枚中ほぼ全部） |
| **0.75** | 画風（色→白黒）・表情・場面を変える（3/3）。ポーズと角度はほとんど変わらない（2/2） |
| **0.85〜0.9** | 元の絵を「服の見本」にしてポーズを変える＋ポーズを文で書く。小物が崩れることがあるので数枚回して選ぶ |

- 🔴 **設定画の「まっすぐ立った正面」を元の絵にすると、0.9 でもポーズが変わらない**（10枚中、座る・振り返る・顔のアップは全部立ち姿のまま）〔実測〕。ポーズを変えたいときは、そのポーズで描いた絵（Codex の場面など）を元の絵にする。
- I2I でも表情が崩れる → **顔の描き直しを I2I にもかける**（I2I 0.45＋顔 0.45 で4枚とも整った）〔実測〕。表情はプロンプトにも書く。
- 元の絵の題字・サインは先に消す（残すと崩れた文字が残る）〔実測〕。
- うちの流れ＝**Codex で構図 → ローカル I2I 0.45＋顔 0.45 で LoRA のタッチ**。

## 2-7. 2人を1枚に描く

- 2人目が他の人のキャラなら、先に [README](README.md)「先に守る線」を見てください（LoRA を作る・使うには本人の許可が要ります）。
- 🔴 **LoRA を2つ重ねると、2人が1人に溶ける**（8枚とも・文で左右を分けても効かない）〔実測〕。Codex の2人の絵を元に I2I しても、LoRA を2つ同時にかける限り特徴が混ざった（服の柄が相手に移る）〔実測・4枚〕。
- **成功した組み方（ComfyUI 本体だけ・追加インストールなし）**〔実測・12枚とも2人が分かれ、特徴も混ざらなかった〕：
  1. `CreateHookLoraModelOnly` で LoRA を1人ずつフックにする
  2. それぞれ `PairConditioningSetProperties`（mask＝左／右・**あいだに隙間のある、はっきりしたマスク**・set_cond_area=default・hooks）
  3. `PairConditioningCombine` → `PairConditioningSetDefaultCombine`（全体＝LoRA なしの文）
  4. KSampler のモデルは素の土台（LoraLoader は使わない）。元の絵＝Codex の2人の構図を `VAEEncode`、denoise 0.55
- 白紙から（EmptyLatent）だと、LoRA は左右に分かれても体が1人のまま左右をまたいだ〔実測〕。
- Hook と ControlNet-LLLite は同時に効かなかった（canny を渡しても構図が変わらない）〔実測・1枚〕。
- 天気（霧・雨など）は全体の文（default）に入れる。左右の文だけだと消えた〔実測〕。
- 1枚 約190秒。描画中は RAM を約19GB 使う（2-2）〔実測〕。
- `tools/studio.py` の SDXL エンジンは、この考え方（キャラごとの領域・中央の隙間）で2人のコマを描きます（README「メンバーの PC でコマを描く」）。

## 2-8. Codex のページにローカルのコマを混ぜる

- **1コマだけ貼りかえ**：Codex のコマ（1人だけ・吹き出しなし・四角い枠）を canny の下絵にしてローカルで描き、枠の内側に貼りかえた → 位置はずれずに貼れたが、**絵柄が合わず不採用**（顔が大人びて目が鋭い・トーンがなく白と黒だけ・頼んでいない背景が出た）〔実測・下絵あり2枚／なし2枚〕。混ぜるなら、絵柄が変わってよいコマ（回想・夢・別の世界）に限るのが無難。
- **ページをまるごとローカルのコマで組む**（3回作り直し）→ Codex の一発描きの水準に届かず不採用〔実体験〕。分かったこと：
  - 線の量は描くときの言葉で決まる（あとから減らせない）
  - 切り抜き＋白ふちを多用するとシールを貼ったように見える
  - コマ枠からはみ出させた人物の頭が画像の端で切れていた（はみ出すなら頭の上に余白のある絵を描く）
  - 人物を囲む枠が多すぎると、通常の漫画として違和感が強い
  - ローカルはコマごとに服がそろわない
- **Codex のページを下絵にして、コマごとにローカルで描き直す**と、Codex の7〜8割の出来まで寄った〔実体験・1回の比較〕。差として残ったのは、コマの強弱がない・力の配分が逆・カメラの変化がない・網点と線が別物に見える・点の目が出ない、で、前の4つは組み方で直せる見込み（未検証）。

## 2-9. ライセンスの補足

[docs/rights-and-characters.md](../rights-and-characters.md) に加えて、本に使う絵では次も確認しています〔調査（一次）〕。

- 土台：Animagine XL 4.0＝CreativeML Open RAIL++-M（商用可）：https://huggingface.co/cagliostrolab/animagine-xl-4.0 。NoobAI 系は商用不可で外した（各自で原文を確認）。
- IP-Adapter-FaceID はモデルカードで非商用の研究用途に限定（通常の IP-Adapter と混同しない）：https://huggingface.co/h94/IP-Adapter-FaceID
- 追加のノード・モデルは、入れる前にライセンスを見る（GPL・AGPL のノードもある。配る絵には影響しないと理解していますが、原文を確認してください。ノードを配るときは条件がある）。
