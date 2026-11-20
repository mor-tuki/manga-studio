"""ComfyUI SDXL I2I and Codex image_gen adapters."""
from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener
from uuid import UUID, uuid4

from PIL import Image, ImageDraw

COMFY_URL = "http://127.0.0.1:8188"
COMFY_TIMEOUT = 1200  # Local I2I example: up to 20 minutes per job.
CODEX_TIMEOUT = 900  # Per-panel upper bound, to release the generation lock on failure.
SDXL_PIXELS = 1024 * 1024  # SDXL generation budget, separate from print resolution.
SDXL_GRID = 8  # VAE spatial compression.
SDXL_MAX_AXIS = 16384  # ComfyUI ImageScale MAX_RESOLUTION.
DENOISE = 0.55  # local-image-gen §5.7, measured duo I2I setting.


def sdxl_size(width, height):
    factor = min(math.sqrt(SDXL_PIXELS / (width * height)), SDXL_MAX_AXIS / max(width, height))
    return tuple(max(SDXL_GRID, round(axis * factor / SDXL_GRID) * SDXL_GRID)
                 for axis in (width, height))


def sdxl_workflow(config, characters, draft, size, seed, prompt, negative, prefix):
    """Return the API graph and named PNG assets for the same I2I workflow."""
    if len(characters) > 2:
        raise ValueError("SDXL の左右 Hook は2人までです。3人以上は codex を指定してください")
    models = config["loras"]
    missing = [char for char in characters if char not in models]
    if missing:
        raise ValueError("SDXL の LoRA 設定がありません: " + ", ".join(missing))

    graph = {}

    def node(kind, **inputs):
        key = str(len(graph) + 1)
        graph[key] = {"class_type": kind, "inputs": inputs}
        return [key, 0]

    def png(image):
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    token = uuid4().hex
    draft_name = f"manga_{token}_draft.png"
    assets = {draft_name: draft.read_bytes()}
    model = node("CheckpointLoaderSimple", ckpt_name=config["checkpoint"])
    clip, vae = [model[0], 1], [model[0], 2]
    bad = node("CLIPTextEncode", clip=clip, text=negative)
    if len(characters) == 1:
        lora = models[characters[0]]
        model = node("LoraLoaderModelOnly", model=model, lora_name=lora["file"],
                     strength_model=1.0)
        prompt = lora["trigger"] + ", " + prompt
    good = node("CLIPTextEncode", clip=clip, text=prompt)

    if len(characters) == 2:
        width, height = size
        # Leave a 4% full-width gap for the unhooked conditioning at the seam.
        left_end, right_start = math.floor(width * 0.48), math.ceil(width * 0.52)
        regions = (("left", 0, left_end), ("right", right_start, width))
        pairs = []
        for char, (side, start, end) in zip(characters, regions):
            lora = models[char]
            mask_name = f"manga_{token}_{side}.png"
            mask = Image.new("L", size, 0)
            ImageDraw.Draw(mask).rectangle((start, 0, end - 1, height - 1), fill=255)
            assets[mask_name] = png(mask)
            mask_node = node("LoadImageMask", image=mask_name, channel="red")
            hooks = node("CreateHookLoraModelOnly", lora_name=lora["file"], strength_model=1.0)
            region = node("CLIPTextEncode", clip=clip,
                          text=f"one character on the {side}, {lora['trigger']}, {prompt}")
            pairs.append(node("PairConditioningSetProperties", positive_NEW=region, negative_NEW=bad,
                              strength=1.0, set_cond_area="default", mask=mask_node, hooks=hooks))
        left, right = pairs
        combined = node("PairConditioningCombine", positive_A=left, negative_A=[left[0], 1],
                        positive_B=right, negative_B=[right[0], 1])
        good = node("PairConditioningSetDefaultCombine", positive=combined, negative=[combined[0], 1],
                    positive_DEFAULT=good, negative_DEFAULT=bad)
        bad = [good[0], 1]

    image = node("LoadImage", image=draft_name)
    scaled = node("ImageScale", image=image, upscale_method="lanczos",
                  width=size[0], height=size[1], crop="center")
    latent = node("VAEEncode", pixels=scaled, vae=vae)
    sampled = node("KSampler", model=model, seed=seed, steps=28, cfg=5.0,
                   sampler_name="euler_ancestral", scheduler="normal", positive=good,
                   negative=bad, latent_image=latent, denoise=DENOISE)
    decoded = node("VAEDecode", samples=sampled, vae=vae)
    node("SaveImage", images=decoded, filename_prefix=prefix)
    return graph, assets


