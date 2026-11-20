# manga-studio

AI で描く同人誌の漫画を、**入稿できる原稿**まで仕上げるための手順とスキル集です。
冬コミ合同誌（A5・右綴じ・本文モノクロ）の制作で使いながら育てています。

> 🔒 非公開リポジトリです。画像・キャラクターの参照画像・モデル・個人の設定は入れていません。

## 流れ

```
[0]   台本（コマ割り・場面・セリフ）……… page.json に書く
[1]   ネーム＝Codex（画像生成）で1ページの下書き（文字なし）
[1.5] ネーム確認＝下書き → review → リポジトリの持ち主（ツキ）の OK → approve → 清書へ
[2]   切り出し＝下書きをコマごとに切る
[3]   コマごとに描く＝ローカル生成（SDXL＋キャラ LoRA）／Codex でコマだけ描き直し
[4]   原寸で組む＝3638×5102（グレー600dpi）・塗り足し・見開き
[5]   写植＝セリフはフォントで原寸に焼く（画像生成に文字を描かせない）
[6]   検収と書き出し＝チェック表 → 001.png…
```

締切を守るのは道具よりネームの早さ。**全ページのネームを先にそろえる**のがいちばん効きます。

## 中身

| 場所 | 中身 |
|---|---|
| `docs/page-spec.md` | 原稿の決まり（大きさ・塗り足し・安全域・右綴じ・見開き・書き出し） |
| `docs/rights-and-characters.md` | 守る線（全年齢・キャラクターの公式ガイドライン・モデルのライセンス） |
| `docs/manga-howto/` | 漫画制作の手引き（Codex の一発描き・ローカル生成・本番の組み方・キャラ LoRA・つまずき集）＝[README](docs/manga-howto/README.md) |
| `skills/01_name_with_codex.md` | Codex にネームを描かせる頼み方（マンガの文法7つ） |
| `skills/02_local_generation.md` | ローカル生成（SDXL・P-H3）のコツと注意 |
| `skills/03_lettering.md` | 写植の決まり（縦書き・読む順・吹き出しの種類） |
| `skills/04_checklist.md` | 検収と入稿前のチェック表 |
| `templates/` | プロンプトの型・page.json／book.json の見本 |
| `config/engines.json` | SDXL のチェックポイントとキャラクター別 LoRA の設定（例だけ。自分の設定は `local/engines.local.json`） |

## いまの状態（2026-11-20）

- ✅ 手順・スキル・型（このリポジトリの中身）
- ✅ `tools/studio.py` の入稿経路、SDXL／Codex のコマ描画と描き直し、ComfyUI 用の書き出しと取り込み
- 数字には根拠を付けています〔実測／調査〕。未測定のものは「未測定」と書いています

## 使い方

Python・Pillow・Playwright と Playwright の Chromium が導入済みの環境で使います。
不足時は非ゼロ終了します。写植時のネットワーク要求は遮断します。

作品は Git 管理しない `local/` または `works/` に置いてください。
`templates/book.example.json` を作品直下の `book.json`、
`templates/page.example.json` を各ページの `page.json` にコピーします。
以下のページ番号・版番号・寸法は使用例〔未測定〕です。

```text
local/作品 テスト/
  book.json
  refs.json                  # chars を使う場合だけ必要
  p02/page.json
  p02/draft_source.png
  p03/page.json
  p03/draft_source.png
  p04-05/page.json            # 見開きは先の番号を page に記入
  p04-05/draft_source.png
```

