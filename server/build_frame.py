"""Build today's frame for the e-paper board.

Usage: .venv/bin/python server/build_frame.py [--date YYYY-MM-DD]

Writes <output_dir>/frame.bin (what the board downloads) and
<output_dir>/preview.png (what the screen will show).
Serve locally with: python3 -m http.server 8000 --directory out
"""
import argparse
import datetime as dt
import tomllib
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

import weather
from frame import canvas_size, dither, encode

ROOT = Path(__file__).resolve().parent.parent


def background(cfg: dict, size: tuple[int, int]) -> Image.Image:
    path = ROOT / cfg["path"]
    if not path.exists():
        print(f"Background {cfg['path']} not found, using blank")
        return Image.new("1", size, 1)
    return dither(Image.open(path), size)


def draw_text(img: Image.Image, text_cfg: dict, line: dict, text: str) -> None:
    """Black text with a white halo, placed by the line's x/y/anchor settings."""
    font = ImageFont.truetype(str(ROOT / text_cfg["font"]), line["size"])
    xy = (img.width * line["x"], img.height * line["y"])
    ImageDraw.Draw(img).text(xy, text, font=font, fill=0, anchor=line["anchor"],
                             stroke_width=text_cfg["halo"], stroke_fill=1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=dt.date.fromisoformat, help="override today's date")
    args = parser.parse_args()

    cfg = tomllib.loads((ROOT / "server" / "config.toml").read_text())
    day = args.date or dt.datetime.now(ZoneInfo(cfg["timezone"])).date()
    size = canvas_size(cfg["orientation"])

    forecast = weather.fetch(cfg["weather"], day, cfg["timezone"])

    img = background(cfg["background"], size)
    text = cfg["text"]
    draw_text(img, text, text["date"], day.strftime(text["date"]["format"]))
    if forecast:
        line = text["weather"]
        draw_text(img, text, line, line["format"].format(**vars(forecast),
                                                         description=forecast.description))

    out = ROOT / cfg["output_dir"]
    out.mkdir(exist_ok=True)
    img.save(out / "preview.png")
    data = encode(img, cfg["orientation"])
    (out / "frame.bin").write_bytes(data)
    print(f"Built frame for {day:%d/%m/%Y}: {out / 'frame.bin'} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
