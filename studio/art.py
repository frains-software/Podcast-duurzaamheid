"""Beeldmerk, podcastcover (3000×3000, eis van Spotify en Apple) en app-icoon (1024×1024)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import config

FONTS = config.ASSETS / "fonts"

# Palet: paars en oranje, gedeeld met de app en de website.
NIGHT = (20, 7, 34)
AUBERGINE = (46, 12, 74)
VIOLET = (109, 40, 217)
ORCHID = (168, 85, 247)
EMBER = (255, 106, 26)
AMBER = (255, 181, 71)
CREAM = (255, 244, 230)


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def aurora(size: int, seed: int = 9) -> Image.Image:
    """Zachte 'mesh'-achtergrond: gloeiende vlekken paars en oranje op diep aubergine."""
    small = 256
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:small, 0:small] / small
    img = np.zeros((small, small, 3)) + np.array(NIGHT, float)
    blobs = [
        (0.18, 0.12, 0.55, VIOLET, 0.95),
        (0.85, 0.18, 0.40, ORCHID, 0.55),
        (0.95, 0.92, 0.60, EMBER, 1.0),
        (0.62, 0.70, 0.30, AMBER, 0.55),
        (0.05, 0.95, 0.45, AUBERGINE, 0.9),
        (0.45, 0.40, 0.35, (90, 24, 154), 0.6),
    ]
    for cx, cy, r, color, strength in blobs:
        d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        w = np.exp(-(d / r) ** 2 * 2.2) * strength
        img = img * (1 - w[..., None]) + np.array(color, float) * w[..., None]
    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))
    big = base.resize((size, size), Image.Resampling.BICUBIC)
    # Filmkorrel tegen banding en voor een tastbare, gedrukte look.
    grain = rng.normal(0, 7, (size, size, 1))
    arr = np.clip(np.asarray(big, float) + grain, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def kringloop(size: int, color=CREAM, accent=AMBER, bars: bool = True, stroke: float = 0.055) -> Image.Image:
    """Het beeldmerk: drie pijlen die een cirkel vormen (de kringloop), met binnenin een golfvorm."""
    scale = 4  # supersampling voor strakke randen
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = s / 2
    r = s * 0.40
    w = s * stroke
    for k in range(3):
        start = -90 + k * 120 + 9
        end = start + 120 - 26
        # PIL tekent de lijndikte binnen de box; verschuif zodat de lijn op straal r ligt.
        box = (c - r - w / 2, c - r - w / 2, c + r + w / 2, c + r + w / 2)
        d.arc(box, start, end, fill=color, width=int(w))
        # Ronde kapjes aan het begin.
        a0 = math.radians(start)
        d.ellipse(_dot(c + r * math.cos(a0), c + r * math.sin(a0), w / 2), fill=color)
        # Pijlpunt aan het eind, in de draairichting.
        a1 = math.radians(end)
        tip = math.radians(end + 9)
        px, py = c + r * math.cos(a1), c + r * math.sin(a1)
        tx, ty = c + r * math.cos(tip), c + r * math.sin(tip)
        nx, ny = math.cos(a1), math.sin(a1)
        head = w * 1.25
        d.polygon(
            [(px + nx * head, py + ny * head), (tx, ty), (px - nx * head, py - ny * head)],
            fill=accent if k == 0 else color,
        )
    if bars:
        n = 13
        heights = [0.22, 0.38, 0.30, 0.55, 0.72, 0.48, 0.92, 0.48, 0.72, 0.55, 0.30, 0.38, 0.22]
        span = r * 1.05
        bw = span / n * 0.52
        for i, h in enumerate(heights):
            x0 = c - span / 2 + (i + 0.5) * span / n
            hh = r * 0.62 * h
            fill = accent if i == n // 2 else color
            d.rounded_rectangle((x0 - bw / 2, c - hh, x0 + bw / 2, c + hh), radius=bw / 2, fill=fill)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def _dot(x: float, y: float, r: float) -> tuple[float, float, float, float]:
    return (x - r, y - r, x + r, y + r)


def _glow(layer: Image.Image, radius: int, opacity: float) -> Image.Image:
    alpha = layer.split()[-1].filter(ImageFilter.GaussianBlur(radius))
    glow = Image.new("RGBA", layer.size, AMBER + (0,))
    glow.putalpha(alpha.point(lambda v: int(v * opacity)))
    return glow


def _tracked(draw: ImageDraw.ImageDraw, xy, text: str, font, fill, tracking: float) -> None:
    """Tekst met extra letterspatiëring, horizontaal gecentreerd rond xy[0]."""
    widths = [font.getlength(ch) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = xy[0] - total / 2
    for ch, w in zip(text, widths):
        draw.text((x, xy[1]), ch, font=font, fill=fill)
        x += w + tracking


def cover(size: int = 3000) -> Image.Image:
    show = config.show()
    img = aurora(size).convert("RGBA")
    mark = kringloop(int(size * 0.46))
    pos = ((size - mark.width) // 2, int(size * 0.13))
    img.alpha_composite(_glow(mark, int(size * 0.03), 0.55), pos)
    img.alpha_composite(mark, pos)

    d = ImageDraw.Draw(img)
    title = _font("fraunces-latin-600-normal.woff2", int(size * 0.165))
    tw = d.textlength(show["title"], font=title)
    d.text(((size - tw) / 2, size * 0.60), show["title"], font=title, fill=CREAM)

    sub = _font("Inter-SemiBold.otf", int(size * 0.030))
    _tracked(d, (size / 2, size * 0.815), "CIRCULAIR NIEUWS  ·  ELKE OCHTEND 09:00", sub, AMBER, size * 0.006)
    by = _font("fraunces-latin-600-italic.woff2", int(size * 0.038))
    line = f"met {show['host']}  —  {show['organisation']}"
    bw = d.textlength(line, font=by)
    d.text(((size - bw) / 2, size * 0.875), line, font=by, fill=CREAM + (220,))
    return img.convert("RGB")


def app_icon(size: int = 1024) -> Image.Image:
    img = aurora(size, seed=3).convert("RGBA")
    mark = kringloop(int(size * 0.74))
    pos = ((size - mark.width) // 2, (size - mark.height) // 2)
    img.alpha_composite(_glow(mark, int(size * 0.035), 0.6), pos)
    img.alpha_composite(mark, pos)
    return img.convert("RGB")


def render_all() -> list[Path]:
    out = config.ASSETS / "art"
    out.mkdir(parents=True, exist_ok=True)
    written = []
    big = cover(3000)
    for name, px in (("cover-3000.jpg", 3000), ("cover-1400.jpg", 1400), ("cover-600.jpg", 600)):
        path = out / name
        (big if px == 3000 else big.resize((px, px), Image.Resampling.LANCZOS)).save(path, quality=90, optimize=True)
        written.append(path)
    icon = app_icon(1024)
    for path in (out / "app-icon-1024.png", config.ROOT / "ios/Grondstof/Assets.xcassets/AppIcon.appiconset/AppIcon.png"):
        path.parent.mkdir(parents=True, exist_ok=True)
        icon.save(path)
        written.append(path)
    mark = kringloop(512, bars=True)
    for path in (out / "kringloop.png", config.ROOT / "ios/Grondstof/Assets.xcassets/Kringloop.imageset/Kringloop.png"):
        path.parent.mkdir(parents=True, exist_ok=True)
        mark.save(path)
        written.append(path)
    favicon = kringloop(180, bars=False)
    favicon.save(out / "favicon.png")
    written.append(out / "favicon.png")
    return written