| コマンド | 処理 |
|---|---|
| `plan <作品> [ページ] [--template]` | コマの原寸と拡大率を一覧表示。指定時は枠と薄い吹き出し予定地を `draft_template.png` に出力（上書きなし） |
| `review <作品> <ページ> [--draft <PNG>] [--derived-from 版JSON]` | 文字入りネームとコマ番号付きの確認画像を作成 |
| `approve <作品> <ページ>` | リポジトリの持ち主（ツキ）の確認後に `page.json` へ `name_ok: true` を記録 |
| `cut <作品> <ページ> --draft <PNG> [--overlay] [--pad %] [--derived-from 版JSON]` | 下書きを百分率で切り出し、確認画像も作成 |
| `draw <作品> <ページ> [id…] --engine <dummy・sdxl・codex> [--seed N] [--size WxH] [--force]` | コマを描いて新版に追加。コマ ID を省くと全コマを順に描画 |
| `redo <作品> <ページ> <id> --scene "新しい場面" [--engine <sdxl・codex>] [--seed N] [--force]` | 台本を書き換え、新版と新旧の比較 PNG を作成 |
| `comfy <作品> <ページ> <id> [--seed N] [--size WxH]` | ComfyUI で編集できる SDXL I2I のワークフロー JSON と入力 PNG を書き出す |
| `import <作品> <ページ> <id> <PNG> [--derived-from 版JSON] [--ph3]` | ComfyUI で保存した PNG を新版として取り込む |
| `pick <作品> <ページ> <id> <K> [--as-draft]` | 使用する版を選択。指定時はコマの下書きも選んだ版に差し替え |
| `build <作品> <ページ> [--force]` | 原寸の組版・枠線・写植と履歴の記録 |
| `check <作品> [ページ]` | 入稿仕様・安全域・鮮度・拡大率・派生元と公開先を検査 |
| `export <作品>` | 全ページの検査後に連番 PNG・ZIP・提出メモを生成 |

```powershell
python -X utf8 tools/studio.py plan "local/作品 テスト"
python -X utf8 tools/studio.py review "local/作品 テスト" 2
# リポジトリの持ち主（ツキ）の OK を受けてから記録
python -X utf8 tools/studio.py approve "local/作品 テスト" 2
python -X utf8 tools/studio.py cut "local/作品 テスト" 2 --draft "local/作品 テスト/p02/draft_source.png" --overlay
python -X utf8 tools/studio.py draw "local/作品 テスト" 2 --engine dummy --seed 42
python -X utf8 tools/studio.py pick "local/作品 テスト" 2 k1 1
python -X utf8 tools/studio.py pick "local/作品 テスト" 2 k2 1
python -X utf8 tools/studio.py build "local/作品 テスト" 2
# 他の通常ページと見開きも同じように review → approve → cut → draw → pick → build
python -X utf8 tools/studio.py check "local/作品 テスト"
python -X utf8 tools/studio.py export "local/作品 テスト"
python -X utf8 tests/run_acceptance.py
```

### ネーム確認

`review` はコマごとに `pick` した版、切り出し済みの `draft.png`、ページ全体の下書きの順で使います。ページ全体の下書きは `draft_source.png` に置くか、作品内の別の PNG を `--draft` で指定します。全コマの素材がそろっていればページ全体の下書きは省略できます。
セリフと語りを薄く重ねた `review_name.png` と、読む順の番号・枠・素材（「下書き」または「v5」など）を入れた `review_overlay.png` をページフォルダに出力します。どちらも長辺2000px以下・1MB以下で、再実行すると更新します。
全ページの確認画像をそろえ、リポジトリの持ち主（ツキ）の OK を受けてから各ページで `approve` を実行します。
`name_ok` が未設定または `false` のページでは、SDXL での描画・描き直しと `build` が警告して停止します。`--force` はその実行だけ確認を省略できます。
`redo --engine codex` で構図を描き直した版を清書の下絵に使うには、`pick <作品> <ページ> <id> <K> --as-draft` を実行します。元の下絵は `draft_v1.png` から連番で保存し、新しい `draft.png` を SDXL I2I に渡します。下絵が変わると `name_ok` が外れるので、`review` で確認し直してから `approve` します。

### メンバーの PC でコマを描く

