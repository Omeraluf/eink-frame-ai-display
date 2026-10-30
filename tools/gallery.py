"""Render every art style from config.toml as it would appear on the frame.

Usage: .venv/bin/python tools/gallery.py [--scenes N]

Writes out/gallery/index.html (self-contained, images inlined) for comparing
styles side by side. Uses today's weather and one Cloudflare image per tile.
"""
import argparse
import base64
import datetime as dt
import html
import io
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

import art  # noqa: E402
import weather  # noqa: E402
from build_frame import load_config, text_lines  # noqa: E402
from compose import compose, prepare  # noqa: E402
from frame import canvas_size  # noqa: E402


def data_uri(img) -> str:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenes", type=int, default=2, help="scenes per style")
    args = parser.parse_args()

    cfg = load_config()
    day = dt.datetime.now(ZoneInfo(cfg["timezone"])).date()
    size = canvas_size(cfg["orientation"])
    forecast = weather.fetch(cfg["weather"], day, cfg["timezone"])
    scenes = cfg["art"]["scenes"][: args.scenes]

    rows = []
    for i, style in enumerate(cfg["art"]["styles"], 1):
        tiles = []
        for scene in scenes:
            prompt = art.build_prompt(cfg["art"], style, scene, forecast, day)
            print(f"[{i}/{len(cfg['art']['styles'])}] {style} / {scene}")
            img = art.generate(cfg["art"], prompt, size, seed=i)
            if img is None:
                tiles.append('<div class="tile missing">generation failed</div>')
                continue
            frame = compose(prepare(img, size), cfg["text"], text_lines(cfg, day, forecast, []))
            tiles.append(f'<img class="tile" src="{data_uri(frame)}" alt="{html.escape(scene)}">')
        rows.append(f'<section><h2><span>{i}</span> {html.escape(style)}</h2>'
                    f'<div class="tiles">{"".join(tiles)}</div></section>')

    out = ROOT / cfg["output_dir"] / "gallery"
    out.mkdir(parents=True, exist_ok=True)
    page = (ROOT / "tools" / "gallery_template.html").read_text()
    page = page.replace("{{DATE}}", f"{day:%d/%m/%Y}").replace("{{ROWS}}", "\n".join(rows))
    (out / "index.html").write_text(page)
    print(f"Wrote {out / 'index.html'}")


if __name__ == "__main__":
    main()
