# TRMNL e-ink photo frame

Minimal PlatformIO firmware that turns a **TRMNL 7.5" (OG) DIY kit** into a static photo frame: on boot it draws one dithered black-and-white photo and leaves it on screen.

## Hardware

- **MCU:** Seeed XIAO ESP32-S3 (8 MB PSRAM, 16 MB flash)
- **Display:** 7.5" monochrome e-paper, 800×480, UC8179 controller
- **Driver board:** XIAO ePaper Display Board EE04

## Project layout

| Path | Purpose |
|---|---|
| `platformio.ini` | Build config: `espressif32@6.12.0`, Arduino framework, Seeed_GFX (pinned commit), panel selected with `BOARD_SCREEN_COMBO=502` and `USE_XIAO_EPAPER_DISPLAY_BOARD_EE04` |
| `src/main.cpp` | Firmware: clears the screen, draws `photo`, refreshes the panel once. `loop()` is empty |
| `tools/convert.py` | Converts a photo into the 1-bit bitmap header |
| `include/photo.h` | Generated bitmap (800×480, 1 bit per pixel, bit set = black). Do not edit by hand |
| `images/` | Source photos and `preview.png`, which shows what the screen will display |
| `backup/` | Full 16 MB dump of the factory TRMNL firmware, plus its sha256 and the read log |

## Usage

1. **Set up Python** (once):
   ```sh
   python3 -m venv .venv
   .venv/bin/pip install pillow
   ```
2. **Convert a photo:**
   ```sh
   .venv/bin/python tools/convert.py images/my_photo.jpg            # portrait (default)
   .venv/bin/python tools/convert.py images/my_photo.jpg --landscape
   ```
   The script applies the EXIF rotation, converts to grayscale, crops to fit, auto-contrasts and dithers to 1-bit (Floyd-Steinberg). Portrait photos are cropped to 480×800 and rotated onto the landscape panel, with the top of the photo at the panel's right edge, so the frame stands upright. Check `images/preview.png` before flashing.
3. **Build and flash:**
   ```sh
   pio run -t upload
   ```
   The upload and monitor port is set to `/dev/cu.usbmodem1401` in `platformio.ini`. Change it if your board shows up on a different port.

## Restoring the factory firmware

`backup/trmnl_factory_16MB.bin` is a complete image of the flash as shipped. To restore it:

```sh
(cd backup && shasum -a 256 -c trmnl_factory_16MB.sha256)
esptool.py --chip esp32s3 --port /dev/cu.usbmodem1401 write_flash 0x0 backup/trmnl_factory_16MB.bin
```

## Limitations

- Shows one image compiled into the firmware. No WiFi, no TRMNL server and no deep sleep.
- Changing the photo means re-running `convert.py` and re-flashing.