- SDXL は各自の PC に ComfyUI と使用権のあるモデルを用意します。チェックポイントは `models/checkpoints/`、LoRA は `models/loras/` に置き、起動済みの ComfyUI を `http://127.0.0.1:8188` で使います。2人用の Hook ノードを含む ComfyUI 本体が必要です。起動・終了やモデルの導入は各自で行います。
- 設定は `MANGA_STUDIO_ENGINES` で指したファイル → `local/engines.local.json`（Git 管理外）→ `config/engines.json` の順に探し、最初に見つかったものの `sdxl.checkpoint` と `sdxl.loras` を使います。LoRA はキャラクター ID ごとの `file` と `trigger` です。**既定の設定（`config/engines.json`）は例（`your_character`）だけです。** `local/engines.local.json` にコピーし、自分のキャラの LoRA を作ってから書き足してください。他の人のキャラは本人の許可を取ってから書き足します。
- SDXL は切り出したコマを I2I で描き直します。denoise の既定は **0.55**〔実測：ローカル生成手順 §5.7〕。画像サイズの既定はコマの縦横比で約 **1MP**、SDXL の `--size` は幅・高さとも **8px** の倍数です〔実装値：VAE の空間圧縮単位〕。2人のコマでは `characters`（従来の `chars` も可）を下絵の**左→右**の順に書きます。2人を左右に分け、中央に両方の LoRA がかからない隙間を作ります。3人以上のコマは Codex を選びます。
- 棒人間の下絵では 0.55 で棒線が残ることがあります。コマごとに `page.json` の `sdxl.denoise`（0 より大きく 1 以下）を指定できます。`sdxl.regional_prompts` は2人のコマでキャラクター ID ごとに服装や向きを指定するオブジェクトです。場面全体は `scene` に書きます。`sdxl.negative_prompt` は既定のネガティブプロンプトに足す文字列です。これらの設定は `draw`、`redo`、`comfy` に共通で、実際に使った denoise は版の JSON と `log.jsonl` に残ります。
- Codex は image_gen が利用できる CLI とログイン済みのアカウントが必要です。Windows で自動検出できない場合は `MANGA_STUDIO_CODEX` に `codex.exe` を設定します。登録済みの参照シートとコマの下絵を Codex のサービスに渡します。各コマを順に実行し、終了したセッションにある PNG を1枚だけ回収します。枠線や白余白を描かずキャンバスの端まで絵を描くよう、縦横比と seed とともに指示します。
- Codex へ渡すニケちゃんの参照画像は公式三面図だけです。`refs.json` の該当項目を `approved: true`、`kind: "official_turnaround"` とし、`files` にそのファイルを登録します。

```powershell
python -X utf8 tools/studio.py draw "local/作品 テスト" 2 k1 --engine sdxl --seed 42
python -X utf8 tools/studio.py draw "local/作品 テスト" 2 k2 --engine codex
python -X utf8 tools/studio.py redo "local/作品 テスト" 2 k1 --scene "もっと引きで、二人が庭で話す" --engine sdxl
python -X utf8 tools/studio.py comfy "local/作品 テスト" 2 k1
python -X utf8 tools/studio.py import "local/作品 テスト" 2 k1 "local/ComfyUI出力.png"
```

`redo` は `log.jsonl` に場面の変更前後を記録し、描画成功時に `panels/<id>/compare_vK.png` を保存します。左は選択中の版（未選択なら最新の完成版）、右は新版です。初回は `draw` または `import` で比較元の版を作ります。エンジンを省略するとコマの `engine` を使い、未指定なら SDXL です。描画が失敗したときも新しい場面は台本に残り、`draw` で再試行できます。採用する版は `pick` で選びます。

`comfy` の `panels/<id>/comfy_inputs/` にある PNG を ComfyUI の `input/` にコピーし、ブラウザで `comfy_workflow.json` を開きます。保存先の接頭辞は `manga-studio/<作品>/<ページ>/<id>` です。保存した PNG を `import` すると、PNG 内のワークフローも保持します。

### 寸法と左右

- 出力は **3638×5102px・8bit グレー L・アルファなし・600dpi**〔実測：受け入れテスト〕。
  PNG の dpi は画素／メートルの整数で記録されるため、読み戻しの誤差を **0.01dpi** まで許容します〔実測：PNG の量子化〕。
