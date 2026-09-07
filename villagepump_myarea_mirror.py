#!/usr/bin/env python3
"""Scrapbox/Cosense の共同日記ページから「自分の場所」を、自分のプロジェクトへ転記する。

井戸端（villagepump）のような、各人が自分のアイコン記法 `[名前.icon]` を col0（行頭インデント
無し）に置いてその下に書く共同日記を対象に、自分のアイコンの場所を切り出して同名ページへ
転記する。対象プロジェクト・アイコン名などは config.toml で設定する。

「自分の場所」= col0 の `[<icon>.icon...]` 行から、次の col0 `[name.icon]` 行の直前まで。
その場所に入っている他者のリアクション/リプライも verbatim で残す（会話の流れごと保存）。
複数箇所に書いていれば各ブロックを順に連結する。

転記元ページへのリンク `[/<source_project>/<title>]` をタイトル直下（日記なら見出し2行の下）
に1行置く。どこから写したかがページ自身に残る。

日記ページ（タイトルが `YYYY/MM/DD`）のときは次も足す:
  - ページ上部の2行（`第N週: …` と `YYYY年 …％経過`）をタイトル直下に
  - 後ろから2行目のナビ行（`[前日.icon] ← 当日 → [翌日.icon]`）を末尾に
    → 転記先で自分の前日/翌日ページへのナビとして働き、日記が日々チェーンする

他者アイコン/ページリンクは既定で `[/<source_project>/...]`（転記元へのクロスプロジェクト
参照）に変換し、転記先でのリンク切れ・孤児リンクを防ぐ。

使い方:
    villagepump_myarea_mirror.py PAGE                # dry-run: 転記される本文を表示するだけ（書き込まない）
    villagepump_myarea_mirror.py PAGE --publish      # 転記先に同名ページを作成する
    villagepump_myarea_mirror.py PAGE --publish --overwrite   # 既存ページを本文ごと作り直す

PAGE は転記元のページ名。日記なら `YYYY/MM/DD` のほか `today` / `yesterday` も可。
前提: `cosense` CLI（https://www.npmjs.com/package/@helpfeel/cosense-cli）が
インストール済み・ログイン済みで、転記先への書き込み権限があること。
"""
import argparse
import datetime
import json
import re
import subprocess
import sys
import tomllib
import urllib.parse
import zoneinfo
from dataclasses import dataclass
from pathlib import Path

ICON_RE = re.compile(r"^\[[^\]]+\.icon\]")        # col0 = その人のセクション見出し
DIARY_RE = re.compile(r"^\d{4}/\d{2}/\d{2}$")     # 日記ページのタイトル形式
NAV_RE = re.compile(r"←.*→")                      # 前日←当日→翌日 のナビ行
ICON_TOKEN_RE = re.compile(r"\[([^\[\]]+?)\.icon(\*\d+)?\]")  # [名前.icon] / [名前.icon*N]
# 単層ブラケット（[[太字]] の内側は対象外にする lookbehind/lookahead 付き）
LINK_RE = re.compile(r"(?<!\[)\[([^\[\]]+)\](?!\])")
# 自分の日記へのリンク `[YYYY/MM/DD]` / `[YYYY/MM/DD.icon]` / `[YYYY/MM/DD.icon*N]`。
# `[` の直後が数字なので `[/<project>/YYYY/MM/DD]` のような他プロジェクト参照には当たらない。
DIARY_LINK_RE = re.compile(r"\[(\d{4}/\d{2}/\d{2})((?:\.icon(?:\*\d+)?)?)\]")
# Cosense の装飾記法 `[* 太字]` `[/ 斜体]` `[$ 数式]` 等＝記号列＋空白で始まる
DECORATION_RE = re.compile(r"^[*/\-_$~%=]+\s")


@dataclass
class Config:
    source_project: str   # 転記元（共同日記のあるプロジェクト）
    dest_project: str     # 転記先（自分のプロジェクト）
    icon: str             # 転記元での自分のアイコン名
    origin: str           # Cosense のオリジン
    timezone: str         # today/yesterday 解決用のタイムゾーン
    date_separator: str = "/"  # 転記先での日記タイトルの日付区切り（"/" or "-"）


def skip(msg):
    """正常な「やることが無い」状態で終わる。真のエラー(sys.exit=1)と区別するため exit 0。
    無人実行(GitHub Actions 等)で、未記入の日・ミラー済み・転記元ページ未作成といった
    日常的な no-op を job 失敗として赤くしない／失敗通知を飛ばさないため。"""
    print(f"skip: {msg}")
    sys.exit(0)