# Core ComfyUI slots, in the UI node's order. API links are [node id, output index].
COMFY_OUTPUTS = {
    "CheckpointLoaderSimple": ("MODEL", "CLIP", "VAE"),
    "LoraLoaderModelOnly": ("MODEL",),
    "CLIPTextEncode": ("CONDITIONING",),
    "LoadImageMask": ("MASK",),
    "CreateHookLoraModelOnly": ("HOOKS",),
    "PairConditioningSetProperties": ("CONDITIONING", "CONDITIONING"),
    "PairConditioningCombine": ("CONDITIONING", "CONDITIONING"),
    "PairConditioningSetDefaultCombine": ("CONDITIONING", "CONDITIONING"),
    "LoadImage": ("IMAGE", "MASK"),
    "ImageScale": ("IMAGE",),
    "VAEEncode": ("LATENT",),
    "KSampler": ("LATENT",),
    "VAEDecode": ("IMAGE",),
    "SaveImage": (),
}
COMFY_OPTIONAL_INPUTS = {
    "CreateHookLoraModelOnly": {"prev_hooks": "HOOKS"},
    "PairConditioningSetProperties": {"timesteps": "TIMESTEPS_RANGE"},
    "PairConditioningSetDefaultCombine": {"hooks": "HOOKS"},
}


