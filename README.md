# villagepump-myarea-mirror

Scrapbox / Cosense の共同日記ページに書いた「自分の場所」を、自分のプロジェクトの同名ページへ
機械的に転記するツール（日記ページの日付区切りだけは `date_separator` で変えられる）。[井戸端](https://scrapbox.io/villagepump/)（villagepump）のような、
各人が自分のアイコンの下に書く形式の共同日記を、自分のプロジェクトへミラーするのを想定している。

## 何をするか

共同日記では、各人が自分のアイコン記法 `[名前.icon]` を col0（行頭インデント無し）に置き、その下に
書く。次の人のアイコンが現れるまでが「その人の場所」。このツールは設定したアイコンの場所を
切り出し、転記先プロジェクトの**同名ページ**へ転記する。

- 切り出し範囲 = col0 の `[<icon>.icon...]` 行から、次の col0 `[名前.icon]` 行の直前まで
- その場所の他者のリアクション・リプライ（「イイね!」や `…[sta.icon]` など）も**そのまま残す**。
  会話の流れごと保存するのが仕様
- 一日に複数箇所へ書いていれば各ブロックを順に連結する
- 転記元ページへのリンク `[/<source_project>/<title>]` を1行入れる。どこから写したかがページ
  自身に残る。位置はタイトル直下（日記ページなら `第N週` / `％経過` の2行の下）

### 日記ページのときの追加挿入

タイトルが `YYYY/MM/DD` 形式のページ（＝日記ページ）のときは、転記先に次も足す:

- ページ上部の2行（`第N週: …` と `YYYY年 …％経過`）をタイトル直下に
- 後ろから2行目のナビ行（`[前日.icon] ← 当日 → [翌日.icon]`）を末尾に
  → 転記先で自分の前日／翌日ページへのナビとして働き、日記が日々チェーンする

#### 日付区切りを変える

`date_separator = "-"` にすると、転記先での日記ページ名を `2026-09-06` の形にする。転記元の
ページ名は常に `YYYY/MM/DD` なので、ページ名だけでなく本文中の自分の日記へのリンク
（`[2026/09/05]` などのナビ行）も同じ区切りに揃える。揃えないと前日／翌日ナビが転記先で
行き先を失う。`[/<source_project>/2026/09/05]` のような転記元への参照は対象外で、そのまま残る。

既定は `"/"`（転記元と同じ、＝同名ページ）。

### 転記元への参照リンク化（リンク切れ対策）

他者のアイコンやページリンクは、転記先に対応ページが無いとリンク切れ／孤児リンクになる。既定で
`[/<source_project>/...]`（転記元へのクロスプロジェクト参照）に変換し、転記元側を指させる。

- 他者アイコン `[taktamur.icon]` → `[/<source_project>/taktamur.icon]`
- 転記元ページリンク `[ページ名]` → `[/<source_project>/ページ名]`

変換しない（＝別物なので触らない）もの:

- 自分のアイコン `[<icon>.icon]` … 転記先で解決する
- 日付アイコン `[2026/06/15.icon]` 等（ナビ行）… `[2026/06/15]` に変換（自分の前日/翌日ページへリンク）
- スラッシュを含むリンク `[/proj/page]` `[2026/06/16]` … 既に別プロジェクト参照 or その扱い
- URL を含む外部リンク `[ラベル https://...]`
- 装飾記法 `[* 見出し]` `[$ 数式]` 等、`[[太字]]`

変換せず素のまま残すなら `--no-foreign-link`。

## セットアップ

1. [cosense CLI](https://www.npmjs.com/package/@helpfeel/cosense-cli) を入れてログインする
   （転記先プロジェクトへの書き込み権限が要る）:

   ```sh
   npm install -g @helpfeel/cosense-cli
   cosense login            # Personal Access Token を設定
   cosense whoami https://scrapbox.io   # 確認
   ```

2. 設定ファイルを用意する:

   ```sh
   cp config.example.toml config.toml
   # config.toml を編集（source_project / dest_project / icon を自分の値に）
   ```

要件: Python 3.11 以上（標準ライブラリの `tomllib` を使う）。pip 依存は無し。

## 使い方

```sh
python3 villagepump_myarea_mirror.py 2026/06/16              # dry-run: 転記される本文を表示（書き込まない）
python3 villagepump_myarea_mirror.py 2026/06/16 --publish    # 転記先に同名ページを新規作成
python3 villagepump_myarea_mirror.py yesterday --publish     # 設定のタイムゾーン基準の昨日。today も可
python3 villagepump_myarea_mirror.py 2026/06/16 --publish --overwrite   # 既存ページを本文ごと作り直す
python3 villagepump_myarea_mirror.py 2026/06/16 --publish --append      # 既存ページの下へ追記する
```

既定は **dry-run**。中身を確認してから `--publish` を付けて確定する二段構え。日記以外の任意
ページ名も指定でき、その場合は上部2行・ナビ行は付かず、自分のブロックだけを転記する。

`--config PATH` で別の設定ファイルを指定できる。

### 転記先に同名ページが既にあったとき

`--overwrite` と `--append` は排他。どちらも付けなければ既定の中断になる。

| | 振る舞い |
| --- | --- |
| 既定 | 事故防止で中断する（既存ページには一切触らない） |
| `--overwrite` | タイトル行だけ残して本文を作り直す。**転記先で手を入れた分は消える** |
| `--append` | 既存の記述をそのまま残し、1行空けてその下へ本文を積む |

`--append` は、その日のページを自分で先に書いてしまった日に、井戸端ぶんを後ろへ足すためのもの。
同じ日を二度足さないよう、転記元リンク `[/<source_project>/<転記元ページ名>]` が既にあれば
「追記済み」と見て中断する（この行は転記のたびに必ず1行入るので、追記済みの印として働く）。
だから `--append` は何度走らせても増えない。日中に井戸端へ書き足したぶんまで取り込みたいなら、
`--overwrite` で作り直す。

転記先が未作成なら、どのフラグでも普通に新規作成する（違いは出ない）。

正常に「やることが無い」状態（その日は未記入＝ブロック無し／既にミラー済み・追記済み／転記元ページが未作成）は
**終了コード 0**（無人実行で job を失敗扱いにしないため）。設定欠如・認証失敗・Cosense API 失敗など
真のエラーだけ非ゼロで終わる。

## 自動実行（GitHub Actions）

`.github/workflows/mirror.yml` で定期実行できる（手動実行も可）。スケジュール・ページ指定・
フラグはその workflow を見ること（ここには書かない。二重管理を避ける）。

動かすには cosense の Personal Access Token を repo secret `COSENSE_TOKEN` に登録しておくこと
（Settings → Secrets and variables → Actions）。設定値（source/dest/icon）は秘密でないので
workflow 内で `config.toml` を生成する。

## 設定（config.toml）

| キー | 説明 |
| --- | --- |
| `source_project` | 転記元（共同日記のあるプロジェクト名。例: `villagepump`） |
| `dest_project` | 転記先（自分のプロジェクト名） |
| `icon` | 転記元での自分のアイコン名（`[名前.icon]` の「名前」） |
| `origin` | Cosense のオリジン（既定 `https://scrapbox.io`） |
| `timezone` | `today` / `yesterday` を解決するタイムゾーン（既定 `Asia/Tokyo`） |
| `date_separator` | 転記先での日記ページ名の日付区切り。`"/"`（既定・転記元と同名）または `"-"`（`2026-09-06`） |

## ライセンス

MIT
