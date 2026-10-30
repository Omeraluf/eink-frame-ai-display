"""Copy photos from images/photos (originals, gitignored) into photos/ (committed),
resized so the repo stays small. Deletes copies whose original is gone.

Usage: .venv/bin/python tools/sync_photos.py
"""
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC, DST = ROOT / "images" / "photos", ROOT / "photos"
MAX_SIZE = 1600  # the image model gets 1024 px anyway

DST.mkdir(exist_ok=True)
originals = {p.stem: p for p in SRC.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")}
for stem, src in sorted(originals.items()):
    dst = DST / f"{stem}.jpg"
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        continue
    img = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    img.thumbnail((MAX_SIZE, MAX_SIZE))
    img.save(dst, "JPEG", quality=85)
    print(f"added {dst.name} ({dst.stat().st_size // 1024} KB)")
for dst in DST.glob("*.jpg"):
    if dst.stem not in originals:
        dst.unlink()
        print(f"removed {dst.name}")
