"""Generates simple gradient poster images for the seed events (so the demo needs no internet)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PALETTES = {
    "Concert": ((124, 58, 237), (236, 72, 153)),
    "Conference": ((30, 64, 175), (14, 165, 233)),
    "Comedy": ((234, 88, 12), (250, 204, 21)),
    "Sports": ((5, 150, 105), (132, 204, 22)),
    "Theatre": ((127, 29, 29), (190, 24, 93)),
    "Festival": ((147, 51, 234), (249, 115, 22)),
    "Workshop": ((15, 118, 110), (56, 189, 248)),
}


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def make_poster(path: Path, title: str, category: str, w: int = 960, h: int = 540) -> None:
    c1, c2 = PALETTES.get(category, PALETTES["Concert"])
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = (x / w * 0.6 + y / h * 0.4)
            px[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
    d = ImageDraw.Draw(img, "RGBA")
    # soft translucent circles for depth
    d.ellipse([w - 420, -160, w + 120, 380], fill=(255, 255, 255, 28))
    d.ellipse([-140, h - 260, 340, h + 160], fill=(0, 0, 0, 45))
    d.ellipse([w - 300, h - 220, w - 40, h + 40], fill=(255, 255, 255, 22))
    d.rectangle([0, h - 8, w, h], fill=(255, 255, 255, 90))
    d.rounded_rectangle([48, 48, 48 + 18 * len(category) + 40, 96], radius=24, fill=(0, 0, 0, 90))
    d.text((68, 58), category, fill="white", font=_font(26))
    # wrap title into up to 3 lines
    words, lines, line = title.split(), [], ""
    for word in words:
        trial = (line + " " + word).strip()
        if d.textlength(trial, font=_font(64)) > w - 120 and line:
            lines.append(line)
            line = word
        else:
            line = trial
    lines.append(line)
    y = h - 90 - 76 * min(len(lines), 3)
    for ln in lines[:3]:
        d.text((52, y), ln, fill="white", font=_font(64))
        y += 76
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="JPEG", quality=88)