- 仕上がり **148×210mm**、塗り足し **3mm**、安全域は上下・外側 **10mm**、ノド **15mm**〔未測定：主催資料の指定値〕。
  設定値は `book.json` に集約します。今回の出力はグレーの指定画素数・解像度のみ対応です。
- ページの左右は `pages` の先頭番号と `first_page_side` を起点に、**ページ番号の差の偶奇**で決めます。
  `binding` は今回 `right` のみ。右ページのノドは左、左ページのノドは右です。
- `box` と `lines` の位置・寸法・文字サイズ・tail は仕上がり枠に対する百分率です。
  `lines` はページ直下と各コマ内の両方を扱い、座標はどちらもページ全体が基準です。
  `order` は読む順の記録です。重ね合わせは従来の道具と同じく `panels` の配列順です。
- `bleed` は `top`・`bottom`・`outer`・`gutter`。指定辺を塗り足し外端まで伸ばします。
  枠線は `border: false` で省略でき、太さは `border_mm`（ページ既定またはコマ別）です。
  枠線既定 **0.3mm**〔未測定：実装上の初期値〕。

### 切り出し・版・参照

`cut` の余白は **コマの幅・高さそれぞれの4%を各辺**に加えます〔未測定：設計書の既定値の解釈〕。
`--pad` で変更でき、下書きの外にはみ出した部分は切り詰めます。
コマごとに必須の `box` が１つ必要で、ID 重複や box 欠落は失敗します。
任意の `panel_count` があれば実数との一致も確認します。
下書き画像内のコマの画像認識は行わず、`draft_overlay.png` で目視確認してください。
生成された枠が白紙テンプレートからずれた場合は、コマの `draft_box: [x, y, w, h]` に下書き画像上の百分率を指定できます。
`cut` と overlay はその座標を使い、テンプレートと組版は `box` を使います。
下書きは作品フォルダ内に置き、既存の `draft.png` と overlay は上書きしません。
切り出し直しには作品を別フォルダにコピーして使ってください。

版は `panels/<id>/vK.png` と `vK.json` です。排他的に予約し、既存のどちらも上書きしません。
Codex の出力と `import` の PNG は、外周近くの四辺に細い枠線を検出した場合に、枠線とその外側を切り落として版に保存します。版の JSON には保存した画像の実寸が入ります。
中断して残った予約も再利用しません。`pick.json` は選択変更時に更新します。
`vK.json` にはエンジン・seed・固定文付き prompt・参照 SHA256・大きさ・
box の比率・source・derived_from・作成日時・画像 SHA256 を保存します。
`draw` の `source` は `chat`、`import` は `comfy` です。`log.jsonl` は生成・取り込み・場面の変更を記録します。
固定の全年齢文・ネガティブは `tools/safety.py` にあり、無効化する引数はありません。

キャラクター参照は `refs.json` の登録制です。例：

```json
{
  "original_character": {
    "approved": true,
    "files": ["refs/original_character.png"]
  }
}
```

Codex とダミーは `characters`／`chars` の指定がある場合に、未登録・未承認のキャラクター参照を拒否します。
参照・派生元は作品内の相対パスだけを許可します。
版に記録する参照は実際に使用したキャラクター画像や切り出した下書きのハッシュです。
作品・画像・参照の登録簿を Git に追加しないでください。

### 組版と検査

`build` は白地の `page_notext.png`、透過の `letter_layer.png`、合成済み `page.png`、
`build.json` を生成します。原稿の焼き直しではこれらの派生成果物を更新します。
元の版画像・版 JSON は保持します。
写植は参照の `manga_letter.py` の SVG・縦書き CSS を移植し、HTML＋Playwright で原寸描画します。
吹き出し・心の声・叫び・キャプション・自由文字・横書き・回転に対応します。
既存フォントのみ使い、文字のはみ出し・実際の文字層の安全域外画素も失敗にします。

`plan` は **1024×1024** の正方形からアスペクト比を保って埋める場合の倍率を出します〔実測：設定から算出〕。
`build` は選択版の実寸に対する倍率を、裁ち切り・zoom・整数丸め込みで計算して記録します。
`max_upscale` 超過は出力前に失敗します。`null` は上限なしで、拡大があれば警告します。
印刷で許容できる倍率・線・トーンは **未測定**です。

