"""Render BYD-HA brand PNGs (icon + logo) with Pillow, supersampled."""
from __future__ import annotations
import os
from PIL import Image, ImageDraw, ImageFont

OUT = r"C:\code\byd-homeassistant\brand-assets\custom_integrations\byd"
os.makedirs(OUT, exist_ok=True)

FONTS = ["seguibl.ttf", "segoeuib.ttf", "arialbd.ttf", "arial.ttf"]

def font(size):
    for f in FONTS:
        p = os.path.join(r"C:\Windows\Fonts", f)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))

TOP = (0x2A, 0xA5, 0xFF)
BOT = (0x0A, 0x46, 0xC8)
GREEN = (0x39, 0xE0, 0x8A)
BLUE = (0x0A, 0x46, 0xC8)
GREY = (0x3A, 0x46, 0x57)

def draw_centered(d, cx, baseline_y, text, fnt, fill):
    l, t, r, b = d.textbbox((0, 0), text, font=fnt)
    d.text((cx - (r - l) / 2 - l, baseline_y - b), text, font=fnt, fill=fill)

def render_icon(N):
    S = N * 4  # supersample
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = Image.new("RGBA", (S, S))
    gp = grad.load()
    for y in range(S):
        c = lerp(TOP, BOT, y / (S - 1)) + (255,)
        for x in range(S):
            gp[x, y] = c
    mask = Image.new("L", (S, S), 0)
    # Full-bleed rounded square: touches all four edges so there is no
    # transparent border for the brands checker to trim.
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, S - 1, S - 1], radius=round(0.225 * S), fill=255,
    )
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    sc = S / 256.0
    draw_centered(d, 128 * sc, 132 * sc, "BYD", font(round(90 * sc)), (255, 255, 255, 255))
    bolt = [(134, 156), (112, 194), (127, 194), (121, 220), (150, 186), (134, 186), (141, 156)]
    d.polygon([(x * sc, y * sc) for x, y in bolt], fill=GREEN + (255,))
    return img.resize((N, N), Image.LANCZOS)

def render_logo_master(byd, divider, text):
    # High-res master; trimmed to content so base/@2x are exact 2x of one image.
    S = 4
    W, H = 512 * S, 160 * S
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bolt = [(52, 24), (18, 82), (42, 82), (32, 136), (82, 66), (54, 66), (68, 24)]
    d.polygon([(x * S, y * S) for x, y in bolt], fill=GREEN + (255,))
    fb = font(round(92 * S))
    d.text((104 * S, 104 * S - fb.getbbox("BYD")[3]), "BYD", font=fb, fill=byd + (255,))
    d.rounded_rectangle([322 * S, 34 * S, 326 * S, 126 * S], radius=2 * S, fill=divider + (255,))
    fh = font(round(34 * S))
    d.text((344 * S, 72 * S - fh.getbbox("Home")[3]), "Home", font=fh, fill=text + (255,))
    d.text((344 * S, 112 * S - fh.getbbox("Assistant")[3]), "Assistant", font=fh, fill=text + (255,))
    # Trim tight to content (brands requires no transparent border).
    return img.crop(img.getbbox())

def save_logo(master, base, prefix):
    bw = 512
    bh = round(master.height * bw / master.width)
    master.resize((bw, bh), Image.LANCZOS).save(os.path.join(base, f"{prefix}.png"))
    master.resize((bw * 2, bh * 2), Image.LANCZOS).save(os.path.join(base, f"{prefix}@2x.png"))

render_icon(256).save(os.path.join(OUT, "icon.png"))
render_icon(512).save(os.path.join(OUT, "icon@2x.png"))
# Light theme: brand-blue BYD, dark-grey descriptor.
save_logo(render_logo_master(BLUE, (0xB8, 0xC4, 0xD8), GREY), OUT, "logo")
# Dark theme: lighter blue + light descriptor for contrast on dark backgrounds.
save_logo(render_logo_master((0x4D, 0xA6, 0xFF), (0x55, 0x62, 0x7A), (0xE6, 0xEC, 0xF5)), OUT, "dark_logo")
for f in ("icon.png", "icon@2x.png", "logo.png", "logo@2x.png"):
    im = Image.open(os.path.join(OUT, f))
    print(f, im.size, im.mode)