def load_config(path):
    if not path.exists():
        sys.exit(f"config が無い: {path}\n  config.example.toml をコピーして編集してください:\n"
                 f"    cp {path.parent / 'config.example.toml'} {path}")
    with path.open("rb") as f:
        data = tomllib.load(f)
    sep = data.get("date_separator", "/")
    if sep not in ("/", "-"):
        sys.exit(f'date_separator は "/" か "-" のどちらか: {sep!r} ({path})')
    try:
        return Config(
            source_project=data["source_project"],
            dest_project=data["dest_project"],
            icon=data["icon"],
            origin=data.get("origin", "https://scrapbox.io"),
            timezone=data.get("timezone", "Asia/Tokyo"),
            date_separator=sep,
        )
    except KeyError as e:
        sys.exit(f"config に必須キーが無い: {e} ({path})")


def resolve_date(keyword, tz):
    today = datetime.datetime.now(zoneinfo.ZoneInfo(tz)).date()
    if keyword == "today":
        d = today
    elif keyword == "yesterday":
        d = today - datetime.timedelta(days=1)
    else:
        return keyword  # 既にページ名（日記なら YYYY/MM/DD）
    return d.strftime("%Y/%m/%d")


def page_url(cfg, project, title):
    return f"{cfg.origin}/{project}/{urllib.parse.quote(title, safe='')}"


def read_page(cfg, project, title):
    url = page_url(cfg, project, title)
    r = subprocess.run(["cosense", "readPage", url], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"readPage failed ({url}): {r.stderr.strip()}")
    return json.loads(r.stdout)


def extract_blocks(lines, icon):
    """col0 `[icon.icon...]` 見出しから次の col0 見出し直前までを各ブロックとして返す。"""
    head = f"[{icon}.icon]"
    n = len(lines)
    blocks, i = [], 0
    while i < n:
        if ICON_RE.match(lines[i]) and lines[i].startswith(head):
            j = i + 1
            while j < n and not ICON_RE.match(lines[j]):
                j += 1
            block = lines[i:j]
            while block and block[-1].strip() == "":  # 末尾空行を落とす
                block.pop()
            blocks.append(block)
            i = j
        else:
            i += 1
    return blocks


def diary_header(lines):
    """日記ページ上部の2行（タイトル直下）。空行は除く。"""
    return [t for t in lines[1:3] if t.strip()]


def diary_nav(lines):
    """前日←当日→翌日 のナビ行（後ろから探す）。無ければ None。"""
    for t in reversed(lines):
        if NAV_RE.search(t):
            return t
    return None


def link_foreign_icons(text, cfg):
    """他者のアイコン `[名前.icon]` を `[/<source>/名前.icon]` に変換する。
    自分のアイコンは対象外（転記先で解決するため）。
    日付アイコン `[YYYY/MM/DD.icon]` は `[YYYY/MM/DD]` に変換する（自分の
    前日/翌日ページへリンクさせるため、アイコン記法を外す）。"""
    def repl(m):
        name, mult = m.group(1), m.group(2) or ""
        if name == cfg.icon:
            return m.group(0)
        if DIARY_RE.match(name):
            return f"[{name}]"
        return f"[/{cfg.source_project}/{name}.icon{mult}]"
    return ICON_TOKEN_RE.sub(repl, text)


def link_foreign_pages(text, cfg):
    """転記元内のページリンク `[ページ名]` を `[/<source>/ページ名]` に変換する。
    除外（別物なので触らない）:
      - スラッシュを含む … 別プロジェクトリンク `[/proj/...]` や `[2026/06/16]` 等
      - URL を含む … 外部リンク `[ラベル https://...]`
      - `.icon` を含む … アイコン（link_foreign_icons が処理済み／自分のは残す）
      - 装飾記法 `[* ...]` `[$ ...]` 等
      - `[[太字]]` の内側（LINK_RE の lookaround で除外済み）"""
    def repl(m):
        x = m.group(1)
        if ("/" in x or "http" in x or ".icon" in x
                or not x.strip() or DECORATION_RE.match(x)):
            return m.group(0)
        return f"[/{cfg.source_project}/{x}]"
    return LINK_RE.sub(repl, text)


def dest_title(title, cfg):
    """転記先でのページ名。日記ページなら日付区切りを cfg.date_separator に揃える。"""
    if cfg.date_separator != "/" and DIARY_RE.match(title):
        return title.replace("/", cfg.date_separator)
    return title


def apply_date_separator(body, src_title, cfg):
    """転記先の日付表記を cfg.date_separator に揃える（タイトル・日記リンク・ナビ行）。

    転記元の日記ページ名は常に `YYYY/MM/DD` なので、転記先で別の区切りを使うなら
    タイトルだけでなく本文中の自分の日記へのリンクも直す必要がある。直さないと
    前日/翌日ナビが転記先で行き先を失う。

    link_foreign_pages の後に呼ぶこと。あちらは「`/` を含むリンク＝別プロジェクト参照
    または日付リンク」と見なして素通しする作りなので、先にハイフン化すると日付リンクが
    `[/<source_project>/YYYY-MM-DD]` に化ける。
    """
    if cfg.date_separator == "/":
        return body
    sep = cfg.date_separator
    out = []
    for i, text in enumerate(body):
        if i == 0:
            out.append(dest_title(text, cfg))
            continue
        # `[YYYY/MM/DD]` `[YYYY/MM/DD.icon]` → 区切りを置換
        text = DIARY_LINK_RE.sub(lambda m: f"[{m.group(1).replace('/', sep)}{m.group(2)}]", text)
        # ナビ行の中央にあるリンクでない当日の日付（`… ← YYYY/MM/DD → …`）
        if NAV_RE.search(text):
            text = text.replace(src_title, src_title.replace("/", sep))
        out.append(text)
    return out


