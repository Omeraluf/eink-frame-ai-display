"""Panel format helpers: canvas size and encoding for the board."""
from PIL import Image

PANEL_W, PANEL_H = 800, 480  # native panel size, landscape


def canvas_size(orientation: str) -> tuple[int, int]:
    return (PANEL_H, PANEL_W) if orientation == "portrait" else (PANEL_W, PANEL_H)


def encode(bw: Image.Image, orientation: str) -> bytes:
    """1 bit per pixel, MSB first, rows padded to bytes; bit set = black pixel."""
    if orientation == "portrait":
        bw = bw.rotate(-90, expand=True)  # canvas top -> right edge of panel
    assert bw.size == (PANEL_W, PANEL_H), bw.size
    return bytes(b ^ 0xFF for b in bw.tobytes())
