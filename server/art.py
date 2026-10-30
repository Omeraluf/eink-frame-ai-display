"""Daily AI artwork from Pollinations (free tier: 1 image every 45 s per IP)."""
import datetime as dt
import io
import time
import urllib.error
import urllib.parse
import urllib.request

from PIL import Image

from weather import Forecast

API = "https://image.pollinations.ai/prompt/"
RATE_LIMIT_S = 46


def season(day: dt.date) -> str:
    return ["winter", "spring", "summer", "autumn"][(day.month % 12) // 3]


def weather_phrase(f: Forecast | None) -> str:
    if f is None:
        return ""
    c = f.code
    if c in (0, 1):
        sky = "under a bright clear sunny sky"
    elif c == 2:
        sky = "with a few scattered clouds in the sky"
    elif c == 3:
        sky = "under a heavy overcast sky"
    elif c in (45, 48):
        sky = "in thick fog"
    elif 71 <= c <= 77 or c in (85, 86):
        sky = "in gently falling snow"
    elif c >= 95:
        sky = "during a dramatic thunderstorm with lightning"
    else:
        sky = "in the rain, with wet ground and puddles"
    if f.high >= 30:
        sky += ", on a hot day"
    elif f.high <= 12:
        sky += ", on a cold day"
    return sky


def build_prompt(cfg: dict, style: str, scene: str, forecast: Forecast | None, day: dt.date) -> str:
    parts = [style, f"{scene} in {season(day)}", weather_phrase(forecast), cfg["carrier"],
             cfg["requirements"]]
    return ". ".join(p for p in parts if p)


def pick(options: list[str], day: dt.date) -> str:
    """Same choice all day, a different one each day."""
    return options[day.toordinal() % len(options)]


def generate(cfg: dict, prompt: str, size: tuple[int, int], seed: int) -> Image.Image | None:
    """Fetch the image, retrying through the free-tier rate limit. None if it never arrives."""
    w, h = size
    crop = cfg["watermark_crop"]
    query = urllib.parse.urlencode({"width": w, "height": h + crop, "seed": seed,
                                    "model": cfg["model"], "nologo": "true"})
    url = API + urllib.parse.quote(prompt) + "?" + query
    for attempt in range(1, cfg["retries"] + 1):
        try:
            with urllib.request.urlopen(url, timeout=180) as resp:
                if resp.headers.get_content_type().startswith("image/"):
                    img = Image.open(io.BytesIO(resp.read()))
                    img.load()
                    return img.crop((0, 0, img.width, img.height - crop))  # drop watermark strip
                print(f"Art: attempt {attempt}: unexpected {resp.headers.get_content_type()}")
        except urllib.error.HTTPError as e:
            print(f"Art: attempt {attempt}: HTTP {e.code}")
        except Exception as e:
            print(f"Art: attempt {attempt}: {e}")
        if attempt < cfg["retries"]:
            time.sleep(RATE_LIMIT_S)
    return None