def build_body(title, lines, blocks, cfg, foreign_link=True):
    """転記先ページの本文行リストを組む（1行目 = タイトル）。"""
    body = [title]
    is_diary = bool(DIARY_RE.match(title))
    if is_diary:
        body += diary_header(lines)
    # 転記元への参照。日記なら見出し2行の下、それ以外はタイトル直下に置く。
    # `/` を含むので link_foreign_pages にも apply_date_separator にも触られない。
    body.append(f"[/{cfg.source_project}/{title}]")
    for block in blocks:
        body.append("")  # 見出し/前ブロックとの区切り
        body += block
    if is_diary:
        nav = diary_nav(lines)
        if nav:
            body += ["", nav]
    if foreign_link:
        body = [link_foreign_pages(link_foreign_icons(t, cfg), cfg) for t in body]
    return apply_date_separator(body, title, cfg)


def publish(title, body_lines, cfg, overwrite):
    """title は転記先でのページ名（dest_title 済み）。"""
    proj_url = f"{cfg.origin}/{cfg.dest_project}"
    dst = read_page(cfg, cfg.dest_project, title)

    if not dst.get("persistent", False):
        prev = subprocess.run(
            ["cosense", "previewEdit", "--new", proj_url],
            input="\n".join(body_lines), capture_output=True, text=True,
        )
    else:
        if not overwrite:
            skip(f"{cfg.dest_project}/{title} は既に存在する（ミラー済み）。作り直すなら --overwrite。")
        # 作り直し: タイトル(line0)はそのまま残し、それ以外を全削除→新本文を末尾に入れる
        old = dst["lines"]
        ops = [{"delete": l["id"]} for l in old[1:]]
        new_after_title = "\n".join(body_lines[1:])
        if new_after_title:
            ops.append({"insertBefore": "_end", "text": new_after_title})
        prev = subprocess.run(
            ["cosense", "previewEdit", proj_url, dst["id"]],
            input=json.dumps({"ops": ops}), capture_output=True, text=True,
        )
    if prev.returncode != 0:
        sys.exit(f"previewEdit failed: {prev.stderr.strip()}\n{prev.stdout}")
    m = re.search(r"previewId:\s*(\S+)", prev.stdout)
    if not m:
        sys.exit(f"previewId not found:\n{prev.stdout}")
    sub = subprocess.run(
        ["cosense", "submitEdit", proj_url, m.group(1)],
        capture_output=True, text=True,
    )
    if sub.returncode != 0:
        sys.exit(f"submitEdit failed: {sub.stderr.strip()}\n{sub.stdout}")
    print(sub.stdout.strip())


def main():
    ap = argparse.ArgumentParser(description="共同日記の自分の場所を自分のプロジェクトへ転記する")
    ap.add_argument("page", help="転記元のページ名（日記は YYYY/MM/DD / today / yesterday）")
    ap.add_argument("--publish", action="store_true", help="実際に書き込む（既定は dry-run）")
    ap.add_argument("--overwrite", action="store_true", help="既存ページを本文ごと作り直す")
    ap.add_argument("--no-foreign-link", dest="foreign_link", action="store_false",
                    help="他者アイコン・ページリンクを [/<source>/...] 化せず素のまま残す")
    ap.add_argument("--config", type=Path, default=Path(__file__).parent / "config.toml",
                    help="設定ファイルのパス（既定: スクリプトと同じディレクトリの config.toml）")
    args = ap.parse_args()

    cfg = load_config(args.config)
    title = resolve_date(args.page, cfg.timezone)
    src = read_page(cfg, cfg.source_project, title)
    if not src.get("persistent", False):
        skip(f"転記元ページが無い（未作成）: {page_url(cfg, cfg.source_project, title)}")
    lines = [l["text"] for l in src["lines"]]
    blocks = extract_blocks(lines, cfg.icon)
    if not blocks:
        skip(f"{title} に [{cfg.icon}.icon] ブロックが無い（その日は未記入）")
    body_lines = build_body(title, lines, blocks, cfg, args.foreign_link)

    if not args.publish:
        print("\n".join(body_lines))
        print("\n--- dry-run（書き込んでいない）。確定するには --publish ---", file=sys.stderr)
        return
    publish(dest_title(title, cfg), body_lines, cfg, args.overwrite)


if __name__ == "__main__":
    main()
