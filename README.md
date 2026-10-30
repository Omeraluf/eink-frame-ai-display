# TRMNL e-ink AI frame

PlatformIO firmware for a **TRMNL 7.5" (OG) DIY kit**. On boot, the board joins WiFi, downloads a ready-made 1-bit 800×480 frame from a server and shows it. If anything fails, the screen keeps its previous picture.

The goal: a server builds a daily AI artwork with the date, weather and a calendar event drawn into the scene, and the board fetches it once a day. The server runs on GitHub Actions every morning and publishes the frame to GitHub Pages; the board downloads it at 10:00 Israel time. No computer needs to be on.

## Hardware

- **MCU:** Seeed XIAO ESP32-S3 (8 MB PSRAM, 16 MB flash, 2.4 GHz WiFi only)
- **Display:** 7.5" monochrome e-paper, 800×480, UC8179 controller
- **Driver board:** XIAO ePaper Display Board EE04

## Project layout

| Path | Purpose |
|---|---|
| `platformio.ini` | Build config: `espressif32@6.12.0`, Arduino framework, Seeed_GFX (pinned commit), panel selected with `BOARD_SCREEN_COMBO=502` and `USE_XIAO_EPAPER_DISPLAY_BOARD_EE04` |
| `src/main.cpp` | Firmware: WiFi → time sync → download frame → save to flash → display → deep sleep. On failure, redraws the saved frame with a ⚠; low battery adds a 🔋 icon; button 2 shows a status screen |
| `include/config.h` | Board settings: image URL, refresh time, timezone, button pins, battery thresholds, timeouts |
| `include/secrets.h` | WiFi name and password. **Gitignored**; create it from the template below |
| `server/build_frame.py` | Builds today's frame: background + date + weather → `out/frame.bin` (what the board downloads) and `out/preview.png` |
| `server/config.toml` | Server settings: timezone, orientation, background, weather location, text style and position |
| `server/frame.py` | Panel format helpers: fit, dither, encode |
| `server/calendar_events.py` | Upcoming events from a Google Calendar secret iCal link: the "most important" one, or the week ahead |
| `server/weather.py` | Daily forecast from Open-Meteo (free, no key). If it fails, the frame is built without weather |
| `server/fonts/` | Fonts used on the frame: Special Elite for date and weather (Apache 2.0), Amatic SC with Hebrew for the calendar (OFL), Permanent Marker (unused) |
| `server/secrets.toml` | Cloudflare and Google Calendar credentials. **Gitignored**; on GitHub Actions they come from env vars |
| `.github/workflows/build-frame.yml` | GitHub Actions: builds the frame daily at 05:00 UTC and publishes `out/` to GitHub Pages |
| `photos/` | Resized copies of your photos, used by photo mode. Made by `tools/sync_photos.py` from `images/photos/` |
| `out/` | Generated output, served to the board. Gitignored |
| `images/` | Original photos (`images/photos/`). Gitignored |
| `backup/` | sha256 and read log of the factory TRMNL firmware dump. The 16 MB `.bin` itself is gitignored |

## Frame format

Raw bytes, no header: 800×480 pixels, 1 bit per pixel, MSB first, row by row, bit set = black. Exactly 48,000 bytes. The board rejects any other size.

## Usage

1. **Set up Python** (once):
   ```sh
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
2. **WiFi credentials** (once): create `include/secrets.h`:
   ```c
   #pragma once
   #define WIFI_SSID     "your-2.4GHz-network"
   #define WIFI_PASSWORD "your-password"
   ```
3. **Server address** is `IMAGE_URL` in `include/config.h` (GitHub Pages). For local testing, point it at `http://<mac-ip>:8000/frame.bin` instead.
4. **Build and flash** (once, or after firmware changes):
   ```sh
   pio run -t upload
   ```
   The upload and monitor port is `/dev/cu.usbmodem1401` in `platformio.ini`. Change it if your board shows up on a different port.
5. **Build a frame and serve it:**
   ```sh
   .venv/bin/python server/build_frame.py                    # today's date
   .venv/bin/python server/build_frame.py --date 2026-12-31  # any date, for testing
   python3 -m http.server 8000 --directory out
   ```
   Settings are in `server/config.toml`. In portrait mode the frame is composed upright at 480×800 and rotated onto the landscape panel. Check `out/preview.png` to see what the screen will show.
6. **Press reset** (or any button) on the board. Watch the logs with `pio device monitor`.

   The board deep-sleeps between refreshes, which switches off USB. To flash new firmware, press reset first: it then stays awake for 60 s (`FLASH_WINDOW_MS`). Refresh time and timezone are in `include/config.h`.

## Running on GitHub

- **Daily:** `.github/workflows/build-frame.yml` runs at 05:00 UTC, builds the frame and deploys `out/` to `https://omeraluf.github.io/eink-frame-ai-display/`.
- **Manually:** Actions tab → *Build daily frame* → *Run workflow*. Pushing changes under `server/` or `photos/` also triggers a run.
- **Secrets** (Settings → Secrets and variables → Actions): `CF_ACCOUNT_ID`, `CF_API_TOKEN`, `GOOGLE_ICAL_URL`.
- **Adding photos:** drop originals in `images/photos/`, run `.venv/bin/python tools/sync_photos.py`, commit `photos/`.

## Restoring the factory firmware

`backup/trmnl_factory_16MB.bin` (local only) is a complete image of the flash as shipped. To restore it:

```sh
(cd backup && shasum -a 256 -c trmnl_factory_16MB.sha256)
esptool.py --chip esp32s3 --port /dev/cu.usbmodem1401 write_flash 0x0 backup/trmnl_factory_16MB.bin
```

## Status

- [x] Step 1: fetch a frame over WiFi and display it
- [x] Step 2: daily cycle (deep sleep until 10:00 Israel time, any button refreshes, 60 s flash window after reset)
- [x] Step 3: server v1 (background photo + DD/MM)
- [x] Step 4: weather (Open-Meteo, Ramat Gan)
- [x] Step 5: AI art (Cloudflare Flux-schnell, 12 styles, pencil every other day)
- [x] Step 6: calendar (most important event or week view, Hebrew supported)
- [x] Step 7: photo mode (your photos redrawn as pencil sketches, random mix)
- [x] Step 8: last frame saved to flash, ⚠ and 🔋 icons, status screen on button 2
- [x] Step 9: server on GitHub Actions + Pages (daily 05:00 UTC; secrets CF_ACCOUNT_ID, CF_API_TOKEN, GOOGLE_ICAL_URL)
