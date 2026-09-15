# regenerates icon.ico (the app/window/tray icon)
# run manually if the icon design ever needs to change: python tools/generate_icon.py

from pathlib import Path

from PIL import Image, ImageDraw

C1 = (0x0A, 0x5C, 0xD8)  # deep blue
C2 = (0x3E, 0xB4, 0xF0)  # light cyan-blue
SIZES = [16, 24, 32, 48, 64, 128, 256]


def _lerp(a, b, t):
    return a + (b - a) * t


def _rounded_mask(size, radius):
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def make_icon(size, supersample=8):
    s = size * supersample
    bg = Image.new("RGB", (s, s))
    px = bg.load()
    for y in range(s):
        for x in range(s):
            t = (x + y) / (2 * s)
            px[x, y] = (
                int(_lerp(C1[0], C2[0], t)),
                int(_lerp(C1[1], C2[1], t)),
                int(_lerp(C1[2], C2[2], t)),
            )

    icon = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    icon.paste(bg, (0, 0), _rounded_mask(s, int(s * 0.22)))

    draw = ImageDraw.Draw(icon)
    cx, cy = s / 2, s / 2
    stroke = s * 0.075
    arrow_w = s * 0.11
    span = s * 0.24

    # two-way swap arrows, representing a remap
    y1 = cy - s * 0.10
    x_start, x_end = cx - span, cx + span
    draw.line([(x_start, y1), (x_end, y1)], fill="white", width=int(stroke))
    draw.polygon(
        [
            (x_end + arrow_w * 0.9, y1),
            (x_end - arrow_w * 0.15, y1 - arrow_w),
            (x_end - arrow_w * 0.15, y1 + arrow_w),
        ],
        fill="white",
    )

    y2 = cy + s * 0.10
    draw.line([(x_end, y2), (x_start, y2)], fill="white", width=int(stroke))
    draw.polygon(
        [
            (x_start - arrow_w * 0.9, y2),
            (x_start + arrow_w * 0.15, y2 - arrow_w),
            (x_start + arrow_w * 0.15, y2 + arrow_w),
        ],
        fill="white",
    )

    return icon.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "icon.ico"
    largest = make_icon(max(SIZES))
    largest.save(out, sizes=[(s, s) for s in SIZES])
    print(f"wrote {out}")
