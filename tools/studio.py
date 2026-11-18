"""Local dummy-only manga production CLI. See README for the on-disk contract."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import zipfile

from PIL import Image, ImageChops, ImageDraw

try:
    from .safety import ALL_AGES_SUFFIX, NEGATIVE_PROMPT, PH3_ALLOWED_PUBLISH
except ImportError:
    from safety import ALL_AGES_SUFFIX, NEGATIVE_PROMPT, PH3_ALLOWED_PUBLISH

REPO = Path(__file__).resolve().parents[1]
VERSION = 1


class StudioError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise StudioError(message)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def write_json(path, value, exclusive=False):
    with Path(path).open("xb" if exclusive else "wb") as stream:
        stream.write(json_bytes(value))


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def number(value, label, minimum=0, strictly=False):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value), f"{label}: 有限の数が必要です")
    require(value > minimum if strictly else value >= minimum,
            f"{label}: 値が小さすぎます")
    return value


def positive_int(value, label):
    require(isinstance(value, int) and not isinstance(value, bool) and value > 0,
            f"{label}: 正の整数が必要です")
    return value


def inside(root, relative):
    relative = Path(relative)
    require(not relative.is_absolute(), "参照・派生元は作品内の相対パスにしてください")
    result = (root / relative).resolve()
    require(result.is_relative_to(root.resolve()), "作品外へのパスは禁止です")
    return result


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]+", value),
            "コマ id は英数字・ハイフン・アンダースコアで指定してください")
    return value


class Book:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.path = self.root / "book.json"
        self.data = read_json(self.path)
        d = self.data
        self.pages = d["pages"]
        require(isinstance(self.pages, list) and self.pages, "pages が空です")
        for page in self.pages:
            positive_int(page, "pages")
        require(len(set(self.pages)) == len(self.pages), "pages が重複しています")
        self.first_side = d["first_page_side"]
        require(self.first_side in ("right", "left"), "first_page_side が不正です")
        require(d.get("binding", "right") == "right", "今回は右綴じのみ対応です")
        require(d["output"] == {"mode": "gray", "dpi": 600, "size_px": [3638, 5102]},
                "今回は gray・600dpi・3638×5102px のみ対応です")
        self.width, self.height = d["output"]["size_px"]
        self.dpi = 600
        self.trim_mm = d["trim_mm"]
        require(isinstance(self.trim_mm, list) and len(self.trim_mm) == 2,
                "trim_mm は [幅,高さ] です")
        for v in self.trim_mm:
            number(v, "trim_mm", strictly=True)
        self.bleed_mm = number(d["bleed_mm"], "bleed_mm")
        self.bleed = round(self.bleed_mm * self.dpi / 25.4)
        for total, trim in zip((self.width, self.height), self.trim_mm):
            require(abs(total - (trim + self.bleed_mm * 2) * self.dpi / 25.4) <= 1,
                    "trim_mm・bleed_mm と output.size_px が整合しません")
        self.tw, self.th = self.width - self.bleed * 2, self.height - self.bleed * 2
        require(self.tw > 0 and self.th > 0, "仕上がり寸法が不正です")
        self.safe = d["safe_mm"]
        for edge in ("top", "bottom", "outer", "gutter"):
            number(self.safe[edge], "safe_mm." + edge)
        require(self.safe["gutter"] >= 15, "綴じ側の安全域は15mm以上必要です")
        require(self.safe["top"] >= 10 and self.safe["bottom"] >= 10
                and self.safe["outer"] >= 10, "上下・外側の安全域は10mm以上必要です")
        require(self.safe["outer"] + self.safe["gutter"] < self.trim_mm[0]
                and self.safe["top"] + self.safe["bottom"] < self.trim_mm[1],
                "安全域が仕上がり枠を超えています")
        self.limit = d.get("max_upscale")
        if self.limit is not None:
            number(self.limit, "max_upscale", strictly=True)
        publish = d.get("publish")
        require(isinstance(publish, list) and publish
                and all(isinstance(v, str) and v for v in publish), "publish が不正です")
        self.spreads = d.get("spreads", [])
        require(isinstance(self.spreads, list), "spreads は配列です")
        used = set()
        for pair in self.spreads:
            require(isinstance(pair, list) and len(pair) == 2, "見開きは2ページ組です")
            a, b = pair
            require(a in self.pages and b in self.pages and b == a + 1
                    and self.pages.index(b) == self.pages.index(a) + 1,
                    "見開きは pages 内の連続する2ページにしてください")
            require(not used.intersection(pair), "見開きの指定が重複しています")
            require(self.side(a) == "right", "見開きの若い番号は右ページでなければなりません")
            used.update(pair)
        self.gutter_bleed_mm = number(d.get("spread_gutter_bleed_mm", self.bleed_mm),
                                      "spread_gutter_bleed_mm")
        require(self.gutter_bleed_mm <= self.bleed_mm,
                "spread_gutter_bleed_mm は bleed_mm 以下にしてください")
        self.gutter_bleed = round(self.gutter_bleed_mm * self.dpi / 25.4)
        for key in ("title", "author"):
            require(isinstance(d.get(key), str) and d[key].strip(), key + " が必要です")

    def side(self, page):
        return self.first_side if (page - self.pages[0]) % 2 == 0 else (
            "left" if self.first_side == "right" else "right")

    def group(self, page):
        page = int(page)
        require(page in self.pages, "指定ページが book.json にありません")
        return next((pair for pair in self.spreads if page in pair), [page])

    def groups(self, page=None):
        if page is not None:
            return [self.group(page)]
        result = []
        for n in self.pages:
            group = self.group(n)
            if group not in result:
                result.append(group)
        return result


class Page:
    def __init__(self, book, group):
        self.book, self.group = book, group
        name = f"p{group[0]:02d}" + (f"-{group[1]:02d}" if len(group) == 2 else "")
        self.folder = inside(book.root, name)
        self.path = self.folder / "page.json"
        self.data = read_json(self.path)
        require(self.data["page"] == group[0], "page.json の page がフォルダと一致しません")
        require(not any(k in self.data for k in ("size", "bleed_mm", "spread_with")),
                "寸法・見開きは book.json だけに設定してください")
        self.width = book.tw * len(group) + book.bleed * 2
        self.height = book.height
        self.trim_width = book.tw * len(group)
        self.panels = self.data["panels"]
        require(isinstance(self.panels, list) and self.panels, "panels が空です")
        ids = []
        orders = []
        for panel in self.panels:
            ids.append(identifier(panel["id"]))
            self.validate_box(panel.get("box"), "box")
            require(isinstance(panel.get("bleed", []), list)
                    and set(panel.get("bleed", [])).issubset({"top", "bottom", "outer", "gutter"}),
                    "bleed は top/bottom/outer/gutter の配列です")
            if "order" in panel:
                orders.append(positive_int(panel["order"], "order"))
            require(isinstance(panel.get("lines", []), list), "lines は配列です")
        require(len(ids) == len(set(ids)), "コマ id が重複しています")
        require(not orders or (len(orders) == len(ids) and len(set(orders)) == len(ids)),
                "order は全コマに重複なく指定してください")
        if "panel_count" in self.data:
            require(self.data["panel_count"] == len(self.panels), "コマ数と box 数が一致しません")
        require(isinstance(self.data.get("lines", []), list), "lines は配列です")

    @staticmethod
    def validate_box(box, label):
        require(isinstance(box, list) and len(box) == 4, label + " は [x,y,w,h] です")
        x, y, w, h = [number(v, label) for v in box]
        require(w > 0 and h > 0 and x + w <= 100 and y + h <= 100,
                label + " が仕上がり枠の外です")

    def panel(self, panel_id):
        return next((p for p in self.panels if p["id"] == panel_id), None)

    def panel_dir(self, panel_id):
        return inside(self.folder, "panels/" + identifier(panel_id))

    def box(self, panel, bleed=True):
        b = self.book.bleed
        x, y, w, h = panel["box"]
        rect = [b + round(x * self.trim_width / 100), b + round(y * self.book.th / 100),
                b + round((x + w) * self.trim_width / 100),
                b + round((y + h) * self.book.th / 100)]
        if bleed:
            edges = panel.get("bleed", [])
            if "top" in edges:
                rect[1] = 0
            if "bottom" in edges:
                rect[3] = self.height
            # On spreads, outer is both exterior edges; gutter is the centre,
            # which is already continuous artwork, never an exterior edge.
            if len(self.group) == 2:
                if "outer" in edges:
                    if x < 50:
                        rect[0] = 0
                    if x + w > 50:
                        rect[2] = self.width
                if "gutter" in edges:
                    seam = b + self.book.tw
                    if x + w <= 50:
                        rect[2] = seam + self.book.bleed
                    elif x >= 50:
                        rect[0] = seam - self.book.bleed
            else:
                right = self.book.side(self.group[0]) == "right"
                if ("outer" if right else "gutter") in edges:
                    rect[2] = self.width
                if ("gutter" if right else "outer") in edges:
                    rect[0] = 0
        require(rect[2] > rect[0] and rect[3] > rect[1], "コマが1px未満です")
        return rect

    def lines(self):
        return self.data.get("lines", []) + [line for p in self.panels for line in p.get("lines", [])]

    def safe_rects(self):
        b = self.book
        result = []
        for physical_index in range(len(self.group)):
            # Left physical half is the older number in a right-bound spread.
            side = "left" if len(self.group) == 2 and physical_index == 0 else (
                "right" if len(self.group) == 2 else b.side(self.group[0]))
            offset = b.bleed + b.tw * physical_index
            left_mm = b.safe["gutter"] if side == "right" else b.safe["outer"]
            right_mm = b.safe["outer"] if side == "right" else b.safe["gutter"]
            result.append((offset + left_mm * b.tw / b.trim_mm[0],
                           b.bleed + b.safe["top"] * b.th / b.trim_mm[1],
                           offset + b.tw - right_mm * b.tw / b.trim_mm[0],
                           b.bleed + b.th - b.safe["bottom"] * b.th / b.trim_mm[1]))
        return result

    def validate_lines(self):
        for i, line in enumerate(self.lines()):
            require(isinstance(line, dict), "line はオブジェクトです")
            require(line.get("type", "balloon") in ("balloon", "caption", "text"),
                    "未対応の line.type です")
            require(line.get("shape", "ellipse") in ("ellipse", "rect", "burst", "thought"),
                    "未対応の吹き出し形です")
            box = [line["x"], line["y"], line.get("w", 10), line.get("h", 10)]
            self.validate_box(box, "lines")
            number(line.get("size", 2.4), "line.size", strictly=True)
            require(isinstance(line.get("text", ""), str), "line.text は文字列です")
            rect = self.box({"box": box}, bleed=False)
            require(any(rect[0] >= r[0] and rect[1] >= r[1]
                        and rect[2] <= r[2] and rect[3] <= r[3] for r in self.safe_rects()),
                    f"lines[{i}] が安全域または綴じ側15mmに入っています")
            if line.get("tail") is not None:
                tail = line["tail"]
                require(isinstance(tail, list) and len(tail) == 2, "tail は [x,y] です")
                tx, ty = [number(v, "tail") for v in tail]
                px = self.book.bleed + tx * self.trim_width / 100
                py = self.book.bleed + ty * self.book.th / 100
                require(any(r[0] <= px <= r[2] and r[1] <= py <= r[3]
                            for r in self.safe_rects()), "しっぽが安全域の外です")


def open_image(path):
    with Image.open(path) as source:
        source.load()
        return source.copy()


def save_png(image, path, exclusive=False):
    with Path(path).open("xb" if exclusive else "wb") as stream:
        image.save(stream, format="PNG", dpi=(600, 600))


def plan(book, page=None):
    print("page\tid\t原寸 px〔実測:設定から算出〕\t1024×1024 の拡大率〔実測:設定から算出〕")
    for group in book.groups(page):
        p = Page(book, group)
        for panel in p.panels:
            x, y, r, bot = p.box(panel)
            w, h = r - x, bot - y
            print(f"{p.folder.name}\t{panel['id']}\t{w}×{h}\t{max(w / 1024, h / 1024):.6f}")


def cut(book, page, draft, pad=4, overlay=False):
    p = Page(book, book.group(page))
    number(pad, "pad")
    require(pad <= 100, "pad は100以下にしてください")
    draft = Path(draft).resolve()
    require(draft.is_relative_to(book.root), "下書きは作品フォルダ内に置いてください")
    image = open_image(draft).convert("RGB")
    targets = [p.panel_dir(panel["id"]) / "draft.png" for panel in p.panels]
    if overlay:
        targets.append(p.folder / "draft_overlay.png")
    require(not any(t.exists() for t in targets), "既存の切り出しは上書きしません。別の作品コピーで実行してください")
    marked = image.copy()
    draw = ImageDraw.Draw(marked)
    for panel, target in zip(p.panels, targets):
        x, y, w, h = panel["box"]
        # Draft uses its own aspect ratio; no final-canvas pixels are reused.
        rect = (round(x * image.width / 100), round(y * image.height / 100),
                round((x + w) * image.width / 100), round((y + h) * image.height / 100))
        dx, dy = w * pad / 100, h * pad / 100
        padded = (max(0, math.floor((x - dx) * image.width / 100)),
                  max(0, math.floor((y - dy) * image.height / 100)),
                  min(image.width, math.ceil((x + w + dx) * image.width / 100)),
                  min(image.height, math.ceil((y + h + dy) * image.height / 100)))
        require(padded[2] > padded[0] and padded[3] > padded[1], "下書きのコマが1px未満です")
        target.parent.mkdir(parents=True, exist_ok=True)
        save_png(image.crop(padded), target, exclusive=True)
        draw.rectangle(rect, outline="red", width=max(1, round(image.width / 400)))
        draw.text((rect[0] + 2, rect[1] + 2), panel["id"], fill="red")
    if overlay:
        save_png(marked, p.folder / "draft_overlay.png", exclusive=True)
    print(f"OK cut {p.folder.name}: {len(p.panels)} コマ")


def references(book, p, panel):
    result = {}
    registry_path = book.root / "refs.json"
    chars = panel.get("chars", [])
    require(isinstance(chars, list), "chars は配列です")
    registry = read_json(registry_path) if chars else {}
    for char in chars:
        require(char in registry, "未登録のキャラクター参照です: " + str(char))
        entry = registry[char]
        if isinstance(entry, dict):
            require(entry.get("approved") is True, "参照は approved=true の登録が必要です")
            files = entry["files"]
        else:
            raise StudioError("refs.json は {id: {approved: true, files: [相対パス]}} 形式です")
        require(isinstance(files, list) and files, "参照ファイルが空です")
        for name in files:
            path = inside(book.root, name)
            result[path.relative_to(book.root).as_posix()] = sha(path)
    draft = p.panel_dir(panel["id"]) / "draft.png"
    if draft.exists():
        result[draft.relative_to(book.root).as_posix()] = sha(draft)
    return result


def draw_dummy(book, page, ids, seed=None, size=None):
    p = Page(book, book.group(page))
    ids = ids or [panel["id"] for panel in p.panels]
    require(len(ids) == len(set(ids)), "コマ指定が重複しています")
    prepared = []
    for panel_id in ids:
        panel = p.panel(panel_id)
        require(panel is not None, "存在しないコマです: " + panel_id)
        rect = p.box(panel)
        dims = size or (rect[2] - rect[0], rect[3] - rect[1])
        for v in dims:
            positive_int(v, "size")
        refs = references(book, p, panel)
        prepared.append((panel, dims, refs))
    for panel, dims, refs in prepared:
        folder = p.panel_dir(panel["id"])
        folder.mkdir(parents=True, exist_ok=True)
        k = 1
        while True:
            metadata = folder / f"v{k}.json"
            if (folder / f"v{k}.png").exists():
                k += 1
                continue
            try:
                # The JSON filename is the reservation. Both files use O_EXCL;
                # interrupted reservations stay on disk and are never reused.
                stream = metadata.open("xb")
                break
            except FileExistsError:
                k += 1
        with stream:
            image = Image.new("L", dims, 205)
            painter = ImageDraw.Draw(image)
            painter.text((max(1, dims[0] // 20), max(1, dims[1] // 20)),
                         f"{panel['id']} v{k}", fill=0,
                         font_size=max(12, min(96, min(dims) // 8)))
            art_path = folder / f"v{k}.png"
            save_png(image, art_path, exclusive=True)
            x, y, w, h = panel["box"]
            record = {"engine": "dummy", "seed": seed if seed is not None else panel.get("seed", 0),
                      "prompt": str(panel.get("scene", "")) + "\n" + ALL_AGES_SUFFIX,
                      "negative_prompt": NEGATIVE_PROMPT, "references_sha256": refs,
                      "size": list(dims), "box_aspect_ratio": w * p.trim_width / (h * book.th),
                      "source": "chat", "derived_from": [], "contains_ph3": False,
                      "created_at": datetime.now(timezone.utc).isoformat(),
                      "image_sha256": sha(art_path)}
            stream.write(json_bytes(record))
        print(f"OK draw {p.folder.name}/{panel['id']}/v{k} {dims[0]}×{dims[1]}")


def version_record(p, panel_id, k):
    positive_int(k, "版番号")
    folder = p.panel_dir(panel_id)
    art, meta = folder / f"v{k}.png", folder / f"v{k}.json"
    record = read_json(meta)
    required = {"engine", "seed", "prompt", "references_sha256", "size", "box_aspect_ratio",
                "source", "derived_from", "created_at", "image_sha256", "contains_ph3"}
    require(required.issubset(record), "版メタデータの必須項目がありません")
    require(record["source"] in ("chat", "comfy"), "版の source が不正です")
    require(record["image_sha256"] == sha(art), "不変の版画像が変更されています")
    require(isinstance(record["derived_from"], list), "derived_from は配列です")
    with Image.open(art) as image:
        require(list(image.size) == record["size"], "版の記録寸法と画像が一致しません")
    return art, meta, record


def pick(book, page, panel_id, k):
    p = Page(book, book.group(page))
    require(p.panel(panel_id) is not None, "存在しないコマです")
    version_record(p, panel_id, k)
    write_json(p.panel_dir(panel_id) / "pick.json", {"version": k})
    print(f"OK pick {p.folder.name}/{panel_id} v{k}")


def ancestry(book, relative, visiting=None):
    """Ancestry is resolved recursively, hashed, and checked for cycles."""
    visiting = set() if visiting is None else visiting
    path = inside(book.root, relative)
    require(path.suffix == ".json", "derived_from は版 JSON の相対パスです")
    key = path.relative_to(book.root).as_posix()
    require(key not in visiting, "derived_from が循環しています")
    visiting.add(key)
    record = read_json(path)
    require(isinstance(record.get("engine"), str), "派生元の engine がありません")
    inherited = record.get("derived_from", [])
    require(isinstance(inherited, list), "派生元の derived_from が不正です")
    contains = record["engine"].lower() in ("ph3", "p-h3", "minimax_h3") or bool(record.get("contains_ph3"))
    hashes = {key: sha(path)}
    for parent in inherited:
        ph3, parent_hashes = ancestry(book, parent, visiting)
        contains |= ph3
        hashes.update(parent_hashes)
    visiting.remove(key)
    if record["engine"] == "codex":
        require(not contains, "ph3 由来を codex に渡すことはできません")
    return contains, hashes


def inputs(p, warn=False):
    book = p.book
    panels = []
    contains_ph3 = False
    for panel in p.panels:
        folder = p.panel_dir(panel["id"])
        pick_path = folder / "pick.json"
        k = read_json(pick_path)["version"]
        art, meta, record = version_record(p, panel["id"], k)
        ph3, inherited = ancestry(book, meta.relative_to(book.root).as_posix())
        contains_ph3 |= ph3
        rect = p.box(panel)
        w, h = rect[2] - rect[0], rect[3] - rect[1]
        sw, sh = record["size"]
        focus = panel.get("focus", [0.5, 0.35])
        require(isinstance(focus, list) and len(focus) == 2, "focus は [x,y] です")
        for v in focus:
            require(number(v, "focus") <= 1, "focus は0〜1です")
        zoom = number(panel.get("zoom", 1), "zoom", minimum=1)
        # Ceiling the resized axes matches the actual PIL fit (no hidden extra scale).
        scale = max(w / sw, h / sh) * zoom
        resized = [max(w, math.ceil(sw * scale - 1e-9)), max(h, math.ceil(sh * scale - 1e-9))]
        actual = max(resized[0] / sw, resized[1] / sh)
        if book.limit is not None:
            require(actual <= book.limit + 1e-12,
                    f"{panel['id']}: 拡大率 {actual:.6f} が上限 {book.limit} を超えています")
        if warn and actual > 1:
            print(f"警告 {panel['id']}: 拡大率 {actual:.6f}（上限 {book.limit}）", file=sys.stderr)
        panels.append({"id": panel["id"], "version": k, "pick_sha256": sha(pick_path),
                       "image_sha256": sha(art), "metadata_sha256": sha(meta),
                       "ancestry_sha256": inherited, "source_size": [sw, sh],
                       "target_size": [w, h], "resized_size": resized,
                       "upscale_xy": [w / sw, h / sh], "upscale": actual})
    if contains_ph3:
        require(set(book.data["publish"]).issubset(PH3_ALLOWED_PUBLISH),
                "ph3 由来のページをこの publish に書き出せません")
    return {"schema_version": VERSION, "book_sha256": sha(book.path), "page_sha256": sha(p.path),
            "pages": p.group, "size": [p.width, p.height],
            "page_sides": {str(n): book.side(n) for n in p.group},
            "contains_ph3": contains_ph3, "panels": panels,
            "guides": False, "background": 255}


def check_attribution(p, contains_ph3=False):
    # Notices belong on the work's opening or final manuscript, not every panel.
    requirements = p.book.data.get("required_notices", [])
    require(isinstance(requirements, list) and all(isinstance(x, str) and x for x in requirements),
            "required_notices は空でない文字列の配列です")
    chars = {c for panel in p.panels for c in panel.get("chars", [])}
    if chars.intersection({"nike", "nikechan", "AIニケちゃん"}):
        requirements = list(requirements) + ["非公式のファンメイド作品", "AIニケちゃん"]
    if contains_ph3:
        requirements = list(requirements) + ["MiniMax H3"]
    if not requirements:
        return
    text_parts = []
    notice_groups = [p.book.group(p.book.pages[0]), p.book.group(p.book.pages[-1])]
    for index, group in enumerate(notice_groups):
        if index and group == notice_groups[0]:
            continue
        try:
            notice_page = Page(p.book, group)
        except FileNotFoundError:
            continue
        notice_page.validate_lines()
        text_parts.extend(line.get("text", "") for line in notice_page.lines())
    text = "\n".join(text_parts)
    for notice in requirements:
        require(notice in text, "安全域の lines に必要な表示がありません: " + notice)


def build(book, page):
    p = Page(book, book.group(page))
    p.validate_lines()
    snapshot = inputs(p, warn=True)
    check_attribution(p, snapshot["contains_ph3"])
    canvas = Image.new("L", (p.width, p.height), 255)
    painter = ImageDraw.Draw(canvas)
    for panel, info in zip(p.panels, snapshot["panels"]):
        rect = p.box(panel)
        w, h = info["target_size"]
        image = open_image(p.panel_dir(panel["id"]) / f"v{info['version']}.png").convert("L")
        image = image.resize(info["resized_size"], Image.Resampling.LANCZOS)
        fx, fy = panel.get("focus", [0.5, 0.35])
        x = min(max(round(image.width * fx - w / 2), 0), image.width - w)
        y = min(max(round(image.height * fy - h / 2), 0), image.height - h)
        canvas.paste(image.crop((x, y, x + w, y + h)), (rect[0], rect[1]))
        if panel.get("border", True):
            mm = number(panel.get("border_mm", p.data.get("border_mm", 0.3)), "border_mm", strictly=True)
            painter.rectangle((rect[0], rect[1], rect[2] - 1, rect[3] - 1),
                              outline=0, width=max(1, round(mm * book.dpi / 25.4)))
    try:
        from .lettering import render_layer
    except ImportError:
        from lettering import render_layer
    layer, bounds = render_layer(p)
    final = canvas.convert("RGBA")
    final.alpha_composite(layer)
    # Detect edits during rendering before publishing a build manifest.
    require(inputs(p) == snapshot, "組版中に入力が変わりました。再 build してください")
    save_png(canvas, p.folder / "page_notext.png")
    save_png(layer, p.folder / "letter_layer.png")
    save_png(final.convert("L"), p.folder / "page.png")
    snapshot["letter_bounds"] = bounds
    snapshot["outputs_sha256"] = {name: sha(p.folder / name)
                                   for name in ("page_notext.png", "letter_layer.png", "page.png")}
    write_json(p.folder / "build.json", snapshot)
    print(f"OK build {p.folder.name}: {p.width}×{p.height} L 600dpi")


def check_image(path, expected, mode="L"):
    with Image.open(path) as image:
        image.load()
        require(image.format == "PNG" and list(image.size) == list(expected), "画像の形式・大きさが違います")
        require(image.mode == mode, f"画像は {mode} でなければなりません")
        if mode == "L":
            require("transparency" not in image.info and "A" not in image.getbands(), "アルファ・透過は禁止です")
        dpi = image.info.get("dpi", (0, 0))
        require(len(dpi) == 2 and all(abs(v - 600) <= 0.01 for v in dpi), "600dpi が記録されていません")


def validate_bounds(p, bounds):
    require(isinstance(bounds, list), "文字の描画範囲の記録がありません")
    for rect in bounds:
        require(len(rect) == 4 and any(rect[0] >= r[0] and rect[1] >= r[1]
                                      and rect[2] <= r[2] and rect[3] <= r[3]
                                      for r in p.safe_rects()), "描画された文字が安全域の外です")


def check_page(book, group):
    p = Page(book, group)
    p.validate_lines()
    current = inputs(p)
    check_attribution(p, current["contains_ph3"])
    record = read_json(p.folder / "build.json")
    require(all(record.get(key) == value for key, value in current.items()),
            "古い build です。台本・pick・版・作品設定を確認し再 build してください")
    require(set(record.get("outputs_sha256", {})) == {"page.png", "page_notext.png", "letter_layer.png"},
            "出力ハッシュが不足しています")
    validate_bounds(p, record.get("letter_bounds"))
    for name, hashed in record["outputs_sha256"].items():
        require(sha(p.folder / name) == hashed, name + " が build 後に変更されています")
        check_image(p.folder / name, (p.width, p.height), "RGBA" if name == "letter_layer.png" else "L")
    # Check the actual alpha layer, including tails/outlines, against the safe mask.
    layer = open_image(p.folder / "letter_layer.png")
    forbidden = Image.new("L", layer.size, 255)
    mask_draw = ImageDraw.Draw(forbidden)
    for x1, y1, x2, y2 in p.safe_rects():
        mask_draw.rectangle((math.ceil(x1), math.ceil(y1), math.floor(x2) - 1, math.floor(y2) - 1), fill=0)
    require(ImageChops.multiply(layer.getchannel("A"), forbidden).getbbox() is None,
            "文字層の画素が安全域の外です")
    # The only background source is white. Verify every pixel outside panel/letter coverage.
    background_mask = Image.new("L", layer.size, 255)
    background_draw = ImageDraw.Draw(background_mask)
    for panel in p.panels:
        x1, y1, x2, y2 = p.box(panel)
        background_draw.rectangle((x1, y1, x2 - 1, y2 - 1), fill=0)
    # Any nonzero lettering alpha is intentional ink, including antialiased edges.
    # Treating fractional alpha as background would reject valid text in margins.
    no_lettering = layer.getchannel("A").point(lambda value: 0 if value else 255)
    background_mask = ImageChops.multiply(background_mask, no_lettering)
    final = open_image(p.folder / "page.png")
    require(ImageChops.multiply(ImageChops.invert(final), background_mask).getbbox() is None,
            "背景が白ではありません")
    print(f"OK check {p.folder.name}")
    return p


def check(book, page=None):
    return [check_page(book, group) for group in book.groups(page)]


def split_page(p, number):
    image = open_image(p.folder / "page.png")
    if len(p.group) == 1:
        return image
    b = p.book
    result = Image.new("L", (b.width, b.height), 255)
    seam = b.bleed + b.tw
    if number == p.group[0]:
        # Right half is the younger number. Its left margin is the gutter bleed.
        crop = image.crop((seam - b.gutter_bleed, 0, p.width, p.height))
        result.paste(crop, (b.bleed - b.gutter_bleed, 0))
    else:
        crop = image.crop((0, 0, seam + b.gutter_bleed, p.height))
        result.paste(crop, (0, 0))
    return result


def export(book):
    checked = check(book)  # All pages pass before any export file is created.
    out = inside(book.root, "out")
    # Never delete or replace a submission. Further exports use out/run-NNN.
    if out.exists():
        n = 1
        while True:
            candidate = out / f"run-{n:03d}"
            try:
                candidate.mkdir()
                out = candidate
                break
            except FileExistsError:
                n += 1
    else:
        out.mkdir()
    names = []
    mapping = []
    for index, number in enumerate(book.pages, 1):
        p = next(p for p in checked if number in p.group)
        name = f"{index:03d}.png"
        save_png(split_page(p, number), out / name, exclusive=True)
        check_image(out / name, (book.width, book.height))
        names.append(name)
        mapping.append({"file": name, "page": number, "sha256": sha(out / name),
                        "source": p.folder.name,
                        "half": ("right" if number == p.group[0] else "left") if len(p.group) == 2 else None})
    require(len(names) == len(book.pages), "出力ページ数が台割と一致しません")
    note = (f"作品名: {book.data['title']}\n作者名: {book.data['author']}\n"
            f"ページ数: {len(names)}\n表現色: 8bit グレースケール（L）・アルファなし・背景白\n"
            f"解像度: 600dpi / {book.width}×{book.height}px\n")
    with (out / "submission.txt").open("x", encoding="utf-8") as stream:
        stream.write(note)
    write_json(out / "export.json", {"book_sha256": sha(book.path), "pages": mapping,
                                   "spread_gutter_bleed_mm": book.gutter_bleed_mm}, exclusive=True)
    with zipfile.ZipFile(out / "submission.zip", "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in names + ["submission.txt"]:
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, (out / name).read_bytes())
    with zipfile.ZipFile(out / "submission.zip") as archive:
        require(archive.testzip() is None and archive.namelist() == names + ["submission.txt"],
                "ZIP の整合性が不正です")
    print(f"OK export: {len(names)} ページ → {out.relative_to(book.root).as_posix()}/submission.zip")


def parse_size(value):
    match = re.fullmatch(r"([1-9][0-9]*)[xX×]([1-9][0-9]*)", value)
    if not match:
        raise argparse.ArgumentTypeError("--size は WxH（正の整数）です")
    return tuple(map(int, match.groups()))


def main(argv=None):
    parser = argparse.ArgumentParser(description="漫画を原寸グレー原稿と ZIP にする（dummy のみ）")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "check", "export", "cut", "draw", "pick", "build"):
        sub = commands.add_parser(name)
        sub.add_argument("work", type=Path)
        if name in ("plan", "check"):
            sub.add_argument("page", type=int, nargs="?")
        elif name != "export":
            sub.add_argument("page", type=int)
        if name == "cut":
            sub.add_argument("--draft", required=True, type=Path)
            sub.add_argument("--overlay", action="store_true")
            sub.add_argument("--pad", type=float, default=4)
        if name == "draw":
            sub.add_argument("ids", nargs="*")
            sub.add_argument("--engine", choices=["dummy"], required=True)
            sub.add_argument("--seed", type=int)
            sub.add_argument("--size", type=parse_size)
        if name == "pick":
            sub.add_argument("id")
            sub.add_argument("version", type=int)
    args = parser.parse_args(argv)
    try:
        book = Book(args.work)
        if args.command == "plan":
            plan(book, args.page)
        elif args.command == "cut":
            cut(book, args.page, args.draft, args.pad, args.overlay)
        elif args.command == "draw":
            draw_dummy(book, args.page, args.ids, args.seed, args.size)
        elif args.command == "pick":
            pick(book, args.page, args.id, args.version)
        elif args.command == "build":
            build(book, args.page)
        elif args.command == "check":
            check(book, args.page)
        else:
            export(book)
        return 0
    except Exception as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
