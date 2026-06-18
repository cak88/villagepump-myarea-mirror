# villagepump-myarea-mirror

Scrapbox / Cosense の共同日記ページに書いた「自分の場所」を、自分のプロジェクトの同名ページへ
機械的に転記するツール。[井戸端](https://scrapbox.io/villagepump/)（villagepump）のような、
各人が自分のアイコンの下に書く形式の共同日記を、自分のプロジェクトへミラーするのを想定している。

## 何をするか

共同日記では、各人が自分のアイコン記法 `[名前.icon]` を col0（行頭インデント無し）に置き、その下に
書く。次の人のアイコンが現れるまでが「その人の場所」。このツールは設定したアイコンの場所を
切り出し、転記先プロジェクトの**同名ページ**へ転記する。

- 切り出し範囲 = col0 の `[<icon>.icon...]` 行から、次の col0 `[名前.icon]` 行の直前まで
- その場所の他者のリアクション・リプライ（「イイね!」や `…[sta.icon]` など）も**そのまま残す**。
  会話の流れごと保存するのが仕様
- 一日に複数箇所へ書いていれば各ブロックを順に連結する

### 日記ページのときの追加挿入

タイトルが `YYYY/MM/DD` 形式のページ（＝日記ページ）のときは、転記先に次も足す:

- ページ上部の2行（`第N週: …` と `YYYY年 …％経過`）をタイトル直下に
- 後ろから2行目のナビ行（`[前日.icon] ← 当日 → [翌日.icon]`）を末尾に
  → 転記先で自分の前日／翌日ページへのナビとして働き、日記が日々チェーンする

### 転記元への参照リンク化（リンク切れ対策）

他者のアイコンやページリンクは、転記先に対応ページが無いとリンク切れ／孤児リンクになる。既定で
`[/<source_project>/...]`（転記元へのクロスプロジェクト参照）に変換し、転記元側を指させる。

- 他者アイコン `[taktamur.icon]` → `[/<source_project>/taktamur.icon]`
- 転記元ページリンク `[ページ名]` → `[/<source_project>/ページ名]`

変換しない（＝別物なので触らない）もの:

- 自分のアイコン `[<icon>.icon]` … 転記先で解決する
- 日付アイコン `[2026/06/15.icon]` 等（ナビ行）… 自分の前日/翌日ページへ向けたい
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
```

既定は **dry-run**。中身を確認してから `--publish` を付けて確定する二段構え。転記先が既にある
ときは事故防止で中断する（作り直すなら `--overwrite`）。日記以外の任意ページ名も指定でき、その
場合は上部2行・ナビ行は付かず、自分のブロックだけを転記する。

`--config PATH` で別の設定ファイルを指定できる。

## 設定（config.toml）

| キー | 説明 |
| --- | --- |
| `source_project` | 転記元（共同日記のあるプロジェクト名。例: `villagepump`） |
| `dest_project` | 転記先（自分のプロジェクト名） |
| `icon` | 転記元での自分のアイコン名（`[名前.icon]` の「名前」） |
| `origin` | Cosense のオリジン（既定 `https://scrapbox.io`） |
| `timezone` | `today` / `yesterday` を解決するタイムゾーン（既定 `Asia/Tokyo`） |

## ライセンス

MIT
