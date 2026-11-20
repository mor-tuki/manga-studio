# 1. Codex で1ページを一発で描く

うちのいまの主力は、**Codex（`codex exec` の image_gen）に文字入りの1ページを一発で描かせる**やり方です。2026-11-11〜11-20 の毎日マンガは、ほぼ全ページこれで描いています。

> 先に読むもの：[skills/01_name_with_codex.md](../../skills/01_name_with_codex.md)（マンガの文法7つ・効いた言い回し・回し方）と、型 [templates/prompt_page_bw.txt](../../templates/prompt_page_bw.txt)。
> この章は、そこに**書いていない追加分**です。

- 1枚 約3分・1024×1536〔実測・3件〕
- 1枚あたりのトークンは、プロンプトのファイルを読ませる頼み方で 4〜8万、中身を標準入力で渡す頼み方で 2万前後〔実測・11/17 と 11/18〜19 の Codex の tokens used〕。参照画像を何枚渡すかでも変わります（1-6 の 7万〜12万は、前のページ・1ページ目・キャラ参照の3枚を渡した条件）
- ChatGPT の5時間の利用枠で、画像はだいたい35枚前後〔実測・1日（11/12）。契約や他の使い方で変わります〕

---

## 1-1. 基本の順番

1. **白黒で描く**（色つきより白黒のほうがマンガらしく見えた〔実体験〕）
2. 画像を開いて検収（[skills/04_checklist.md](../../skills/04_checklist.md)）
3. 直す（1-7）
4. 色がほしい日だけ、白黒の完成ページに**着色の編集**を1回足す（1-7）

色をつけたあとに直すと、色まで描き直しになります。直しは白黒のうちに。

---

## 1-2. ネームの段階で決めること

プロンプトより前の、話の組み立てで効いたことです。

- **構成の型を台帳にして、直近2本と同じ型を使わない**。毎回同じ流れ（ふり→ずれ→オチ）だと、続けて読む人に「いつもの形」と見えます〔実体験〕。うちの型の一覧は下の表。
- **「気持ちの出発点 → 到達点」を1行**書く（だれの・どの気持ちが・何をきっかけに動くか）。型が「どう見せるか」なら、こちらは「何が変わるか」の軸です。シリーズ全体のゴールは決めず、回ごとの1行だけにすると展開が読まれにくい〔実体験〕。
- **初めて読む人が1話だけ読んでも分かる**こと。続けて読んだ人だけ気づく仕掛けは「分かると深くなる」までにとどめる。
- **オチは最後のコマの絵だけで1秒で分かる**ように。セリフを隠しても伝わるか確かめる。
- **見せ場のあるページは3コマ以下**にして、見せ場は「ページの縦いっぱい」か「見開き」。詰まったらコマを減らさずにページを分ける〔他者の経験則：森茶さんのネーム直し前後の比較 https://x.com/moritya369_dayo/status/2122972517984026988 〕。

### 構成の型（うちの台帳から）

| 型 | 流れ |
|---|---|
| やりすぎ→安全な代案 | A が提案→B が乗る→A がやりすぎる→B が代案→やり方に性格が出るオチ |
| 素直のりすぎ | B が聞く→A が生返事→B がまじめに積み上げる→大きな最後のコマで結果を見せる |
| サイレント定点・時間飛ばし | 同じカメラの小ゴマ3つで時間が進む→枠なしの大ゴマでどんでん返し。吹き出しなし |
| 大きな1枚絵＋一言 | 決め絵1枚とひとことだけ |
| ビフォーアフター2コマ | 前と後の2コマ。あいだは読者に想像させる（後のコマに一言あるほうが伝わった〔実体験〕） |
| 取り違え・すれ違い | 同じ言葉を別の意味で受けとったまま進み、最後に絵でずれが分かる |
| 二人でボケて物がオチ | 二人とも同じ方向に走り、止めるのは物や状況 |
| 同じ言葉の持ち回り | ひとつの言葉が、ページごとに意味を変えて戻ってくる |
| 並行して合流 | 同じきっかけから二人が別々に動き、最後に合流して種が分かる |
| 一行設定の扉＋引き | 一行の設定を大ゴマ・題字で言い切り、1枚目の最後に引き（(1/N)） |
| 言い換え3回 | 読者のやることを、語り手が「代わりに〜だけ」と3回小さくする |
| 探させる大ゴマ＋種明かし | 大ゴマで読者に何かを探させ、次のコマで種明かし |
| 語り手の入れかわり | 最後のコマだけ語り手が替わり、見る側が見られる側になる |
| 鏡返し | 始まりのボケを、相手が教わったとおりに返す。続きものの回収向き |
| あるある4連 | 1枚1ネタを4枚。同じ主人公・同じ題材で、ネタごとに1ページで落とす |

