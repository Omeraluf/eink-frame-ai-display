"""Lay out the frame: art background plus date and weather text."""
import datetime as dt
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat

from weather import Forecast

ROOT = Path(__file__).resolve().parent.parent


def prepare(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Crop to `size` as grayscale with boosted contrast (still continuous tone)."""
    img = ImageOps.exif_transpose(img).convert("L")
    img = ImageOps.fit(img, size, Image.LANCZOS)
    return ImageOps.autocontrast(img, cutoff=1)


def text_lines(cfg: dict, day: dt.date, forecast: Forecast | None) -> list[tuple[dict, str]]:
    lines = [(cfg["date"], day.strftime(cfg["date"]["format"]))]
    if forecast:
        w = cfg["weather"]
        lines.insert(0, (w, w["format"].format(**vars(forecast), description=forecast.description)))
    return lines


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


def compose(gray: Image.Image, cfg: dict, day: dt.date, forecast: Forecast | None) -> Image.Image:
    """Dither the art and write the text, on a blank area if the art has one."""
    lines = text_lines(cfg, day, forecast)
    fonts = [ImageFont.truetype(str(ROOT / cfg["font"]), line["size"]) for line, _ in lines]
    sizes = [font.getbbox(text, anchor="ls") for font, (_, text) in zip(fonts, lines)]
    gap = cfg["line_gap"]
    block_w = max(b[2] - b[0] for b in sizes)
    block_h = sum(b[3] - b[1] for b in sizes) + gap * (len(lines) - 1)
    pad = cfg["auto"]["padding"]

    center = None
    if cfg["placement"] == "auto":
        center = find_blank_area(gray, (block_w + 2 * pad, block_h + 2 * pad), cfg["auto"])
        print(f"Text: blank area at {center}" if center else "Text: no blank area, using fallback")

    img = gray.convert("1")  # Floyd-Steinberg dithering
    draw = ImageDraw.Draw(img)
    if center:
        # Text block centered on the blank area, lines centered on each other
        y = center[1] - block_h / 2
        for font, (line, text), b in zip(fonts, lines, sizes):
            y += -b[1]  # ascent above the baseline
            draw.text((center[0], y), text, font=font, fill=0, anchor="ms")
            y += b[3] + gap
    else:
        for font, (line, text) in zip(fonts, lines):
            xy = (img.width * line["x"], img.height * line["y"])
            draw.text(xy, text, font=font, fill=0, anchor=line["anchor"],
                      stroke_width=cfg["halo"], stroke_fill=1)
    return img
