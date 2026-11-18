# manga-studio

AI で描く同人誌の漫画を、**入稿できる原稿**まで仕上げるための手順とスキル集です。
冬コミ合同誌（A5・右綴じ・本文モノクロ）の制作で使いながら育てています。

> 🔒 非公開リポジトリです。画像・キャラクターの参照画像・モデル・個人の設定は入れていません。

## 流れ

```
[0]   台本（コマ割り・場面・セリフ）……… page.json に書く
[1]   ネーム＝Codex（画像生成）で1ページの下書き（文字なし）
[1.5] ネーム確認＝下書きにセリフを仮で重ねて、全ページそろえてから OK を出す
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
| `skills/01_name_with_codex.md` | Codex にネームを描かせる頼み方（マンガの文法7つ） |
| `skills/02_local_generation.md` | ローカル生成（SDXL・P-H3）のコツと注意 |
| `skills/03_lettering.md` | 写植の決まり（縦書き・読む順・吹き出しの種類） |
| `skills/04_checklist.md` | 検収と入稿前のチェック表 |
| `templates/` | プロンプトの型・page.json／book.json の見本 |

## いまの状態（2026-11-18）

- ✅ 手順・スキル・型（このリポジトリの中身）
- ✅ 入稿コマンド `tools/studio.py`（今回の描画エンジンは `dummy` のみ）
- 数字には根拠を付けています〔実測／調査〕。未測定のものは「未測定」と書いています

## 使い方

Python・Pillow・Playwright と Playwright の Chromium が導入済みの環境で使います。
不足時は非ゼロ終了し、自動インストールやダウンロードは行いません。
画像生成・ComfyUI・外部サービス送信は行いません。写植時のネットワーク要求も遮断します。

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
| `plan <作品> [ページ]` | コマの原寸と正方形の下書きからの拡大率を一覧表示 |
| `cut <作品> <ページ> --draft <PNG> [--overlay] [--pad %]` | 下書きを比率に依存しない百分率で切り出し、確認画像も作成 |
| `draw <作品> <ページ> [id…] --engine dummy [--seed N] [--size WxH]` | 原寸または指定寸法のダミー画像を新しい版に追加 |
| `pick <作品> <ページ> <id> <K>` | 使用する版を選択 |
| `build <作品> <ページ>` | 原寸の組版・枠線・写植と履歴の記録 |
| `check <作品> [ページ]` | 入稿仕様・安全域・鮮度・拡大率・派生元と公開先を検査 |
| `export <作品>` | 全ページの検査後に連番 PNG・ZIP・提出メモを生成 |

```powershell
python -X utf8 tools/studio.py plan "local/作品 テスト"
python -X utf8 tools/studio.py cut "local/作品 テスト" 2 --draft "local/作品 テスト/p02/draft_source.png" --overlay
python -X utf8 tools/studio.py draw "local/作品 テスト" 2 --engine dummy --seed 42
python -X utf8 tools/studio.py pick "local/作品 テスト" 2 k1 1
python -X utf8 tools/studio.py pick "local/作品 テスト" 2 k2 1
python -X utf8 tools/studio.py build "local/作品 テスト" 2
# 他の通常ページと見開きも同じように cut → draw → pick → build
python -X utf8 tools/studio.py check "local/作品 テスト"
python -X utf8 tools/studio.py export "local/作品 テスト"
python -X utf8 tests/run_acceptance.py
```

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
下書きは作品フォルダ内に置き、既存の `draft.png` と overlay は上書きしません。
切り出し直しには作品を別フォルダにコピーして使ってください。

版は `panels/<id>/vK.png` と `vK.json` です。排他的に予約し、既存のどちらも上書きしません。
中断して残った予約も再利用しません。`pick.json` は選択変更時に更新します。
`vK.json` にはエンジン・seed・固定文付き prompt・参照 SHA256・大きさ・
box の比率・source・derived_from・作成日時・画像 SHA256 を保存します。
dummy の `source` は `chat`、`derived_from` は空配列です。
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

`chars` の ID が未登録・未承認の場合は失敗します。
参照・派生元は作品内の相対パスだけを許可します。
版に記録する参照はキャラクター画像と切り出した下書きのハッシュです。
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
今回新たに作れるのは dummy の版だけです。

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

`python -X utf8 tests/run_acceptance.py` は標準ライブラリの unittest で実行します。
pytest が導入済みなら `python -X utf8 -m pytest -q` でも同じ検査を実行できます。
一時作品・画像・実行時ファイルは無視済みの `local/acceptance/` 配下に作り、削除しません。
通常の右・左ページと見開きの全工程、再 build のハッシュ一致、古い台本・pick の拒否、
拡大上限・安全域・参照・派生由来・排他的な版採番・ZIP の整合を検証します。
印刷・画像の目視検収・実際の生成エンジンの品質は未測定です。