〔実体験・各1〜3本。型ごとの読者の反応の差は、まだ数字がそろっていないので言いません〕

---

## 1-3. 効いた書き方（skills/01 にない分）

| やりたいこと | 頼み方 | 根拠 |
|---|---|---|
| **読む順を守る（いちばん効いた）** | 全コマ共通の決まりに1文：「先に話す人がコマの右に立つ・吹き出しは自分の頭の真上・尻尾は短く、交差しない」。位置（upper right 等）だけ書くと、話し手と吹き出しの組が入れ替わった | 〔実測・直しゼロが1枚→その日の午後5枚すべて1回で通った〕 |
| 同じコマで2人が話す | `the balloon nearest the RIGHT panel edge is read first and belongs to <名前>` と、話す順と話し手を1文で結ぶ | 案（上の立ち位置の書き方で解決したので単独では未検証） |
| 3コマ以上が横に並ぶ段 | 列の左右を書く（「大ゴマは右・小2つは左の列に縦」）＋読む順を `P1→P5` で1行 | 〔実測・1件〕 |
| いろいろな角度 | 「全コマ別のカメラ・目の高さを使わない」＋コマごとに**カメラ名＋何が手前で大きいか**（真上から／肩越し／テーブル面からのアオリ／手首の超アップ＋奥に小さく二人） | 〔実測・1枚で4つとも成立〕 |
| 線の量をそろえる | 数字でなく「前のページの下の段くらいの線の量」と、参照画像の一部を名指し | 〔実測・1枚〕 |
| 情報量を減らす | 前のページを1枚目に渡し「同じ構図と文字のまま、線は半分・トーンは2か所だけ・背景の小物を消す」。**消してはいけないもの（オチの小物）を名指しで残す**。書かなかったらオチの小物まで消えた | 〔実測・1枚〕 |
| 小声の吹き出し | 「ほかの吹き出しの**半分の大きさ・字も半分**」と比で、**そのコマの中に**書く。`clearly SMALLER` だけでは小さくならず、共通の決まりにまとめて書いたら効かなかった | 〔実測・効いた2件／効かなかった2件〕 |
| 目線の向き | 「〜を見る」でなく**顔の向き**で：`HER HEAD IS IN STRICT PROFILE: the tip of her nose points to the RIGHT edge of the page, we see ONLY ONE eye` | 〔実測・2件〕（「左上を見上げる」は2枚とも正面寄り） |
| 正面の顔のコマ | 後ろにある髪飾りは「後ろにあって見えない・横に描かない」と最初から書く。書かないと頭の左右に飾りが2つ付いた | 〔実測・崩れ1件→書いて防げた1件〕 |
| 後ろ頭のコマ | 前髪の髪飾りは「描かない」と書く。「見えるように」と書くと後頭部に付いた（頼み方が矛盾していた） | 〔実測・1件〕 |
| 「見ている」がセリフの芯 | 「目を開けて相手を見る」と書く。書かないとにこ目（閉じた目）になった | 〔実測・1件〕 |
| 向きのある地面（横断歩道など） | しまの向きと歩く向きを1文で結ぶ：`she walks ACROSS the stripes, each stripe lies parallel to her shoulders` | 未検証（崩れたのは1件） |
| 作中の小物の文字 | 実物にある書き方で（服のタグなら「日本製」より `MADE IN JAPAN`）。編集1回で文字だけ差し替えられた | 〔実測・1件〕 |
| 1色をオチの答えに | 白黒＋1色のとき、その色を「探させる大ゴマの答え」だけに使う：`THE ONLY CLUE: her ONE small flat TEAL bow … about 4% of the panel width` | 〔実測・1枚〕 |
| 1色をにじませない | 色をつける物を列挙し、それ以外（髪・服・文字）は白黒と書く | 〔実測・3作品で、指定した物だけに乗った〕 |
| 着替えの回 | キャラの柄を別の服へ移す：`today the cow-print is the pattern of her KIMONO`。目印は全コマ残った | 〔実測・1枚〕 |
| 着物の衿合わせ | `the wearer's LEFT front panel lies ON TOP (seen from the front, the collar line looks like a lowercase letter "y")` | 〔実測・1枚・拡大して4か所確認〕 |
| 下着などの題材 | 本人に着せず、**作中の資料（スケッチブック・設計図）の中に描く**。資料の中だけ別の絵柄にもできた | 〔実測・1枚〕 |
| 胸もとを閉じる | `high closed collar, no cleavage` だけでは参照の衣装（胸もとに切れ込み）に引っ張られた〔実測・2枚〕。強めの一段落（STRICT MODESTY）を毎回入れたら首まで閉じた〔実測・複数ページ〕。閉じた衣装の参照を別に用意するのも手 | 左記 |
| 動物の出ない題材 | 「NO animals anywhere, no animal heads, tails, paws or pelts」を共通の決まりに | 〔実測・3枚で出なかった〕 |

