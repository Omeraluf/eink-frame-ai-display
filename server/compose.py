"""Lay out the frame: art background plus a block of text lines."""
import re
from dataclasses import dataclass
from pathlib import Path

from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat

ROOT = Path(__file__).resolve().parent.parent
HEBREW = re.compile("[֐-׿]")
RLM = "‏"  # invisible right-to-left mark


@dataclass
class Line:
    text: str
    font: str  # path relative to the repo root
    size: int


def visual(text: str) -> str:
    """Pillow draws left to right; reorder right-to-left runs (with mirrored brackets).
    Lines start with a time or date and end with the title, so the line stays left to
    right while a trailing RLM keeps end punctuation like ")" or "…" with the Hebrew."""
    if not HEBREW.search(text):
        return text
    return get_display(text + RLM, base_dir="L").replace(RLM, "")


def ellipsize(text: str) -> str:
    return text + "…"


def fit(text: str, font: ImageFont.FreeTypeFont, max_width: float) -> str:
    """Shorten from the end with "…" until the line fits."""
    if font.getlength(visual(text)) <= max_width:
        return text
    while len(text) > 4:
        text = text.rstrip("…")[:-1].rstrip()
        if font.getlength(visual(ellipsize(text))) <= max_width:
            break
    return ellipsize(text)


def prepare(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Crop to `size` as grayscale with boosted contrast (still continuous tone)."""
    img = ImageOps.exif_transpose(img).convert("L")
    img = ImageOps.fit(img, size, Image.LANCZOS)
    return ImageOps.autocontrast(img, cutoff=1)


def find_blank_area(gray: Image.Image, box: tuple[int, int], cfg: dict) -> tuple[int, int] | None:
    """Where to center a `box`-sized text block: in the middle of the blank bright area
    (e.g. empty sky) inside the search band, or None if there is none."""
    bw, bh = box
    top = int(gray.height * cfg["search_top"])
    bottom = int(gray.height * cfg["search_bottom"])
    step = 8
    fits = []  # centers of every window that is bright and calm enough
    for y in range(top, max(top, bottom - bh) + 1, step):
        for x in range(0, gray.width - bw, step):
            stat = ImageStat.Stat(gray.crop((x, y, x + bw, y + bh)))
            if stat.mean[0] >= cfg["min_brightness"] and stat.stddev[0] <= cfg["max_variation"]:
                fits.append((x + bw // 2, y + bh // 2))
    if not fits:
        return None
    # The fitting window nearest the middle of the blank area
    cx = sum(x for x, _ in fits) / len(fits)
    cy = sum(y for _, y in fits) / len(fits)
    return min(fits, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)


def compose(gray: Image.Image, cfg: dict, lines: list[Line]) -> Image.Image:
    """Dither the art and write the text block: centered on a blank area if the art has
    one, otherwise right-aligned at the fallback corner with a white halo."""
    fonts = [ImageFont.truetype(str(ROOT / line.font), line.size) for line in lines]
    max_width = gray.width * cfg["max_width"] - 2 * cfg["auto"]["padding"]
    texts = [visual(fit(line.text, font, max_width)) for line, font in zip(lines, fonts)]
    boxes = [font.getbbox(text, anchor="ls") for font, text in zip(fonts, texts)]
    gap = cfg["line_gap"]
    block_w = max(b[2] - b[0] for b in boxes)
    block_h = sum(b[3] - b[1] for b in boxes) + gap * (len(lines) - 1)
    pad = cfg["auto"]["padding"]

    center = None
    if cfg["placement"] == "auto":
        center = find_blank_area(gray, (block_w + 2 * pad, block_h + 2 * pad), cfg["auto"])
        print(f"Text: blank area at {center}" if center else "Text: no blank area, using fallback")

    img = gray.convert("1")  # Floyd-Steinberg dithering
    draw = ImageDraw.Draw(img)
    if center:
        x, y, anchor, halo = center[0], center[1] - block_h / 2, "ms", {}
    else:
        fb = cfg["fallback"]
        x, y, anchor = img.width * fb["x"], img.height * fb["y"] - block_h, "rs"
        halo = {"stroke_width": cfg["halo"], "stroke_fill": 1}
    for font, text, b in zip(fonts, texts, boxes):
        y += -b[1]  # ascent above the baseline
        draw.text((x, y), text, font=font, fill=0, anchor=anchor, **halo)
        y += b[3] + gap
    return img