def browser_workflow(graph, provenance):
    """Serialize the core-node API graph in the format the ComfyUI editor opens."""
    nodes, links = [], []
    for key, spec in graph.items():
        kind = spec["class_type"]
        outputs = COMFY_OUTPUTS[kind]
        names = ("positive", "negative") if len(outputs) == 2 and kind.startswith("Pair") else outputs
        index = int(key) - 1
        current = {"id": int(key), "type": kind, "pos": [60 + index % 5 * 365, 60 + index // 5 * 340],
                   "size": [325, 175 if kind != "KSampler" else 270], "flags": {},
                   "order": index, "mode": 0, "properties": {"Node name for S&R": kind},
                   "inputs": [], "outputs": [{"name": n, "type": t, "links": []}
                                             for n, t in zip(names, outputs)], "widgets_values": []}
        for name, value in spec["inputs"].items():
            if isinstance(value, list):
                upstream, slot = value
                port = nodes[int(upstream) - 1]["outputs"][slot]
                link = len(links) + 1
                port["links"].append(link)
                links.append([link, int(upstream), slot, int(key), len(current["inputs"]), port["type"]])
                current["inputs"].append({"name": name, "type": port["type"], "link": link})
            else:
                current["widgets_values"].append(value)
                if kind == "KSampler" and name == "seed":
                    current["widgets_values"].append("fixed")
        for name, port_type in COMFY_OPTIONAL_INPUTS.get(kind, {}).items():
            current["inputs"].append({"name": name, "type": port_type, "link": None})
        nodes.append(current)
    return {"last_node_id": len(nodes), "last_link_id": len(links), "nodes": nodes,
            "links": links, "groups": [], "config": {}, "extra": {"manga_studio": provenance},
            "version": 0.4}


def comfy_request(path, body=None, content_type="application/json", timeout=10):
    request = Request(COMFY_URL + path, data=body, headers={"Content-Type": content_type})
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
            return response.read()
    except HTTPError as exc:
        detail = exc.read(700).decode("utf-8", errors="replace")
        raise ValueError(f"ComfyUI {path} が HTTP {exc.code} を返しました: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise ValueError(f"ComfyUI に接続できません。{COMFY_URL} で起動状態を確認してください") from exc


def run_sdxl(graph, assets, provenance):
    comfy_request("/system_stats")
    for name, data in assets.items():
        boundary = uuid4().hex
        parts = (f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
                 'Content-Type: image/png\r\n\r\n').encode("ascii")
        parts += data + f"\r\n--{boundary}--\r\n".encode("ascii")
        uploaded = json.loads(comfy_request("/upload/image", parts,
                                           f"multipart/form-data; boundary={boundary}"))
        if uploaded.get("name") != name or uploaded.get("subfolder"):
            raise ValueError("ComfyUI が入力画像を指定名で保存できませんでした")

    workflow = browser_workflow(graph, provenance)
    payload = {"prompt": graph, "extra_data": {"extra_pnginfo": {"workflow": workflow}}}
    prompt_id = json.loads(comfy_request("/prompt", json.dumps(payload).encode("utf-8")))["prompt_id"]
    prompt_id = str(UUID(prompt_id))
    deadline = time.monotonic() + COMFY_TIMEOUT
    while time.monotonic() < deadline:
        history = json.loads(comfy_request(f"/history/{prompt_id}")).get(prompt_id)
        if history:
            status = history["status"]
            if status.get("status_str") != "success":
                detail = json.dumps(status, ensure_ascii=False)[:700]
                raise ValueError(f"ComfyUI の描画に失敗しました: {detail}")
            images = [image for entry in history["outputs"].values() for image in entry.get("images", [])]
            if len(images) != 1 or images[0].get("type") != "output":
                raise ValueError("ComfyUI が保存したコマ画像を1枚特定できません")
            image = {key: images[0][key] for key in ("filename", "subfolder", "type")}
            return comfy_request("/view?" + urlencode(image), timeout=30)
        time.sleep(2)
    raise ValueError(f"ComfyUI の描画がタイムアウトしました（{COMFY_TIMEOUT}秒、ジョブ {prompt_id}）")


@contextmanager
def exclusive_edit(path, busy_message):
    """Advisory lock released by the OS even if the process is interrupted."""
    with path.open("a+b") as stream:
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError(busy_message) from exc
        yield


def codex_binary():
    configured = os.environ.get("MANGA_STUDIO_CODEX")
    if os.name != "nt":
        return configured or "codex"
    if configured:
        if Path(configured).suffix.lower() != ".exe":
            raise ValueError("MANGA_STUDIO_CODEX には codex.exe を設定してください")
        return configured
    native = shutil.which("codex.exe")
    if native:
        return native
    shim = shutil.which("codex.cmd")
    if shim:
        npm = Path(shim).parent / "node_modules" / "@openai"
        roots = (npm / "codex" / "node_modules" / "@openai", npm, npm / "codex")
        for root in roots:
            binaries = sorted(root.glob("codex-win32-*/vendor/*/bin/codex.exe"))
            binaries += sorted(root.glob("vendor/*-pc-windows-msvc/bin/codex.exe"))
            if binaries:
                return str(binaries[0])
    raise ValueError("codex.exe が見つかりません。PATH または MANGA_STUDIO_CODEX を設定してください")


def codex_prompt(scene, size, seed, has_refs, negative):
    roles = ("Use the attached character sheets for identity. " if has_refs else "")
    roles += ("Use the final attached image as the rough panel layout and camera reference. "
              "Apply the scene revision where it calls for changes to the layout. "
              "Use black ink and grayscale screentones, with no dialogue or lettering.")
    return (f"{roles}\nTarget canvas ratio (width:height): {size[0]}:{size[1]}. "
            f"Reproducibility hint: {seed}.\nAvoid: {negative}.\nScene: {scene}")


def run_codex(prompt, refs, work):
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    binary = codex_binary()
    instructions = ("Use the built-in image_gen tool exactly once to draw one manga panel from stdin. "
                    "Use the attached images in the specified order. Write no project files and run no "
                    "shell commands. Leave the generated PNG in this session's generated_images directory.")
    args = [binary, "exec", "--json", "--color", "never", "--skip-git-repo-check",
            "--sandbox", "read-only", instructions]
    for path in refs:
        args.extend(("-i", str(path)))
    with exclusive_edit(home / "manga-studio-image-gen.lock", "別の studio の Codex 描画が実行中です"):
        try:
            result = subprocess.run(args, cwd=work, input=prompt.encode("utf-8"), capture_output=True,
                                    timeout=CODEX_TIMEOUT)
        except FileNotFoundError as exc:
            raise ValueError("Codex CLI が見つかりません。PATH を確認してください") from exc
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f"Codex の描画がタイムアウトしました（{CODEX_TIMEOUT}秒）") from exc
        session = None
        errors = []
        for line in result.stdout.decode("utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "thread.started" and session is None:
                session = str(UUID(event["thread_id"]))
            if event.get("type") in ("error", "turn.failed"):
                errors.append(str(event.get("message") or event.get("error")))
        if result.returncode or not session:
            detail = " ".join(errors) or result.stderr.decode("utf-8", errors="replace").strip()
            raise ValueError(f"Codex の描画に失敗しました（exit {result.returncode}）: {detail[-500:]}")
        folder = home / "generated_images" / session
        files = [path for path in folder.glob("*.png") if path.is_file() and not path.is_symlink()]
        if len(files) != 1:
            detail = " ".join(errors)
            raise ValueError(f"Codex のセッション {session} に出力 PNG が1枚ありません"
                             + (f": {detail[-500:]}" if detail else ""))
        return files[0].read_bytes()
