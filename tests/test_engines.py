"""Engine and revision tests with fake generation, no service or account required."""
from io import BytesIO
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from PIL import Image, ImageDraw, PngImagePlugin

from tools import engines, studio


ROOT = Path(__file__).resolve().parents[1]


def png(size=(64, 48), fill=80, **metadata):
    return encode_png(Image.new("L", size, fill), **metadata)


def encode_png(image, **metadata):
    data = BytesIO()
    info = PngImagePlugin.PngInfo()
    for key, value in metadata.items():
        info.add_text(key, json.dumps(value))
    image.save(data, format="PNG", pnginfo=info)
    return data.getvalue()


def framed_panel():
    image = Image.new("L", (240, 160), 255)
    draw = ImageDraw.Draw(image)
    for inset, fill in ((2, 190), (3, 0), (4, 120), (5, 225)):
        draw.rectangle((inset, inset, image.width - inset - 1, image.height - inset - 1),
                       fill=fill)
    draw.ellipse((30, 30, 150, 100), fill=80)
    return image


class EngineCommands(unittest.TestCase):
    def setUp(self):
        storage = ROOT / "local" / "acceptance"
        storage.mkdir(parents=True, exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="engines-", dir=storage))
        spec = studio.read_json(ROOT / "templates" / "book.example.json")
        self.book_path = self.work / "book.json"
        studio.write_json(self.book_path, dict(spec, pages=[2], spreads=[], publish=["print_jp"]))
        self.page = self.work / "p02" / "page.json"
        self.folder = self.page.parent / "panels" / "k1"
        self.folder.mkdir(parents=True)
        self.draft = self.folder / "draft.png"
        self.draft.write_bytes(png())
        self.spec = {"page": 2, "name_ok": True, "panels": [{"id": "k1", "box": [10, 10, 80, 45],
                                           "scene": "もとの場面", "seed": 17}]}
        studio.write_json(self.page, self.spec)
        # Tests carry their own example config instead of the shared/local one.
        config = self.work / "engines.test.json"
        studio.write_json(config, {"sdxl": {"checkpoint": "test.safetensors", "loras": {
            "nek": {"file": "nek_test.safetensors", "trigger": "nek_char"},
            "nike": {"file": "nike_test.safetensors", "trigger": "nike_char"}}}})
        env = patch.dict("os.environ", MANGA_STUDIO_ENGINES=str(config))
        env.start()
        self.addCleanup(env.stop)

    def command(self, name, *args, expected=0):
        self.assertEqual(studio.main([name, str(self.work), "2", "k1", *map(str, args)]), expected)

    def metadata(self, version):
        return studio.read_json(self.folder / f"v{version}.json")

    def test_sdxl_requires_approval_for_draw_and_redo(self):
        self.spec.pop("name_ok")
        studio.write_json(self.page, self.spec)
        with patch.object(engines, "run_sdxl", return_value=png()) as run:
            self.command("draw", "--engine", "sdxl", expected=1)
            run.assert_not_called()
            self.command("draw", "--engine", "sdxl", "--size", "64x48", "--force")
            self.assertEqual(studio.read_json(self.page), self.spec)
            self.command("redo", "--scene", "未承認の場面", expected=1)
            run.assert_called_once()
            self.assertEqual(studio.read_json(self.page), self.spec)
            self.assertEqual(studio.main(["approve", str(self.work), "2"]), 0)
            self.assertEqual(studio.read_json(self.page), dict(self.spec, name_ok=True))
            self.command("draw", "--engine", "sdxl", "--size", "64x48")
            self.assertEqual(run.call_count, 2)

    def test_sdxl_duo_uses_config_and_disjoint_hooks(self):
        config = self.work / "engines.local.json"
        studio.write_json(config, {"sdxl": {"checkpoint": "test.safetensors", "loras": {
            "left": {"file": "left.safetensors", "trigger": "left_char"},
            "right": {"file": "right.safetensors", "trigger": "right_char"}}}})
        self.spec["panels"][0]["characters"] = ["left", "right"]
        studio.write_json(self.page, self.spec)

        def fake(graph, assets, provenance):
            self.assertEqual(graph["1"]["inputs"]["ckpt_name"], "test.safetensors")
            self.assertEqual(assets[next(name for name in assets if name.endswith("_draft.png"))],
                             self.draft.read_bytes())
            nodes = {node["class_type"]: node["inputs"] for node in graph.values()}
            for name in ("VAEEncode", "ImageScale", "PairConditioningCombine",
                         "PairConditioningSetDefaultCombine"):
                self.assertIn(name, nodes)
            self.assertNotIn("LoraLoaderModelOnly", nodes)
            sample = nodes["KSampler"]
            self.assertEqual((sample["denoise"], sample["seed"], sample["model"]), (0.55, 23, ["1", 0]))
            hooks = [node["inputs"]["lora_name"] for node in graph.values()
                     if node["class_type"] == "CreateHookLoraModelOnly"]
            self.assertEqual(hooks, ["left.safetensors", "right.safetensors"])
            default = graph[sample["positive"][0]]["inputs"]
            combined = graph[default["positive"][0]]["inputs"]
            masks = (("A", "left", (0, 0, 30, 48)), ("B", "right", (33, 0, 64, 48)))
            for side, char, bounds in masks:
                pair = graph[combined[f"positive_{side}"][0]]["inputs"]
                self.assertEqual(pair["set_cond_area"], "default")
                self.assertEqual(graph[pair["hooks"][0]]["inputs"]["lora_name"], f"{char}.safetensors")
                mask_name = graph[pair["mask"][0]]["inputs"]["image"]
                data = assets[mask_name]
                with Image.open(BytesIO(data)) as mask:
                    self.assertEqual(mask.getbbox(), bounds)
            self.assertFalse(provenance["contains_ph3"])
            return png()

        with patch.dict("os.environ", MANGA_STUDIO_ENGINES=str(config)), patch.object(
                engines, "run_sdxl", side_effect=fake):
            self.command("draw", "--engine", "sdxl", "--seed", 23, "--size", "64x48")
        record = self.metadata(1)
        self.assertEqual((record["size"], record["seed"], record["engine"]), ([64, 48], 23, "sdxl"))
        self.assertIn("left_char", record["regional_prompts"][0])
        self.assertIn("right_char", record["regional_prompts"][1])
        self.assertTrue(record["prompt"].endswith(studio.ALL_AGES_SUFFIX))
        log = json.loads((self.folder / "log.jsonl").read_text(encoding="utf-8"))
        self.assertGreaterEqual(log["elapsed_seconds"], 0)
        self.assertEqual(log["version"], 1)
        self.assertEqual(log["denoise"], 0.55)

    def test_sdxl_panel_options_reach_sampler_and_version(self):
        panel = self.spec["panels"][0]
        panel["characters"] = ["nek", "nike"]
        panel["sdxl"] = {"denoise": 0.72, "negative_prompt": "fused bodies",
                         "regional_prompts": {"nike": "1girl, nike_char, open hoodie"}}
        studio.write_json(self.page, self.spec)

        with patch.object(engines, "run_sdxl", return_value=png()) as run:
            self.command("draw", "--engine", "sdxl", "--size", "64x48")
        graph, _, _ = run.call_args.args
        actual = studio.sampler_settings(graph)
        self.assertEqual(actual["denoise"], 0.72)
        self.assertIn(studio.NEGATIVE_PROMPT, actual["negative_prompt"])
        self.assertIn("fused bodies", actual["negative_prompt"])
        self.assertIn("bladed staff", actual["negative_prompt"])
        left, right = actual["regional_prompts"]
        self.assertTrue(left.startswith("one character on the left, nek_char, "))
        self.assertTrue(right.startswith("1girl, nike_char, open hoodie"))
        self.assertEqual(right.count("nike_char"), 1)
        self.assertIn("two blunt wooden ends", right)
        self.assertTrue(right.endswith(studio.ALL_AGES_SUFFIX))
        record = self.metadata(1)
        self.assertEqual({key: record[key] for key in actual}, actual)
        log = json.loads((self.folder / "log.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(log["denoise"], 0.72)

    def test_invalid_sdxl_panel_options_stop_before_generation(self):
        panel = self.spec["panels"][0]
        panel["characters"] = ["nek", "nike"]
        bad_options = ([], {"denoise": 0}, {"denoise": 1.1}, {"denoise": True},
                       {"negative_prompt": []}, {"regional_prompts": {"unknown": "1girl"}},
                       {"regional_prompts": {"nike": " "}})
        with patch.object(engines, "run_sdxl") as run:
            for options in bad_options:
                with self.subTest(options=options):
                    panel["sdxl"] = options
                    studio.write_json(self.page, self.spec)
                    self.command("draw", "--engine", "sdxl", expected=1)
            run.assert_not_called()

    def test_sdxl_single_and_missing_draft(self):
        self.spec["panels"][0]["chars"] = ["nek"]
        studio.write_json(self.page, self.spec)
        with patch.object(engines, "run_sdxl", return_value=png()) as run:
            self.command("draw", "--engine", "sdxl", "--size", "64x48")
            graph, _, _ = run.call_args.args
            node_types = [node["class_type"] for node in graph.values()]
            self.assertIn("LoraLoaderModelOnly", node_types)
            self.assertNotIn("CreateHookLoraModelOnly", node_types)
            self.assertTrue(self.metadata(1)["prompt"].startswith("nek_char, "))
            self.draft.unlink()
            self.command("draw", "--engine", "sdxl", expected=1)
            run.assert_called_once()

    def test_codex_has_official_sheet_then_draft_and_accepts_actual_size(self):
        self.spec["panels"][0]["characters"] = ["nike"]
        studio.write_json(self.page, self.spec)
        ref = self.work / "official.png"
        ref.write_bytes(png(fill=100))
        registry = {"nike": {"approved": True, "files": ["official.png"]}}
        studio.write_json(self.work / "refs.json", registry)
        with patch.object(engines, "run_codex", return_value=png((33, 44))) as run:
            self.command("draw", "--engine", "codex", expected=1)
            run.assert_not_called()
            registry["nike"]["kind"] = "official_turnaround"
            studio.write_json(self.work / "refs.json", registry)
            self.command("draw", "--engine", "codex", "--size", "64x48")
            prompt, refs, work = run.call_args.args
            self.assertIn("もとの場面", prompt)
            self.assertIn("No blades", prompt)
            self.assertIn("Do not draw any frame, panel border, or white margin.", prompt)
            self.assertIn("every edge of the canvas", prompt)
            self.assertEqual((refs, work), ([ref, self.draft], self.work))
        self.assertEqual(self.metadata(1)["size"], [33, 44])

    def test_codex_trims_frame_before_saving_version(self):
        image = framed_panel()
        self.spec.pop("name_ok")
        studio.write_json(self.page, self.spec)
        with patch.object(engines, "run_codex", return_value=encode_png(image)):
            self.command("draw", "--engine", "codex")
        path = self.folder / "v1.png"
        with Image.open(path) as saved:
            self.assertEqual(saved.tobytes(), image.crop((5, 5, 235, 155)).tobytes())
        self.assertEqual(self.metadata(1)["size"], [230, 150])
        self.assertEqual(self.metadata(1)["image_sha256"], studio.sha(path))

    def test_import_trims_frame_and_preserves_comfy_metadata_and_ph3_lineage(self):
        source = self.work / "framed.png"
        workflow = {"extra": {"manga_studio": {"contains_ph3": True}}}
        graph = {"1": {"class_type": "PH3ImageConditioning"}}
        original = encode_png(framed_panel(), workflow=workflow, prompt=graph)
        source.write_bytes(original)
        self.command("import", source)
        self.assertEqual(source.read_bytes(), original)
        record = self.metadata(1)
        self.assertEqual(record["size"], [230, 150])
        self.assertTrue(record["contains_ph3"])
        with Image.open(self.folder / "v1.png") as saved:
            self.assertEqual(saved.size, (230, 150))
            self.assertEqual(studio.png_metadata(saved, "workflow"), workflow)
            self.assertEqual(studio.png_metadata(saved, "prompt"), graph)

    def test_trim_leaves_isolated_ink_and_thick_rectangles_in_place(self):
        for thickness in (None, 12):
            with self.subTest(thickness=thickness):
                image = Image.new("L", (240, 160), 255)
                draw = ImageDraw.Draw(image)
                if thickness is None:
                    draw.line((0, 1, image.width, 1), fill=0, width=2)
                else:
                    draw.rectangle((0, 0, 239, 159), outline=0, width=thickness)
                data = encode_png(image)
                self.assertEqual(studio.trim_panel_frame(data), data)

    def test_redo_compares_selected_and_keeps_pick(self):
        for fill in (30, 55):
            path = self.work / f"manual-{fill}.png"
            path.write_bytes(png(fill=fill))
            self.command("import", path)
        self.command("pick", 1)
        with patch.object(engines, "run_codex", return_value=png(fill=110)):
            self.command("redo", "--scene", "引きの構図に直す", "--engine", "codex", "--seed", 31)
        spec = studio.read_json(self.page)
        self.assertEqual(spec["panels"][0]["scene"], "引きの構図に直す")
        self.assertIn("引きの構図に直す", self.metadata(3)["prompt"])
        self.assertEqual(self.metadata(3)["seed"], 31)
        self.assertEqual(studio.read_json(self.folder / "pick.json"), {"version": 1})
        with Image.open(self.folder / "compare_v3.png") as image:
            self.assertEqual(image.size, (128, 48))
            self.assertEqual(image.getpixel((1, 1)), (30, 30, 30))
            self.assertEqual(image.getpixel((65, 1)), (110, 110, 110))
        events = [json.loads(line) for line in (self.folder / "log.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual((events[-2]["scene_before"], events[-2]["scene_after"]), ("もとの場面", "引きの構図に直す"))

    def test_redo_failed_draw_keeps_logged_scene_and_no_new_version(self):
        self.command("draw", "--engine", "dummy", "--size", "64x48")
        with patch.object(engines, "run_sdxl", side_effect=ValueError("backend failed")):
            self.command("redo", "--scene", "もう一度描く", expected=1)
        self.assertEqual(studio.read_json(self.page)["panels"][0]["scene"], "もう一度描く")
        self.assertFalse((self.folder / "v2.json").exists())
        event = json.loads((self.folder / "log.jsonl").read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual((event["previous_version"], event["engine"]), (1, "sdxl"))

    def test_pick_as_draft_keeps_history_and_sdxl_uses_promoted_version(self):
        original = self.draft.read_bytes()
        self.command("draw", "--engine", "dummy", "--size", "64x48")
        self.command("pick", 1)
        with patch.object(engines, "run_codex", return_value=png(fill=110)):
            self.command("redo", "--scene", "構図を描き直す", "--engine", "codex")
        new = (self.folder / "v2.png").read_bytes()

        self.command("pick", 2)
        self.assertEqual(self.draft.read_bytes(), original)
        self.assertTrue(studio.read_json(self.page)["name_ok"])
        self.command("pick", 2, "--as-draft")
        self.assertEqual(self.draft.read_bytes(), new)
        self.assertEqual((self.folder / "draft_v1.png").read_bytes(), original)
        self.assertEqual(studio.read_json(self.folder / "pick.json"), {"version": 2})
        self.assertNotIn("name_ok", studio.read_json(self.page))

        with patch.object(engines, "run_sdxl", return_value=png(fill=125)) as run:
            self.command("draw", "--engine", "sdxl", "--size", "64x48", expected=1)
            run.assert_not_called()
            self.assertEqual(studio.main(["approve", str(self.work), "2"]), 0)
            self.command("pick", 2, "--as-draft")
            self.assertTrue(studio.read_json(self.page)["name_ok"])
            self.assertFalse((self.folder / "draft_v2.png").exists())
            self.command("draw", "--engine", "sdxl", "--size", "64x48")
            self.assertEqual(next(iter(run.call_args.args[1].values())), new)
        self.assertIn("p02/panels/k1/v2.json", self.metadata(3)["derived_from"])

        self.command("pick", 1, "--as-draft")
        self.assertEqual((self.folder / "draft_v2.png").read_bytes(), new)
        self.assertEqual((self.folder / "draft_v1.png").read_bytes(), original)
        self.assertEqual((self.folder / "v2.png").read_bytes(), new)

    def test_review_prefers_picked_version_then_panel_then_page_draft(self):
        self.spec["panels"][0].update(box=[10, 10, 25, 25], order=2)
        self.spec["panels"].append({"id": "k2", "box": [40, 10, 25, 25], "order": 1})
        studio.write_json(self.page, self.spec)
        second = self.folder.parent / "k2"
        second.mkdir()
        (second / "draft.png").write_bytes(png(fill=170))
        source = self.work / "first-version.png"
        source.write_bytes(png(fill=40))
        self.command("import", source)
        self.command("pick", 1)
        source.write_bytes(png(fill=60))
        self.command("import", source)

        review_args = ["review", str(self.work), "2"]
        lettered = self.page.parent / "review_name.png"
        self.assertEqual(studio.main(review_args), 0)
        with Image.open(lettered) as image:
            self.assertEqual(image.getpixel((image.width // 5, image.height // 5)), 40)
            self.assertEqual(image.getpixel((image.width // 2, image.height // 5)), 170)
            self.assertEqual(studio.png_metadata(image, "manga_studio")["derived_from"],
                             ["p02/panels/k1/v1.json"])

        self.spec["panels"].append({"id": "k3", "box": [70, 10, 25, 25], "order": 3})
        studio.write_json(self.page, self.spec)
        page_source = self.page.parent / "draft_source.png"
        page_source.write_bytes(png((800, 600), fill=215))
        book = studio.Book(self.work)
        canvas, labels, _ = studio.review_canvas(studio.Page(book, [2]), None, (), ())
        self.assertEqual([item[1:] for item in labels], [(2, "v1"), (1, "下書き"), (3, "下書き")])
        self.assertEqual([canvas.getpixel((x, 120))[0] for x in (160, 400, 640)], [40, 170, 215])

    def test_review_and_draft_promotion_reject_ph3_for_sns(self):
        source = self.work / "ph3.png"
        source.write_bytes(png(fill=150))
        self.command("import", source, "--ph3")
        self.command("pick", 1)
        review_args = ["review", str(self.work), "2"]
        self.assertEqual(studio.main(review_args), 0)
        lettered = self.page.parent / "review_name.png"
        with Image.open(lettered) as image:
            self.assertTrue(studio.png_metadata(image, "manga_studio")["contains_ph3"])
        old_review = lettered.read_bytes()
        old_draft = self.draft.read_bytes()
        studio.write_json(self.book_path, dict(studio.read_json(self.book_path), publish=["x"]))
        self.assertEqual(studio.main(review_args), 1)
        self.command("pick", 1, "--as-draft", expected=1)
        self.assertEqual(lettered.read_bytes(), old_review)
        self.assertEqual(self.draft.read_bytes(), old_draft)
        self.assertTrue(studio.read_json(self.page)["name_ok"])

    def test_comfy_exports_editable_graph_and_import_preserves_png(self):
        self.spec["panels"][0]["sdxl"] = {"denoise": 0.65}
        studio.write_json(self.page, self.spec)
        self.command("comfy", "--seed", 7, "--size", "64x48")
        workflow = studio.read_json(self.folder / "comfy_workflow.json")
        self.assertEqual(workflow["version"], 0.4)
        nodes = {node["type"]: node for node in workflow["nodes"]}
        image = nodes["LoadImage"]["widgets_values"][0]
        marker = workflow["extra"]["manga_studio"]
        self.assertEqual(studio.sha(self.folder / "comfy_inputs" / image), marker["input_sha256"][image])
        self.assertEqual(nodes["KSampler"]["widgets_values"][:2], [7, "fixed"])
        self.assertEqual(nodes["KSampler"]["widgets_values"][-1], 0.65)
        self.assertEqual(nodes["ImageScale"]["widgets_values"][1:3], [64, 48])
        self.assertIn(f"/p02/k1", nodes["SaveImage"]["widgets_values"][0])
        by_id = {node["id"]: node for node in workflow["nodes"]}
        for link_id, upstream, slot, downstream, inlet, kind in workflow["links"]:
            self.assertEqual(by_id[downstream]["inputs"][inlet]["link"], link_id)
            self.assertEqual(by_id[upstream]["outputs"][slot]["type"], kind)
        source = self.work / "from_comfy.png"
        graph = {
            "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "edited in ComfyUI"}},
            "2": {"class_type": "KSampler", "inputs": {"seed": 9, "positive": ["1", 0], "denoise": 0.65}},
        }
        source.write_bytes(png(workflow=workflow, prompt=graph))
        self.command("import", source)
        self.assertEqual((self.folder / "v1.png").read_bytes(), source.read_bytes())
        self.command("pick", 1)
        record = self.metadata(1)
        self.assertEqual((record["source"], record["seed"], record["prompt"]),
                         ("comfy", 9, "edited in ComfyUI"))
        self.assertEqual(record["denoise"], 0.65)

    def test_ph3_origin_survives_import_copy_cut_and_blocks_codex(self):
        source = self.work / "ph3.png"
        source.write_bytes(png(prompt={"1": {"class_type": "PH3ImageConditioning"}}))
        self.command("import", source)
        self.assertTrue(self.metadata(1)["contains_ph3"])
        # A copied version without embedded ComfyUI metadata is still recognized by SHA.
        opaque = self.work / "opaque.png"
        opaque.write_bytes(png(fill=155))
        self.command("import", opaque, "--derived-from", "p02/panels/k1/v1.json")
        renamed = self.work / "renamed.png"
        renamed.write_bytes((self.folder / "v2.png").read_bytes())
        self.draft.unlink()
        self.assertEqual(studio.main(["cut", str(self.work), "2", "--draft", str(renamed)]), 0)
        with patch.object(engines, "run_codex") as run:
            self.command("draw", "--engine", "codex", expected=1)
            run.assert_not_called()
        for publish in ("x", "bluesky"):
            studio.write_json(self.book_path, dict(studio.read_json(self.book_path), publish=[publish]))
            self.command("import", renamed, expected=1)
            self.command("comfy", expected=1)
        self.assertFalse((self.folder / "v3.png").exists())


class AdapterTests(unittest.TestCase):
    def test_codex_reads_only_returned_session_and_places_reference_args_last(self):
        storage = ROOT / "local" / "acceptance"
        storage.mkdir(parents=True, exist_ok=True)
        home = Path(tempfile.mkdtemp(prefix="codex-fake-", dir=storage))
        expected, unrelated = str(uuid4()), str(uuid4())
        for session, fill in ((expected, 80), (unrelated, 200)):
            folder = home / "generated_images" / session
            folder.mkdir(parents=True)
            (folder / "exec-panel.png").write_bytes(png(fill=fill))
        stdout = (json.dumps({"type": "thread.started", "thread_id": expected}) + "\n").encode("utf-8")
        completed = subprocess.CompletedProcess([], 0, stdout=stdout, stderr=b"")
        refs = [home / "sheet with spaces.png", home / "draft.png"]
        with patch.dict("os.environ", CODEX_HOME=str(home)), patch.object(
                engines, "codex_binary", return_value="codex"), patch.object(
                subprocess, "run", return_value=completed) as run:
            self.assertEqual(engines.run_codex("朝の場面", refs, home), png(fill=80))
            args, = run.call_args.args
            self.assertEqual(args[-4:], ["-i", str(refs[0]), "-i", str(refs[1])])
            self.assertIn("stdin", args[-5])
            self.assertEqual(run.call_args.kwargs["input"].decode("utf-8"), "朝の場面")
            (home / "generated_images" / expected / "extra.png").write_bytes(png())
            with self.assertRaisesRegex(ValueError, "出力 PNG"):
                engines.run_codex("another panel", refs, home)

    def test_comfy_api_round_trip_and_unavailable_server(self):
        job = str(uuid4())
        history = {job: {"status": {"status_str": "success"}, "outputs": {
            "1": {"images": [{"type": "output", "subfolder": "manga", "filename": "panel.png"}]}
        }}}
        payloads = [b"{}", b'{"name":"unique.png","subfolder":""}',
                    json.dumps({"prompt_id": job}).encode(), json.dumps(history).encode(), png()]
        with patch.object(engines, "comfy_request", side_effect=payloads) as req:
            self.assertEqual(engines.run_sdxl({}, {"unique.png": png()}, {}), png())
        self.assertEqual([c.args[0] for c in req.call_args_list],
                         ["/system_stats", "/upload/image", "/prompt", f"/history/{job}",
                          "/view?filename=panel.png&subfolder=manga&type=output"])
        self.assertIn(b'filename="unique.png"', req.call_args_list[1].args[1])
        with patch.object(engines, "comfy_request", side_effect=ValueError("ComfyUI に接続できません")) as req:
            with self.assertRaisesRegex(ValueError, "接続できません"):
                engines.run_sdxl({}, {}, {})
            req.assert_called_once_with("/system_stats")
