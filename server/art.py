"""Daily AI artwork: Cloudflare Workers AI (Flux-schnell) first, Pollinations as a backup."""
import base64
import datetime as dt
import io
import json
import os
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

from weather import Forecast

SECRETS = Path(__file__).resolve().parent / "secrets.toml"
CLOUDFLARE_API = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
POLLINATIONS_API = "https://image.pollinations.ai/prompt/"
POLLINATIONS_RATE_LIMIT_S = 46  # free tier: 1 image every 45 s per IP


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
    parts = [f"{style}: {scene} in {season(day)}", weather_phrase(forecast), cfg["carrier"],
             cfg["requirements"]]
    return ", ".join(p for p in parts if p)


def pick(options: list[str], day: dt.date) -> str:
    """Same choice all day, a different one each day."""
    return options[day.toordinal() % len(options)]


def cloudflare_credentials() -> tuple[str, str] | None:
    """From env vars (GitHub Actions) or server/secrets.toml (local)."""
    account, token = os.environ.get("CF_ACCOUNT_ID"), os.environ.get("CF_API_TOKEN")
    if not (account and token) and SECRETS.exists():
        cf = tomllib.loads(SECRETS.read_text()).get("cloudflare", {})
        account, token = cf.get("account_id"), cf.get("api_token")
    if not account or not token or "PASTE" in account + token:
        return None
    return account, token


def from_cloudflare(cfg: dict, prompt: str) -> Image.Image | None:
    creds = cloudflare_credentials()
    if creds is None:
        print("Art: no Cloudflare credentials")
        return None
    url = CLOUDFLARE_API.format(account=creds[0], model=cfg["model"])
    body = json.dumps({"prompt": prompt, "steps": cfg["steps"]}).encode()
    headers = {"Authorization": f"Bearer {creds[1]}", "Content-Type": "application/json"}
    for attempt in range(1, cfg["retries"] + 1):
        try:
            req = urllib.request.Request(url, body, headers)
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = base64.b64decode(json.load(resp)["result"]["image"])
            return Image.open(io.BytesIO(data))
        except urllib.error.HTTPError as e:
            print(f"Art: Cloudflare attempt {attempt}: HTTP {e.code} {e.read()[:200]!r}")
        except Exception as e:
            print(f"Art: Cloudflare attempt {attempt}: {e}")
        if attempt < cfg["retries"]:
            time.sleep(5)
    return None


def from_pollinations(cfg: dict, prompt: str, size: tuple[int, int], seed: int) -> Image.Image | None:
    w, h = size
    crop = cfg["watermark_crop"]
    query = urllib.parse.urlencode({"width": w, "height": h + crop, "seed": seed, "nologo": "true"})
    url = POLLINATIONS_API + urllib.parse.quote(prompt) + "?" + query
    for attempt in range(1, cfg["retries"] + 1):
        try:
            with urllib.request.urlopen(url, timeout=180) as resp:
                if resp.headers.get_content_type().startswith("image/"):
                    img = Image.open(io.BytesIO(resp.read()))
                    img.load()
                    return img.crop((0, 0, img.width, img.height - crop))  # drop watermark strip
                print(f"Art: Pollinations attempt {attempt}: unexpected {resp.headers.get_content_type()}")
        except urllib.error.HTTPError as e:
            print(f"Art: Pollinations attempt {attempt}: HTTP {e.code}")
        except Exception as e:
            print(f"Art: Pollinations attempt {attempt}: {e}")
        if attempt < cfg["retries"]:
            time.sleep(POLLINATIONS_RATE_LIMIT_S)
    return None


def trim(img: Image.Image, fraction: float) -> Image.Image:
    """Cut `fraction` off every edge: removes the borders and signatures models like to add."""
    dx, dy = int(img.width * fraction), int(img.height * fraction)
    return img.crop((dx, dy, img.width - dx, img.height - dy))


def generate(cfg: dict, prompt: str, size: tuple[int, int], seed: int) -> Image.Image | None:
    """Try each provider in order; None if all fail."""
    for provider in cfg["providers"]:
        if provider == "cloudflare":
            img = from_cloudflare(cfg["cloudflare"], prompt)
        else:
            img = from_pollinations(cfg["pollinations"], prompt, size, seed)
        if img:
            print(f"Art: generated by {provider}")
            img.load()
            return trim(img, cfg["trim"])
    return None