---

## 1-4. 画風

- **画風は STYLE の段落で名指しする**と、参照画像の塗りに引っ張られません（skills/01「参照の画風をまねさせない」と組み合わせる）〔実測・11枚〕。
- うちのベースは「**女性誌風**」「**アール・ヌーヴォー風**」（扉向き）です。これはうちの好みの選択です。
- 「線は少なく・黒い面を大きく」（ギャグ寄りの簡略）は、話の間をつなぐコマで時々使う程度。コミケ向けの画風には合わないと判断しました〔実体験〕。
- オチのコマだけ画風を切り替えるなら、アメコミ風がいちばん自然でした（劇画・少女マンガ・浮世絵は合わなかった）〔実体験・各1枚〕。
- 描きこみの量は言葉で段階指定できます。バトルの下限の例：`about HALF the lines of a normal finished page; hair as a few large shapes; almost no clothing wrinkles; screentone in ONLY two places; small solid blacks`。ベタとトーンを全部抜くと、ぬりえに見えて重さが消えた〔実測・4枚〕。

### バトル漫画タッチ（冬コミ用に作った STYLE ブロック）

〔実体験：これで描いたキャラの設定画を「完璧に近い」と判断・1枚〕。**特定の作家名・作品名は書かない**（その人の絵の写しに寄りすぎるため）。

```
DRAWING STYLE (follow strictly; do not imitate any specific artist):
- High-precision modern shonen battle manga inking: crisp confident main contour lines with clear thick-to-thin line weight variation, very clean and controlled.
- Dense shading made with fine parallel hatching and cross-hatching (pen lines), plus solid black areas; very little gray screentone. No soft gradients, no color.
- Sharp, elegant eyes with defined upper lashes; cool, composed beauty in the face.
- Detailed fabric folds, ruffles and lace; hair drawn as many flowing strands with ink highlights.
- Strong sense of weight and motion in action poses (foreshortening, a few speed lines).
```

- 画風の見本画像があるときは、**画風の見本を `-i` の1枚目、キャラのデザイン参照を2枚目**に渡し、「1枚目は STYLE だけ・デザインは2枚目から」と書く。2人目のキャラもこれで画風がそろった〔実測・1枚〕。見本画像はこのリポジトリには入れていません（各自で、自分のキャラで作ってください）。
- 二人が戦うコマには TONE の段落を入れる：`a fair sparring duel between two friendly EQUAL RIVALS; neither is a villain, neither is losing, nobody is hurt`。3枚とも笑顔で、傷・流血なし〔実測・3枚〕。

---

## 1-5. 扉絵の型

複数ページの回は「扉絵＋本編」にしています（冬コミ本番も同じ構成の予定）。

1. **お題（テーマ）が主・題はサブタイトル**：テーマの行を右の余白に縦書きでいちばん目立たせ、物語の題は絵の中のすみに小さく
2. **人物は画面の高さの3割前後**：1割だと説明図に見え、4〜5割だと強すぎた。数字（about 30%）で頼むと4〜5割になった → **余白で頼む**と3割になった：`Above each girl's head, leave an empty calm space that is at least TWICE AS TALL as the girl herself`＋「ページの高さの3分の1より小さい」〔実測・2件〕
3. **その話の関係を1枚の構図で見せる**：例「別々の世界」＝まん中のはっきりした柱で左右を分け、左右の背景を別のものにし、上で一枚の空。仕切りが細い草だけ・左右が同じ背景だと「同じ場所にいる」絵になった
4. **枠は軽く**：細いつる草・小さな花・四隅の丸いメダイヨンに話の小物。重い枠と大きな花は主役に勝った
5. **白黒＋トーンに1色**（本編と同じ色の決まり）。SNS 用に色つき、本用に白黒、が要るときは、色つきを1枚目に渡して「その色だけトーンに置きかえる」編集1回で白黒版が作れた〔実測・1件〕

〔実測・扉絵7枚（うち改良の4枚）＋その後の2作品〕。描く順は本編が決まってから扉。

---

## 1-6. 複数ページで絵柄をそろえる

skills/01 の「前のページを `-i` の1枚目に」に加えて：

