"""Build today's frame for the e-paper board.

Usage: .venv/bin/python server/build_frame.py [--date YYYY-MM-DD] [--style "..."]
                                              [--calendar important|week|off] [--mode art|photo]

Writes <output_dir>/frame.bin (what the board downloads), preview.png (what
the screen will show) and art.png (today's raw artwork, reused if tomorrow's
generation fails). Serve locally with: python3 -m http.server 8000 --directory out
"""
import argparse
import datetime as dt
import random
import tomllib
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

import art
import calendar_events
import weather
from compose import Line, compose, prepare
from frame import canvas_size, encode

ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    return tomllib.loads((ROOT / "server" / "config.toml").read_text())


def pick_photo(cfg: dict, out: Path) -> Path | None:
    """A random photo from the photos folder, never the same one twice in a row."""
    folder = ROOT / cfg["dir"]
    photos = sorted(p for p in folder.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    if not photos:
        return None
    last = out / "last_photo.txt"
    previous = last.read_text().strip() if last.exists() else ""
    choices = [p for p in photos if p.name != previous] or photos
    photo = random.choice(choices)
    last.write_text(photo.name)
    return photo


def get_art(cfg: dict, day: dt.date, forecast, size, out: Path, style: str | None,
            mode: str | None) -> Image.Image:
    """Today's artwork: sometimes one of the user's photos redrawn, otherwise generated art.
    Falls back to generated art, then the last saved art, then a blank canvas."""
    a, p = cfg["art"], cfg["photos"]
    img = None
    if mode == "photo" or (mode is None and random.random() < p["chance"]):
        photo = pick_photo(p, out)
        if photo:
            print(f"Art: redrawing photo {photo.name}")
            img = art.from_photo(p, p["prompt"], photo)
    if img is None:
        style = style or art.pick_style(a, day)
        prompt = art.build_prompt(a, style, art.pick(a["scenes"], day), forecast, day)
        print(f"Art prompt: {prompt}")
        img = art.generate(a, prompt, size, seed=day.toordinal())
    if img:
        img.save(out / "art.png")
        return img
    if (out / "art.png").exists():
        print("Art: generation failed, reusing the last artwork")
        return Image.open(out / "art.png")
    print("Art: generation failed and no saved artwork, using blank")
    return Image.new("L", size, 255)


def calendar_texts(cfg: dict, day: dt.date, mode: str) -> list[str]:
    """Calendar lines for the frame, as of the board's refresh time on `day`."""
    c = cfg["calendar"]
    if mode == "off":
        return []
    tz = ZoneInfo(cfg["timezone"])
    now = dt.datetime.combine(day, dt.time.fromisoformat(c["shown_at"]), tz)
    events = calendar_events.fetch(now, c["lookahead_days"], tz)
    if not events:
        return []
    if mode == "week":
        return calendar_events.week_lines(events, now, c)
    event = calendar_events.most_important(events, now, c)
    return [calendar_events.event_line(event, now, c)] if event else []


def text_lines(cfg: dict, day: dt.date, forecast, calendar: list[str]) -> list[Line]:
    t = cfg["text"]
    lines = []
    if forecast:
        w = t["weather"]
        text = w["format"].format(**vars(forecast), description=forecast.description)
        lines.append(Line(text, w["font"], w["size"]))
    lines.append(Line(day.strftime(t["date"]["format"]), t["date"]["font"], t["date"]["size"]))
    c = t["calendar"]
    lines += [Line(text, c["font"], c["size"], c["max_rows"]) for text in calendar]
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=dt.date.fromisoformat, help="override today's date")
    parser.add_argument("--style", help="override the art style for this run")
    parser.add_argument("--mode", choices=["art", "photo"], help="force generated art or a photo")
    parser.add_argument("--calendar", choices=["important", "week", "off"],
                        help="override the calendar mode for this run")
    args = parser.parse_args()

    cfg = load_config()
    day = args.date or dt.datetime.now(ZoneInfo(cfg["timezone"])).date()
    size = canvas_size(cfg["orientation"])
    out = ROOT / cfg["output_dir"]
    out.mkdir(exist_ok=True)

    forecast = weather.fetch(cfg["weather"], day, cfg["timezone"])
    calendar = calendar_texts(cfg, day, args.calendar or cfg["calendar"]["mode"])
    gray = prepare(get_art(cfg, day, forecast, size, out, args.style, args.mode), size)
    img = compose(gray, cfg["text"], text_lines(cfg, day, forecast, calendar))

    img.save(out / "preview.png")
    data = encode(img, cfg["orientation"])
    (out / "frame.bin").write_bytes(data)
    (out / "built.txt").write_text(day.isoformat())  # lets backup scheduled runs skip
    print(f"Built frame for {day:%d/%m/%Y}: {out / 'frame.bin'} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
