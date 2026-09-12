"""Generate all AgentForge icons (favicon, PWA, apple-touch) from the CPU logo design.

Run: python tools/make_icons.py
Outputs into pg_ui/static/.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

STATIC = Path(__file__).resolve().parent.parent / "pg_ui" / "static"
TOP = (56, 189, 248)      # sky-400
MID = (59, 130, 246)      # blue-500
BOTTOM = (99, 102, 241)   # indigo-500
WHITE = (255, 255, 255)


def _gradient(size: int, top=TOP, bottom=BOTTOM) -> Image.Image:
    img = Image.new("RGBA", (size, size))
    px = img.load()
    for y in range(size):
        t = y / max(size - 1, 1)
        color = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(size):
            px[x, y] = (*color, 255)
    return img


def _rounded_gradient_icon(size: int, scale: float = 1.0) -> Image.Image:
    canvas = int(size * scale)
    img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    bg = _gradient(canvas)
    radius = int(canvas * 0.28)

    mask = Image.new("L", (canvas, canvas), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, canvas - 1, canvas - 1], radius=radius, fill=255)

    img.paste(bg, (0, 0), mask)

    # CPU glyph
    draw = ImageDraw.Draw(img)
    w = int(canvas * 0.078)  # stroke width
    chip = int(canvas * 0.56)
    left = (canvas - chip) // 2
    top = (canvas - chip) // 2
    # corner pins
    pin = int(canvas * 0.075)
    off = int(canvas * 0.06)
    pr = int(pin * 0.45)
    for cx, cy in [(left - off, top - off), (left + chip - pin + off, top - off),
                   (left - off, top + chip - pin + off), (left + chip - pin + off, top + chip - pin + off)]:
        draw.rounded_rectangle([cx, cy, cx + pin, cy + pin], radius=pr, fill=WHITE)
    # outer chip
    draw.rounded_rectangle([left, top, left + chip, top + chip], radius=int(chip * 0.16),
                           outline=WHITE, width=w)
    # inner core
    core = int(canvas * 0.26)
    c_left = (canvas - core) // 2
    c_top = (canvas - core) // 2
    draw.rounded_rectangle([c_left, c_top, c_left + core, c_top + core], radius=int(core * 0.22),
                           outline=WHITE, width=w)
    return img


def _make_png(size: int, maskable: bool = False) -> Image.Image:
    if maskable:
        img = _rounded_gradient_icon(size, scale=1.0)
        return img
    return _rounded_gradient_icon(size)


def main() -> None:
    STATIC.mkdir(parents=True, exist_ok=True)

    _round_icon = _rounded_gradient_icon(512)
    imagess = [_round_icon.resize((s, s), Image.LANCZOS) for s in (16, 32, 48, 64)]
    _round_icon.save(STATIC / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

    _make_png(192).save(STATIC / "icon-192.png")
    _make_png(512).save(STATIC / "icon-512.png")
    _make_png(512, maskable=True).save(STATIC / "icon-maskable-512.png")
    _make_png(180).save(STATIC / "apple-touch-icon.png")

    print(f"Icons written to {STATIC}")


if __name__ == "__main__":
    main()