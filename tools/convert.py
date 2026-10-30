"""Convert a photo into a raw 1-bit 800x480 frame for the e-paper display.

Usage: .venv/bin/python tools/convert.py <photo> [--landscape]

Portrait photos (default) are cropped to 480x800 and rotated onto the
landscape panel, so the frame is stood upright. Writes out/frame.bin
(what the board downloads) and out/preview.png (what the screen will show).
Serve it with: python3 -m http.server 8000 --directory out
"""
import sys
from pathlib import Path

from PIL import Image, ImageOps

W, H = 800, 480  # native panel size
OUT = Path(__file__).resolve().parent.parent / "out"

src = Path(sys.argv[1])
landscape = "--landscape" in sys.argv

img = ImageOps.exif_transpose(Image.open(src)).convert("L")
img = ImageOps.fit(img, (W, H) if landscape else (H, W), Image.LANCZOS)
img = ImageOps.autocontrast(img, cutoff=1)
bw = img.convert("1")  # Floyd-Steinberg dithering
OUT.mkdir(exist_ok=True)
bw.save(OUT / "preview.png")
if not landscape:
    bw = bw.rotate(-90, expand=True)  # photo top -> right edge of panel

# 1 bit per pixel, MSB first, rows padded to bytes; bit set = black pixel
data = bytes(b ^ 0xFF for b in bw.tobytes())
(OUT / "frame.bin").write_bytes(data)
print(f"Wrote out/frame.bin ({len(data)} bytes) and out/preview.png")
