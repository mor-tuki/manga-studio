"""Transparent original-size HTML lettering, adapted from the local reference.

The ellipse/burst/thought shapes, SVG tails and vertical CSS follow
local/ref/manga_letter.py. No art URL, external font or network is used.
"""
from __future__ import annotations

import html
import io
import math
import os
import re

from PIL import Image


def burst_points(cx, cy, rx, ry, n=18):
    points = []
    for i in range(n * 2):
        angle = math.pi * i / n
        k = 1 if i % 2 == 0 else 0.8
        points.append(f"{cx + rx * k * math.cos(angle):.3f},{cy + ry * k * math.sin(angle):.3f}")
    return " ".join(points)


def color(value):
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", value):
        raise ValueError("写植色は #RGB / #RRGGBB で指定してください")
    return value


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("写植の数値が不正です")
    return value


def build_html(page, draft_size=None, review_labels=None):
    if draft_size is None:
        W, H, tw, th = page.width, page.height, page.trim_width, page.book.th
        bleed = page.book.bleed
    else:
        W, H = tw, th = draft_size
        bleed = 0
    font = page.data.get("font", "Noto Sans JP")
    if not isinstance(font, str) or not re.fullmatch(r"[\w \-]+", font):
        raise ValueError("font はフォント名だけを指定してください")
    svg, divs = [], []
    sw = max(2, tw * 0.0028)
    for index, item in enumerate(page.lines()):
        kind = item.get("type", "balloon")
        x, y = bleed + item["x"] * tw / 100, bleed + item["y"] * th / 100
        w, h = item.get("w", 10) * tw / 100, item.get("h", 10) * th / 100
        size = item.get("size", 2.4) * tw / 100
        ink = color(item.get("color", "#111"))
        fill = color(item.get("fill", "#fff"))
        weight = finite(item.get("weight", 900 if kind == "text" else 700))
        text = html.escape(item.get("text", "")).replace("\n", "<br>")
        horizontal = " h" if item.get("horizontal") else ""
        if kind == "balloon":
            cx, cy, rx, ry = x + w / 2, y + h / 2, w / 2, h / 2
            shape = item.get("shape", "ellipse")
            tail = item.get("tail")
            if tail:
                tx, ty = bleed + tail[0] * tw / 100, bleed + tail[1] * th / 100
                angle = math.atan2(ty - cy, tx - cx)
                half = finite(item.get("tail_width", 0.22))
                if half <= 0 or half > 1:
                    raise ValueError("tail_width は0より大きく1以下です")
                if shape == "thought":
                    ex, ey = cx + rx * math.cos(angle), cy + ry * math.sin(angle)
                    for k, r in ((0.45, 0.16), (0.72, 0.11), (0.95, 0.07)):
                        bx, by = ex + (tx - ex) * k, ey + (ty - ey) * k
                        svg.append(f'<circle cx="{bx}" cy="{by}" r="{min(rx, ry) * r}" '
                                   f'fill="{fill}" stroke="#111" stroke-width="{sw}"/>')
                else:
                    p1 = (cx + rx * 0.92 * math.cos(angle - half), cy + ry * 0.92 * math.sin(angle - half))
                    p2 = (cx + rx * 0.92 * math.cos(angle + half), cy + ry * 0.92 * math.sin(angle + half))
                    svg.append(f'<polygon points="{p1[0]},{p1[1]} {tx},{ty} {p2[0]},{p2[1]}" '
                               f'fill="{fill}" stroke="#111" stroke-width="{sw}" stroke-linejoin="round"/>')
            if shape == "burst":
                svg.append(f'<polygon points="{burst_points(cx, cy, rx, ry)}" fill="{fill}" '
                           f'stroke="#111" stroke-width="{sw}" stroke-linejoin="miter"/>')
            elif shape == "rect":
                svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{w * 0.12}" '
                           f'fill="{fill}" stroke="#111" stroke-width="{sw}"/>')
            else:
                svg.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" '
                           f'fill="{fill}" stroke="#111" stroke-width="{sw}"/>')
            if tail and shape == "ellipse":
                q1 = (cx + rx * 0.8 * math.cos(angle - half * 0.9), cy + ry * 0.8 * math.sin(angle - half * 0.9))
                q2 = (cx + rx * 0.8 * math.cos(angle + half * 0.9), cy + ry * 0.8 * math.sin(angle + half * 0.9))
                m = (cx + (rx + sw) * 1.02 * math.cos(angle), cy + (ry + sw) * 1.02 * math.sin(angle))
                svg.append(f'<polygon points="{q1[0]},{q1[1]} {m[0]},{m[1]} {q2[0]},{q2[1]}" fill="{fill}"/>')
        elif kind == "caption":
            svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                       f'fill="{fill}" stroke="#111" stroke-width="{sw}"/>')
        if kind == "text":
            rotate = finite(item.get("rotate", 0))
            outline = color(item.get("outline", "#fff"))
            divs.append(f'<div class="free{horizontal}" data-line="{index}" '
                        f'style="left:{x}px;top:{y}px;font-size:{size}px;color:{ink};'
                        f'font-weight:{weight};transform:rotate({rotate}deg);'
                        f'-webkit-text-stroke:{size * 0.18}px {outline};paint-order:stroke fill">'
                        f'<span>{text}</span></div>')
        else:
            divs.append(f'<div class="t{horizontal}" data-line="{index}" '
                        f'style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;'
                        f'font-size:{size}px;color:{ink};font-weight:{weight}"><span>{text}</span></div>')
    labels = ""
    if review_labels is not None:
        size = max(12, min(W, H) // 37)
        stroke = max(1, size // 10)
        parts = []
        for (left, top, right, bottom), order, source in review_labels:
            parts.append(f'<rect x="{left + 0.5}" y="{top + 0.5}" width="{right - left}" '
                         f'height="{bottom - top}" fill="none" stroke="#be2727" '
                         f'stroke-width="{stroke}" shape-rendering="crispEdges"/>')
            parts.append(f'<text x="{left + 4}" y="{top + size + 2}" font-size="{size}" '
                         f'fill="#a61717" stroke="white" stroke-width="{stroke}" '
                         f'paint-order="stroke" font-weight="700">{order} '
                         f'<tspan font-size="72%">{html.escape(source)}</tspan></text>')
        labels = (f'<div id="review-labels" hidden><svg width="{W}" height="{H}">'
                  f'{"".join(parts)}</svg></div>')
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;padding:0;background:transparent}}
#page{{position:relative;width:{W}px;height:{H}px;overflow:hidden;
font-family:'{font}','Noto Sans JP','Yu Gothic','BIZ UDGothic',sans-serif}}
svg{{position:absolute;left:0;top:0}}
.t{{position:absolute;display:flex;align-items:center;justify-content:center}}
.t span,.free span{{writing-mode:vertical-rl;text-orientation:upright;line-height:1.28;
letter-spacing:.02em;white-space:nowrap;font-feature-settings:'vert'}}
.h span{{writing-mode:horizontal-tb;text-align:center;line-height:1.35;font-feature-settings:normal}}
.free{{position:absolute;transform-origin:center}}
</style></head><body><div id="page"><svg width="{W}" height="{H}" viewBox="0 0 {W} {H}">
{''.join(svg)}</svg>{''.join(divs)}{labels}</div></body></html>'''


def render_layer(page, draft_size=None, review_labels=None):
    from playwright.sync_api import sync_playwright

    # Runtime files stay in ignored repository-local storage. Nothing is downloaded.
    runtime = page.folder / "runtime"
    runtime.mkdir(exist_ok=True)
    old_env = {key: os.environ.get(key) for key in ("TMP", "TEMP", "TMPDIR")}
    try:
        for key in old_env:
            os.environ[key] = str(runtime)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(downloads_path=str(runtime), timeout=30000)
            try:
                width, height = draft_size or (page.width, page.height)
                tab = browser.new_page(viewport={"width": width, "height": height},
                                       device_scale_factor=1, locale="ja-JP")
                tab.route("**/*", lambda route: route.abort())
                tab.set_default_timeout(30000)
                tab.set_content(build_html(page, draft_size, review_labels), wait_until="load")
                tab.evaluate("() => document.fonts.ready")
                if draft_size is not None:
                    data = tab.screenshot(type="png", omit_background=True, animations="disabled", timeout=30000)
                    layer = Image.open(io.BytesIO(data)).convert("RGBA")
                    if review_labels is None:
                        return layer, []
                    tab.locator("#review-labels").evaluate("""labels => {
                        labels.parentNode.replaceChildren(labels);
                        labels.hidden = false;
                        return document.fonts.ready;
                    }""")
                    data = tab.screenshot(type="png", omit_background=True, animations="disabled", timeout=30000)
                    return layer, Image.open(io.BytesIO(data)).convert("RGBA")
                measured = tab.evaluate('''() => [...document.querySelectorAll('[data-line]')].map(d => {
                    const s = d.firstElementChild.getBoundingClientRect(), b = d.getBoundingClientRect();
                    const stroke = parseFloat(getComputedStyle(d).webkitTextStrokeWidth) || 0;
                    return {rect:[s.left-stroke,s.top-stroke,s.right+stroke,s.bottom+stroke],
                      overflow:d.classList.contains('t') && (s.width>b.width*.80 || s.height>b.height*.86)};
                })''')
                if any(item["overflow"] for item in measured):
                    raise ValueError("文字が吹き出しからはみ出します。size または w/h を調整してください")
                try:
                    from .studio import validate_bounds
                except ImportError:
                    from studio import validate_bounds
                bounds = [item["rect"] for item in measured]
                validate_bounds(page, bounds)
                data = tab.screenshot(type="png", omit_background=True, animations="disabled", timeout=30000)
            finally:
                browser.close()
    finally:
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    layer = Image.open(io.BytesIO(data)).convert("RGBA")
    # Reject actual shapes/outlines outside safety, before writing any build output.
    from PIL import ImageChops, ImageDraw
    mask = Image.new("L", layer.size, 255)
    draw = ImageDraw.Draw(mask)
    for x1, y1, x2, y2 in page.safe_rects():
        draw.rectangle((math.ceil(x1), math.ceil(y1), math.floor(x2) - 1, math.floor(y2) - 1), fill=0)
    if ImageChops.multiply(mask, layer.getchannel("A")).getbbox() is not None:
        raise ValueError("文字・吹き出し・しっぽが安全域の外です")
    return layer, bounds