`check` と `export` は台本・作品設定・pick・版メタデータ・派生元・版画像の変更と出力の改変を検出します。
box・lines・pick を変更したあとは必ず再 `build` してください。
派生元は `derived_from` に作品内の版 JSON パスを列挙し、循環を拒否します。
P-H3 由来は派生をたどって継承し、`print_jp` 以外の公開先を拒否します。
未知の公開先も許可しません。P-H3 由来を codex に渡す版も拒否します。
編集で来歴が失われた PNG は `--derived-from` で元の版 JSON を指定します。元の版が作品内にない P-H3 由来の PNG は `import --ph3` で申告します。P-H3 由来の画像は `print_jp` の作品でのみ扱えます。

`book.json` に任意の `required_notices: ["必要な表示", ...]` を指定すると、
作品の先頭または最終原稿の安全域内の `lines` にその表示を必須にできます。
`chars` に `nike`・`nikechan`・`AIニケちゃん` がある原稿には
「非公式のファンメイド作品」「AIニケちゃん」を同じ場所で必須にします。
P-H3 由来を含む場合は同じ場所で `MiniMax H3` の表示も必須です。
読み順・顔・誤字・健全さ・第三者由来の画像に既に焼かれたガイド類の有無は、
`skills/04_checklist.md` に従って目視で確認してください。
本コマンド自身は原稿へガイド・目盛り・ページ番号・トンボを描きません。
dummy のコマ内 ID・版表示は検収用の印で、本番の絵ではありません。

### 見開きと提出

`book.json` の `spreads: [[4, 5]]` のように連続した右→左の組を宣言します。
見開きは `p04-05/page.json` の `page: 4` に保存し、通常ページと同じコマ・lines を使います。
引数には組内のどちらの番号も使えます。座標の横幅は仕上がり２ページ分です。
物理的な左半分が後の番号、右半分が若い番号です。
見開きの `outer` はそのコマがある半分の外端、`gutter` は中央側の塗り足しを表します。
中央をまたぐコマは継ぎ目のない１枚として組みます。

指定寸法での内部見開きは **7134×5102px**〔実測：受け入れテスト〕です。
仕上がり横幅 **3496px** と外側塗り足し **71px**〔実測：設定から算出〕を基準にし、
中央の塗り足しを二重に含めず組みます。
export でそれぞれ **3638×5102px** に切り、中央の **142px** を共有します〔実測：受け入れテスト〕。
左右それぞれノド側に **3mm** を持たせる既定値は **主催の確認待ち**〔未測定：主催資料の暫定案〕です。
`spread_gutter_bleed_mm`（省略時 `bleed_mm`）で共有する量を変更できます。
指定範囲はゼロから外側の塗り足し量までで、共有しないノド余白は白になります。
設定変更後は再 build が必要です。

全原稿が check を通った場合だけ `out/001.png`…、`submission.zip`、`submission.txt`、
対応番号とハッシュを示す `export.json` を作ります。ZIP の内容は連番 PNG と提出メモです。
再 export は既存の提出物を保持して `out/run-NNN/` に追加します。
ファイルの削除・送信は行いません。ファイル名が主催指定と異なる場合は提出前に確認してください。

### 受け入れテスト

`python -X utf8 -m unittest discover -s tests -v` で入稿経路と偽エンジンの全テストを実行します。
pytest が導入済みなら `python -X utf8 -m pytest -q` でも同じ検査を実行できます。
一時作品・画像・実行時ファイルは無視済みの `local/acceptance/` 配下に作り、削除しません。
通常の右・左ページと見開きの全工程、再 build のハッシュ一致、古い台本・pick の拒否、
拡大上限・安全域・参照・派生由来・排他的な版採番・ZIP の整合を検証します。
偽エンジンでは Hook・Codex のセッション回収・描き直し・PNG の取り込みも検証します。印刷品質は未測定です。
