"""Run without installing pytest; all fixtures live under ignored local/.

No fixture file is deleted, and no pre-existing work or version is overwritten.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import studio


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(studio.json_bytes(value))


def get(path):
    return json.loads(path.read_text(encoding="utf-8"))


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Acceptance(unittest.TestCase):
    @classmethod
    def command(cls, *args, ok=True):
        result = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "tools" / "studio.py"),
                                 str(args[0]), str(cls.work), *map(str, args[1:])],
                                cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True,
                                encoding="utf-8", timeout=60,
                                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        if (result.returncode == 0) != ok:
            raise AssertionError(f"{args}: exit={result.returncode}\n{result.stdout}\n{result.stderr}")
        return result

    @classmethod
    def setUpClass(cls):
        storage = ROOT / "local" / "acceptance"
        storage.mkdir(parents=True, exist_ok=True)
        cls.work = Path(tempfile.mkdtemp(prefix="検収 空白 ", dir=storage))
        cls.book_path = cls.work / "book.json"
        cls.book = {"title": "ダミー検収作品", "author": "検収用作者", "pages": [2, 3, 4, 5],
                    "first_page_side": "right", "binding": "right", "trim_mm": [148, 210],
                    "bleed_mm": 3, "safe_mm": {"top": 10, "bottom": 10, "outer": 10, "gutter": 15},
                    "output": {"mode": "gray", "dpi": 600, "size_px": [3638, 5102]},
                    "max_upscale": None, "spreads": [[4, 5]], "publish": ["print_jp"]}
        put(cls.book_path, cls.book)
        cls.specs = {}
        for number in (2, 3, 4):
            name = f"p{number:02d}" if number < 4 else "p04-05"
            folder = cls.work / name
            panels = ([{"id": "k1", "order": 1, "box": [12, 12, 76, 76],
                        "bleed": ["top", "outer"]}] if number < 4 else [
                            {"id": "left", "order": 2, "box": [4, 10, 40, 75]},
                            {"id": "right", "order": 1, "box": [56, 10, 40, 75]}])
            for panel in panels:
                panel.update({"scene": "A dummy panel", "chars": [], "lines": []})
            panels[-1]["lines"] = [{"type": "balloon", "who": "tester", "shape": "ellipse",
                                     "x": 65 if number < 4 else 68, "y": 20,
                                     "w": 15, "h": 20, "tail": [70, 43],
                                     "size": 1.4 if number < 4 else 0.9, "text": "検収\n台詞"}]
            spec = {"page": number, "panel_count": len(panels), "panels": panels,
                    "lines": [{"type": "text", "x": 25 if number < 4 else 20, "y": 55,
                               "w": 10, "h": 10, "size": 1, "text": "効果", "rotate": -5}]}
            cls.specs[number] = spec
            put(folder / "page.json", spec)
            # Deliberately not the manuscript aspect ratio.
            Image.new("RGB", (800, 600), "white").save(folder / "draft_source.png")
        report = cls.command("plan").stdout
        if "原寸" not in report or "1024" not in report:
            raise AssertionError(report)
        for number in (2, 3, 4):
            name = f"p{number:02d}" if number < 4 else "p04-05"
            cls.command("cut", number, "--draft", cls.work / name / "draft_source.png", "--overlay")
            cls.command("draw", number, "--engine", "dummy", "--seed", 17)
            for panel in cls.specs[number]["panels"]:
                cls.command("pick", number, panel["id"], 1)
            cls.command("build", number)
        cls.command("check")
        cls.command("export")
        print("\nPASS plan → cut --overlay → draw(dummy) → pick → build → check → export", flush=True)

    def restore_book(self):
        put(self.book_path, self.book)

    def test_01_exact_png_format_dpi_and_background(self):
        for index in range(1, 5):
            path = self.work / "out" / f"{index:03d}.png"
            studio.check_image(path, (3638, 5102))
            with Image.open(path) as image:
                self.assertEqual(image.mode, "L")
                self.assertNotIn("transparency", image.info)
                # Bottom margin is blank in all four physical pages.
                self.assertEqual(image.getpixel((1800, 5101)), 255)
        with zipfile.ZipFile(self.work / "out" / "submission.zip") as archive:
            self.assertEqual(archive.namelist(), ["001.png", "002.png", "003.png", "004.png", "submission.txt"])
            self.assertIsNone(archive.testzip())
        note = (self.work / "out" / "submission.txt").read_text(encoding="utf-8")
        for value in ("ダミー検収作品", "検収用作者", "4", "600", "グレースケール"):
            self.assertIn(value, note)

    def test_02_rebuild_is_byte_identical(self):
        for number, name in ((2, "p02"), (3, "p03"), (4, "p04-05")):
            paths = [self.work / name / file for file in ("page.png", "page_notext.png", "letter_layer.png", "build.json")]
            before = [file_hash(path) for path in paths]
            self.command("build", number)
            self.assertEqual([file_hash(path) for path in paths], before)

    def test_03_cut_percent_padding_and_overlay(self):
        with Image.open(self.work / "p02" / "panels" / "k1" / "draft.png") as image:
            # 4% of panel width/height on each edge, floor/ceil to include pixels.
            self.assertEqual(image.size, (658, 494))
        with Image.open(self.work / "p02" / "draft_overlay.png") as image:
            self.assertEqual(image.size, (800, 600))
            self.assertEqual(image.getpixel((96, 72)), (255, 0, 0))
        self.command("cut", 2, "--draft", self.work / "p02" / "draft_source.png", ok=False)

    def test_cut_uses_optional_draft_box_for_crop_and_overlay(self):
        work = Path(tempfile.mkdtemp(prefix="shifted-draft-", dir=self.work.parent))
        put(work / "book.json", self.book)
        panel = dict(self.specs[2]["panels"][0], draft_box=[20, 25, 55, 40])
        put(work / "p02/page.json", dict(self.specs[2], panels=[panel]))
        draft = work / "p02/draft_source.png"
        Image.new("RGB", (800, 600), "white").save(draft)
        book = studio.Book(work)
        studio.cut(book, 2, draft, pad=0, overlay=True)
        with Image.open(work / "p02/panels/k1/draft.png") as crop:
            self.assertEqual(crop.size, (440, 240))
        with Image.open(work / "p02/draft_overlay.png") as overlay:
            self.assertEqual(overlay.getpixel((160, 150)), (255, 0, 0))
            self.assertEqual(overlay.getpixel((96, 72)), (255, 255, 255))

    def test_plan_template_matches_cut_coordinates_and_omits_lettering(self):
        path = self.work / "p02" / "draft_template.png"
        self.command("plan", 2, "--template")
        with Image.open(path) as template:
            self.assertEqual(template.mode, "L")
            self.assertEqual(template.size, (1095, 1536))
            self.assertEqual(template.getpixel((131, 184)), 0)
            self.assertEqual(template.getpixel((794, 307)), 212)
            self.assertEqual(template.getpixel((794, 460)), 255)
        digest = file_hash(path)
        self.command("plan", 2, "--template", ok=False)
        self.assertEqual(file_hash(path), digest)

    def test_04_spread_right_is_younger_and_overlap_is_real_art(self):
        with Image.open(self.work / "p04-05" / "page.png") as source:
            self.assertEqual(source.size, (7134, 5102))
            for number, rect in ((3, (3496, 0, 7134, 5102)), (4, (0, 0, 3638, 5102))):
                with Image.open(self.work / "out" / f"{number:03d}.png") as output:
                    self.assertIsNone(ImageChops.difference(output, source.crop(rect)).getbbox())
            with Image.open(self.work / "out" / "003.png") as right, Image.open(self.work / "out" / "004.png") as left:
                self.assertIsNone(ImageChops.difference(right.crop((0, 0, 142, 5102)),
                                                        left.crop((3496, 0, 3638, 5102))).getbbox())
        mapping = get(self.work / "out" / "export.json")["pages"]
        self.assertEqual([(m["page"], m["half"]) for m in mapping],
                         [(2, None), (3, None), (4, "right"), (5, "left")])

    def test_05_box_and_lines_invalidate_check_and_export(self):
        path = self.work / "p02" / "page.json"
        for what in ("box", "lines"):
            changed = json.loads(json.dumps(self.specs[2]))
            if what == "box":
                changed["panels"][0]["box"][0] += 1
            else:
                changed["panels"][0]["lines"][0]["text"] += "！"
            try:
                put(path, changed)
                self.command("check", 2, ok=False)
                self.command("export", ok=False)
            finally:
                put(path, self.specs[2])

    def test_06_pick_change_invalidates_build_without_overwriting_version(self):
        panel = self.work / "p02" / "panels" / "k1"
        hashes = {name: file_hash(panel / name) for name in ("v1.png", "v1.json")}
        self.command("draw", 2, "k1", "--engine", "dummy", "--seed", 19, "--size", "1024x1024")
        self.assertEqual({name: file_hash(panel / name) for name in hashes}, hashes)
        self.command("pick", 2, "k1", 2)
        try:
            self.command("check", 2, ok=False)
            self.command("export", ok=False)
        finally:
            self.command("pick", 2, "k1", 1)

    def test_07_upscale_limit_stops_before_outputs_are_overwritten(self):
        before = file_hash(self.work / "p02" / "page.png")
        changed = dict(self.book, max_upscale=0.5)
        try:
            put(self.book_path, changed)
            result = self.command("build", 2, ok=False)
            self.assertIn("拡大率", result.stderr)
            self.command("check", 2, ok=False)
            self.command("export", ok=False)
            self.assertEqual(file_hash(self.work / "p02" / "page.png"), before)
        finally:
            self.restore_book()

    def test_08_sides_flip_without_editing_page_and_bleed_follows(self):
        book = studio.Book(self.work)
        self.assertEqual((book.side(2), book.side(3)), ("right", "left"))
        right, left = studio.Page(book, [2]), studio.Page(book, [3])
        self.assertEqual(right.box(right.panels[0])[2], 3638)
        self.assertEqual(left.box(left.panels[0])[0], 0)
        try:
            put(self.book_path, dict(self.book, first_page_side="left", spreads=[]))
            flipped = studio.Book(self.work)
            page = studio.Page(flipped, [2])
            self.assertEqual(page.box(page.panels[0])[0], 0)
            self.assertEqual(flipped.side(2), "left")
        finally:
            self.restore_book()

    def test_09_safety_and_gutter_failures(self):
        path = self.work / "p02" / "page.json"
        for x, y in ((0, 20), (5, 20), (65, 0), (91, 20)):
            changed = json.loads(json.dumps(self.specs[2]))
            changed["panels"][0]["lines"][0].update(x=x, y=y, w=5, h=10)
            try:
                put(path, changed)
                self.command("build", 2, ok=False)
                self.command("check", 2, ok=False)
            finally:
                put(path, self.specs[2])
        path = self.work / "p04-05" / "page.json"
        changed = json.loads(json.dumps(self.specs[4]))
        changed["panels"][1]["lines"][0].update(x=48, w=4)
        try:
            put(path, changed)
            self.command("build", 4, ok=False)
            self.command("check", 4, ok=False)
        finally:
            put(path, self.specs[4])

    def test_10_missing_duplicate_box_and_panel_count_fail(self):
        path = self.work / "p02" / "page.json"
        for kind in ("missing", "duplicate", "count"):
            changed = json.loads(json.dumps(self.specs[2]))
            if kind == "missing":
                changed["panels"][0].pop("box")
            elif kind == "duplicate":
                changed["panels"].append(dict(changed["panels"][0]))
            else:
                changed["panel_count"] = 9
            try:
                put(path, changed)
                self.command("cut", 2, "--draft", self.work / "p02" / "draft_source.png", ok=False)
            finally:
                put(path, self.specs[2])

    def test_11_exclusive_numbering_under_concurrent_draw(self):
        folder = self.work / "p03" / "panels" / "k1"
        before = file_hash(folder / "v1.json")
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.command, "draw", 3, "k1", "--engine", "dummy", "--size", "80x100")
                       for _ in range(2)]
            for future in futures:
                future.result()
        self.assertTrue((folder / "v2.png").exists())
        self.assertTrue((folder / "v3.png").exists())
        self.assertEqual(file_hash(folder / "v1.json"), before)

    def test_12_unregistered_references_and_path_traversal_fail(self):
        path = self.work / "p02" / "page.json"
        changed = json.loads(json.dumps(self.specs[2]))
        changed["panels"][0]["chars"] = ["unknown"]
        try:
            put(path, changed)
            self.command("draw", 2, "--engine", "dummy", ok=False)
            changed["panels"][0]["id"] = "../escape"
            put(path, changed)
            self.command("plan", 2, ok=False)
        finally:
            put(path, self.specs[2])

    def test_13_reference_metadata_and_policy_constants(self):
        record = get(self.work / "p02" / "panels" / "k1" / "v1.json")
        self.assertEqual(record["source"], "chat")
        self.assertFalse(record["contains_ph3"])
        self.assertEqual(record["derived_from"], [])
        self.assertEqual(record["seed"], 17)
        self.assertIn("All ages", record["prompt"])
        self.assertIn("nsfw", record["negative_prompt"])
        self.assertEqual(record["references_sha256"]["p02/panels/k1/draft.png"],
                         file_hash(self.work / "p02" / "panels" / "k1" / "draft.png"))
        manifest = get(self.work / "p02" / "build.json")
        self.assertEqual(manifest["panels"][0]["upscale"], 1)
        self.assertFalse(manifest["contains_ph3"])
        self.command("draw", 2, "--engine", "ph3", ok=False)

    def test_14_ph3_recursive_ancestry_and_publish_fail_closed(self):
        meta = self.work / "p02" / "panels" / "k1" / "v1.json"
        original = meta.read_bytes()
        ancestor = self.work / "ancestry" / "ph3.json"
        put(ancestor, {"engine": "ph3", "derived_from": []})
        record = json.loads(original)
        record["derived_from"] = ["ancestry/ph3.json"]
        try:
            put(meta, record)
            put(self.book_path, dict(self.book, publish=["print_jp", "x"]))
            result = self.command("build", 2, ok=False)
            self.assertIn("ph3", result.stderr)
            self.command("check", 2, ok=False)
            self.command("export", ok=False)
            put(self.book_path, dict(self.book, publish=["electronic"]))
            self.command("build", 2, ok=False)
            self.restore_book()
            result = self.command("build", 2, ok=False)
            self.assertIn("MiniMax H3", result.stderr)
            ph3, ancestry = studio.ancestry(studio.Book(self.work), "p02/panels/k1/v1.json")
            self.assertTrue(ph3)
            self.assertIn("ancestry/ph3.json", ancestry)
            record["engine"] = "codex"
            put(meta, record)
            self.command("build", 2, ok=False)
            record["engine"] = "dummy"
            record["derived_from"] = ["p02/panels/k1/v1.json"]
            put(meta, record)
            self.command("build", 2, ok=False)
        finally:
            meta.write_bytes(original)
            self.restore_book()

    def test_15_tampered_outputs_fail(self):
        path = self.work / "p02" / "page.png"
        original = path.read_bytes()
        try:
            for mode, dims, dpi in (("RGBA", (3638, 5102), (600, 600)),
                                    ("L", (300, 400), (600, 600)),
                                    ("L", (3638, 5102), (72, 72))):
                Image.new(mode, dims, "white").save(path, dpi=dpi)
                self.command("check", 2, ok=False)
                self.command("export", ok=False)
        finally:
            path.write_bytes(original)

    def test_16_repeated_export_keeps_original_submission(self):
        original = file_hash(self.work / "out" / "submission.zip")
        self.command("export")
        self.assertEqual(file_hash(self.work / "out" / "submission.zip"), original)
        self.assertTrue((self.work / "out" / "run-001" / "submission.zip").exists())
        self.assertEqual(file_hash(self.work / "out" / "run-001" / "submission.zip"), original)

    def test_17_configurable_gutter_bleed(self):
        try:
            put(self.book_path, dict(self.book, spread_gutter_bleed_mm=0))
            page = studio.Page(studio.Book(self.work), [4, 5])
            right = studio.split_page(page, 4)
            left = studio.split_page(page, 5)
            self.assertEqual(right.crop((0, 0, 71, 5102)).getextrema(), (255, 255))
            self.assertEqual(left.crop((3567, 0, 3638, 5102)).getextrema(), (255, 255))
        finally:
            self.restore_book()

    def test_18_balloon_overflow_and_required_notices_fail(self):
        path = self.work / "p02" / "page.json"
        changed = json.loads(json.dumps(self.specs[2]))
        changed["panels"][0]["lines"][0]["text"] = "あ" * 150
        try:
            put(path, changed)
            result = self.command("build", 2, ok=False)
            self.assertIn("はみ出", result.stderr)
        finally:
            put(path, self.specs[2])
        try:
            put(self.book_path, dict(self.book, required_notices=["非公式のファンメイド作品"]))
            self.command("build", 2, ok=False)
            self.command("check", 2, ok=False)
        finally:
            self.restore_book()

    def test_19_lettering_outside_panels_is_valid_white_background(self):
        path = self.work / "p02" / "page.json"
        changed = json.loads(json.dumps(self.specs[2]))
        changed["panels"][0]["box"] = [12, 12, 40, 40]
        changed["panels"][0]["bleed"] = []
        changed["panels"][0]["lines"] = []
        changed["lines"] = [{"type": "text", "x": 70, "y": 65, "w": 10, "h": 15,
                             "size": 1.2, "text": "余白"}]
        try:
            put(path, changed)
            self.command("build", 2)
            self.command("check", 2)
        finally:
            put(path, self.specs[2])
            self.command("build", 2)

    def test_20_registered_reference_hashes_and_approval(self):
        path = self.work / "p02" / "page.json"
        folder = self.work / "p02" / "panels" / "k1"
        ref = self.work / "refs" / "test.png"
        ref.parent.mkdir(exist_ok=True)
        Image.new("L", (48, 64), 180).save(ref)
        registry = self.work / "refs.json"
        entry = {"original_character": {"approved": True, "files": ["refs/test.png"]}}
        put(registry, entry)
        changed = json.loads(json.dumps(self.specs[2]))
        changed["panels"][0]["chars"] = ["original_character"]
        try:
            put(path, changed)
            before = set(folder.glob("v*.json"))
            self.command("draw", 2, "k1", "--engine", "dummy", "--size", "64x96")
            new = set(folder.glob("v*.json")) - before
            self.assertEqual(len(new), 1)
            record = get(new.pop())
            self.assertEqual(record["references_sha256"]["refs/test.png"], file_hash(ref))
            entry["original_character"]["approved"] = False
            put(registry, entry)
            self.command("draw", 2, "--engine", "dummy", ok=False)
            entry["original_character"].update(approved=True, files=["../outside.png"])
            put(registry, entry)
            self.command("draw", 2, "--engine", "dummy", ok=False)
        finally:
            put(path, self.specs[2])

    def test_21_pages_array_order_is_preserved(self):
        try:
            put(self.book_path, dict(self.book, pages=[4, 5, 2, 3]))
            book = studio.Book(self.work)
            self.assertEqual(book.pages, [4, 5, 2, 3])
            self.assertEqual(book.groups(), [[4, 5], [2], [3]])
            self.assertEqual(book.side(2), "right")
        finally:
            self.restore_book()

    def test_22_final_baseline_still_passes(self):
        self.command("check")


if __name__ == "__main__":
    unittest.main(verbosity=2)