- `-i` の順＝**前のページ → 1ページ目 → キャラ参照**（2ページ目は前のページ＝1ページ目なので3枚）。プロンプトの頭に「同じ作品・同じ衣装・同じ字の手・コマやポーズや文字は写さない」と書く → 4ページとも絵柄・衣装の柄・吹き出しと字の手がそろった〔実測・4枚〕
- **共通の決まりを1ファイル（common.txt）に切り出し**、ページごとのファイルには PAGE の節だけ書く。3案を順番に描いて3枚とも1回で文字・読む順が正しかった〔実測・3枚〕
- 会話を続ける方式（`codex exec resume`）と見た目はほぼ互角で、新しいセッション＋前ページ渡しのほうがトークンが約4割安い（74,586 対 119,124）〔実測・各1枚〕→ うちは新しいセッションのほう
- 同じ日に描いたデッサン（服の分解図など）を参照の4枚目に渡し、「大ゴマの中の絵柄専用」と書くと、その部分だけデッサンの絵柄になった〔実測・1枚〕

---

## 1-7. 直し方・色のつけ方

- **一部だけ直す**：直したい絵を `-i` の1枚目に「EDIT・ほかは全部そのまま・ここだけ変える」（skills/01）。ポーズ1つ・目だけ・文字だけの直しで、ほかのコマと文字は変わらなかった〔実測・数件〕
- 🔴 **「消す」編集は、同じ物がほかのコマにもあると巻きこむ**：1コマの余分な髪飾りを消したら、頼んでいない最後のコマの髪飾りまで消えた → **直したコマだけを元のページへ手元で貼り戻した**（コマの間の白い溝で切り貼り・継ぎ目なし）〔実測・1件〕
- 同じ構図で描き直した版どうしは、コマの溝の位置がそろうので、**段ごとに手元で差し替え**られる（上の段は版A・下の段は版B）〔実測・1件〕
- 読む順の取り違えは、吹き出しの位置や尻尾を編集で入れ替えるより、**二人の立ち位置を入れかえてそのコマを描き直す**ほうが早かった（編集2回で直りきらず→描き直し1回で通った）〔実測・1件〕

### 着色の編集（白黒の完成ページ → 平らな色）

白黒の完成ページを `-i` の1枚目、キャラ参照を2・3枚目に。線・コマ・吹き出し・文字は残り、平らな色だけが乗った。トーンが一部うすくなる・肌にうっすら色がつく、は起きた〔実測・1件〕。

```
COLORIZE the first attached image (a finished black-and-white manga page). This is a coloring job only, like a colorist working on top of finished inks.
KEEP EXACTLY: every line, every panel, the layout, all screentones, every balloon, every piece of Japanese text and handwritten lettering, all faces and poses. Do not redraw, restyle, move, add or remove anything. Balloons, narration box and the paper stay white. Text stays black.
ADD ONLY flat spot colors (no gradients, no glossy shading, no highlights):
- <キャラ1の見分け方（例：Girl with the braided crown hairstyle and bow）>: hair <色>, bow <色>, dress <色>, eyes <色>.
- <キャラ2の見分け方（例：Girl with the ponytail）>: hair <色>, hoodie <色と柄>, ...
- <その日の小物: flat pastel colors ...>
- Skin stays paper white with at most a light blush. Backgrounds stay white.
The second and third attached images are character design references for colors only. Keep ALL screentone dots exactly as they are and keep skin pure paper white.
```

- 🔴 白黒用の言い換え（「黒髪」「水玉」など）を色の指定に書かない。色つきの絵にそのまま流れ込んだ〔実測・1件〕。色の行は本来の色で書く。

---

## 1-8. 回し方の補足

- **プロンプトの中身は標準入力で渡す**。Codex に「このファイルを読んで」と頼むと、ファイルを読むコマンドが方針で拒否されて画像なしで終わったことがある〔実測・1回〕。標準入力に変えてからは失敗なし〔実測・8回〕：

  ```bash
  cat common.txt prompt_p1.txt | codex exec -s workspace-write --skip-git-repo-check \
    "The page prompt is given on stdin. Do NOT read any files. Use the image_gen tool to generate ONE image following it exactly. The attached images are: 1 = previous page, 2 = character A reference, 3 = character B reference. In the final message, state the tool used, the saved path, and any failure reason." \
    -i prev_page.png -i charaA_ref.png -i charaB_ref.png
  ```
  - 指示文は英語（ASCII）・`-i` は最後（skills/01）
- 保存できなかったときの回収と、並列で走らせない理由は [05_pitfalls.md](05_pitfalls.md)
