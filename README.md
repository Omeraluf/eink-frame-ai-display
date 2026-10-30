# TRMNL e-ink AI frame

A **TRMNL 7.5" (OG) DIY kit** turned into a daily art frame. Every morning a server on GitHub Actions builds a new 1-bit 800×480 picture and publishes it to GitHub Pages. At 10:00 Israel time the board wakes up, downloads it, shows it and goes back to deep sleep. No computer needs to be on.

## What the frame shows

- **Art:** an AI illustration (Cloudflare Workers AI, Flux-schnell) in one of 12 black-and-white styles. Pencil sketch appears every other day, and the others take turns. The prompt follows today's weather and season, so partly cloudy days get clouds and rainy days get rain.
- **Your photos** (about 1 refresh in 3, chosen at random): a random photo from `photos/`, redrawn as a pencil sketch by an image-editing model (FLUX.2 klein). The same photo never comes up twice in a row.
- **Text**, written into empty sky when the picture has some, otherwise in the bottom-right corner with a white outline:
  - Weather for Ramat Gan: high / low and conditions (Open-Meteo).
  - Date as DD.MM.
  - The most important upcoming Google Calendar event: one with `!` in its title within 7 days, otherwise the next timed event today or tomorrow. Titles longer than 30 characters are cut with "…", and long lines wrap to two rows. Hebrew titles read right to left, with Hebrew day names (היום, מחר, ראשון…).

If a source fails, the frame is still built: without weather or the event, with yesterday's artwork, or with Pollinations as a backup art source.

## Using the frame

| Button | Action |
|---|---|
| 1 or 3 | Refresh now |
| 2 | Status screen for 30 s (last update, result, next refresh, battery, WiFi signal), then back to the picture |
| Reset | Refresh, then stay awake 60 s so new firmware can be flashed |

- **If a refresh fails** (no WiFi, server down), the board redraws the last good picture, saved in flash, with a ⚠ in the top-left corner.
- **Battery:** a 🔋 icon appears below 3.5 V. One refresh a day should last on the order of a year per charge. That's an estimate: the sleep current hasn't been measured. The kit's side switch cuts battery power, and USB-C charges the battery.

## Hardware

- **MCU:** Seeed XIAO ESP32-S3 (8 MB PSRAM, 16 MB flash, 2.4 GHz WiFi only)
- **Display:** 7.5" monochrome e-paper, 800×480, UC8179 controller
- **Driver board:** XIAO ePaper Display Board EE04. Buttons on GPIO2, 3 and 5 (active-low); battery ADC on GPIO1, enabled by GPIO6.

## Project layout

| Path | Purpose |
|---|---|
| `src/main.cpp` | Firmware: WiFi → time sync → download → save to flash → display → deep sleep; warning and battery icons, status screen |
| `include/config.h` | Board settings: image URL, refresh time, timezone, button pins, battery thresholds, timeouts |
| `include/secrets.h` | WiFi name and password. **Gitignored** |
| `platformio.ini` | Build config: `espressif32@6.12.0`, Arduino, Seeed_GFX (pinned), panel `BOARD_SCREEN_COMBO=502` on the EE04 board |
| `server/build_frame.py` | Builds the frame: picks art or a photo, fetches weather and calendar, composes, writes `out/` |
| `server/config.toml` | Server settings: styles, scenes, photo chance, weather location, calendar rules, fonts and text layout |
| `server/art.py` | Prompt building and image generation: Cloudflare (Flux-schnell, FLUX.2 klein for photos), Pollinations backup |
| `server/compose.py` | Text layout: finds empty space, wraps and shortens lines, right-to-left Hebrew, dithering |
| `server/calendar_events.py` | Google Calendar (secret iCal link): picks the event to show and formats it |
| `server/weather.py` | Daily forecast from Open-Meteo (free, no key) |
| `server/frame.py` | Canvas size and encoding to the board's format |
| `server/fonts/` | Special Elite (date, weather), Amatic SC (calendar, has Hebrew), Permanent Marker (unused) |
| `server/secrets.toml` | Cloudflare and Google Calendar credentials for local runs. **Gitignored** |
| `.github/workflows/build-frame.yml` | Daily build at 05:00 UTC, deployed to GitHub Pages |
| `photos/` | Resized copies of your photos, used by photo mode |
| `tools/sync_photos.py` | Resizes originals from `images/photos/` into `photos/` |
| `tools/gallery.py` | Renders every art style as the frame would show it, into an HTML page |
| `images/`, `out/` | Original photos; generated output. Both gitignored |
| `backup/` | sha256 and log of the factory TRMNL firmware dump (the 16 MB `.bin` is local only) |

**Frame format:** raw bytes, no header: 800×480 pixels, 1 bit per pixel, MSB first, row by row, bit set = black. Exactly 48,000 bytes; the board rejects any other size. The picture is composed upright at 480×800 and rotated onto the landscape panel.

## Running on GitHub

- **Daily:** 05:00 UTC (08:00 Israel summer time, 07:00 winter). The board reads at 10:00, which leaves room for GitHub's scheduler running late.
- **Now:** Actions tab → *Build daily frame* → *Run workflow*, then press button 1. Pushing changes under `server/` or `photos/` also triggers a run.
- **Output:** `https://omeraluf.github.io/eink-frame-ai-display/` serves `frame.bin`, `preview.png`, `art.png` (reused if tomorrow's generation fails) and `last_photo.txt`.
- **Secrets** (Settings → Secrets and variables → Actions): `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `GOOGLE_ICAL_URL`.
- **Adding photos:** drop originals in `images/photos/`, run `.venv/bin/python tools/sync_photos.py`, commit `photos/`.

## Development

**Setup (once):**
```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
Create `include/secrets.h`:
```c
#pragma once
#define WIFI_SSID     "your-2.4GHz-network"
#define WIFI_PASSWORD "your-password"
```
Create `server/secrets.toml`:
```toml
[cloudflare]
account_id = "..."
api_token  = "..."   # Workers AI token

[google_calendar]
ical_url = "https://calendar.google.com/calendar/ical/.../basic.ics"  # "Secret address in iCal format"
```

**Build a frame locally** (writes `out/`; open `out/preview.png`):
```sh
.venv/bin/python server/build_frame.py
.venv/bin/python server/build_frame.py --date 2026-12-31 --mode photo --calendar week
.venv/bin/python server/build_frame.py --style "Detailed graphite pencil sketch"
```
To test on the board without GitHub, serve it (`python3 -m http.server 8000 --directory out`) and point `IMAGE_URL` in `include/config.h` at `http://<mac-ip>:8000/frame.bin`.

**Flash the firmware:** press reset (the board then stays awake 60 s), then:
```sh
pio run -t upload
pio device monitor   # logs
```
The upload port is `/dev/cu.usbmodem1401` in `platformio.ini`. Deep sleep switches off USB, which is why the reset comes first.

**Compare art styles:** `.venv/bin/python tools/gallery.py` writes `out/gallery/index.html`. It uses about 24 images of the free Cloudflare allowance (10,000 neurons a day).

## Restoring the factory firmware

`backup/trmnl_factory_16MB.bin` (local only) is a complete image of the flash as shipped:

```sh
(cd backup && shasum -a 256 -c trmnl_factory_16MB.sha256)
esptool.py --chip esp32s3 --port /dev/cu.usbmodem1401 write_flash 0x0 backup/trmnl_factory_16MB.bin
```

## Ideas not done yet

- Several refreshes a day (battery allows it; the firmware has a single `WAKE_HOUR` for now)
- Week-view calendar as an option (`mode = "week"` exists in `config.toml`)
- Tuning prompts, fonts and layout over time
