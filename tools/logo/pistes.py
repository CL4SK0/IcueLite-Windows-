"""Planche des pistes de logo IcueLite : le symbole iCUE redessiné en version « lite ».

Usage : python tools/logo/pistes.py sortie.png   (planche des trois pistes)
        python tools/logo/pistes.py mark         (symbole retenu, piste A, vers icuelite/assets/mark.png)
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geometry import (COLORS, I_DOT, I_STEM, ORDER, blade, hexagon,  # noqa: E402
                      power_arc, power_ring, rounded_polygon)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(ROOT, "icuelite", "assets")
WHITE = (240, 242, 245)
PLATE = (58, 60, 64)
BG = (12, 13, 16)
CARD = (20, 22, 26)
BORDER = (40, 44, 50)
MUTED = (139, 146, 155)


def font(name, size):
    return ImageFont.truetype(os.path.join(ASSETS, name), size)


def ui_font(size):
    for path in ("C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/opentype/inter/Inter-Regular.otf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def glow(layer, radius=18, strength=1.6):
    """Halo néon : la forme floutée, renforcée, sous la forme nette."""
    blur = layer.filter(ImageFilter.GaussianBlur(radius))
    alpha = blur.getchannel("A").point(lambda a: min(255, int(a * strength)))
    blur.putalpha(alpha)
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.alpha_composite(blur)
    out.alpha_composite(layer)
    return out


def line(draw, pts, fill, width):
    draw.line(pts, fill=fill, width=width, joint="curve")
    r = width / 2
    for x, y in (pts[0], pts[-1]):
        draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)


# --- les trois pistes, dessinées dans un carré de 1200 px ---

def mark_a():
    """Piste A, « Filaire » : les pales en contour fin lumineux, comme RazerLite."""
    img = Image.new("RGBA", (1200, 1200), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    hexa = rounded_polygon(hexagon(470), 70)
    d.line(hexa + hexa[:2], fill=(92, 96, 104, 255), width=14, joint="curve")
    for i, name in enumerate(ORDER):
        pts = blade(i, thinness=0.25)
        d.line(pts + pts[:2], fill=COLORS[name] + (255,), width=16, joint="curve")
    line(d, power_arc(150), WHITE + (255,), 36)
    line(d, [(600, 440), (600, 458)], WHITE + (255,), 36)
    line(d, [(600, 540), (600, 640)], WHITE + (255,), 36)
    return glow(img)


def mark_b():
    """Piste B, « Allégé » : le logo d'origine, pales affinées, anneau et « i » plus fins."""
    img = Image.new("RGBA", (1200, 1200), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    hexa = rounded_polygon(hexagon(490), 80)
    d.polygon(hexa, fill=(30, 32, 36, 255))
    d.line(hexa + hexa[:2], fill=(84, 88, 96, 255), width=10, joint="curve")
    colored = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dc = ImageDraw.Draw(colored)
    for i, name in enumerate(ORDER):
        dc.polygon(blade(i, thinness=0.62), fill=COLORS[name] + (255,))
    img.alpha_composite(glow(colored, 14, 1.2))
    d = ImageDraw.Draw(img)
    d.polygon(power_ring(178, 138), fill=WHITE + (255,))
    w = 20
    d.rectangle((600 - w, 438, 600 + w, 478), fill=WHITE + (255,))
    d.rectangle((600 - w, 528, 600 + w, 650), fill=WHITE + (255,))
    return img


def mark_c():
    """Piste C, « Contour » : l'hexagone en six couleurs, le bouton marche « i » au centre."""
    img = Image.new("RGBA", (1200, 1200), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pts = hexagon(470)
    # côté k entre les sommets k et k+1 : couleur de la pale qui le longe (le jaune en haut à droite)
    for k in range(6):
        a, b = pts[k], pts[(k + 1) % 6]
        gap = 0.13
        a2 = (a[0] + (b[0] - a[0]) * gap, a[1] + (b[1] - a[1]) * gap)
        b2 = (b[0] + (a[0] - b[0]) * gap, b[1] + (a[1] - b[1]) * gap)
        line(d, [a2, b2], COLORS[ORDER[k]] + (255,), 34)
    line(d, power_arc(160), WHITE + (255,), 44)
    line(d, [(600, 432), (600, 452)], WHITE + (255,), 44)
    line(d, [(600, 540), (600, 650)], WHITE + (255,), 44)
    return glow(img, 16, 1.4)


def original():
    img = Image.new("RGBA", (1200, 1200), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon(rounded_polygon(hexagon(490), 80), fill=PLATE + (255,))
    for i, name in enumerate(ORDER):
        d.polygon(blade(i), fill=COLORS[name] + (255,))
    d.polygon(power_ring(), fill=WHITE + (255,))
    d.rectangle(I_DOT, fill=WHITE + (255,))
    d.rectangle(I_STEM, fill=WHITE + (255,))
    return img


# --- logotype ---

def rainbow(width, height):
    """Dégradé horizontal reprenant les six couleurs des pales."""
    grad = Image.new("RGBA", (width, height))
    cols = [COLORS[n] for n in ("rouge", "jaune", "vert", "cyan", "bleu", "violet")]
    px = grad.load()
    for x in range(width):
        t = x / max(1, width - 1) * (len(cols) - 1)
        i = min(int(t), len(cols) - 2)
        f = t - i
        c = tuple(int(cols[i][k] + (cols[i + 1][k] - cols[i][k]) * f) for k in range(3))
        for y in range(height):
            px[x, y] = c + (255,)
    return grad


def wordmark(mark, height):
    S = 3
    H = height * S
    bold = font("Michroma-Regular.ttf", int(H * 0.42))
    light = font("Exo2-ExtraLight.ttf", int(H * 0.60))
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    w1 = tmp.textlength("iCUE", font=bold)
    w2 = tmp.textlength("lite", font=light)
    gap, inner = H * 0.25, H * 0.12
    W = int(H + gap + w1 + inner + w2 + H * 0.1)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(mark.resize((H, H), Image.LANCZOS))
    d = ImageDraw.Draw(out)
    mid = H * 0.53
    d.text((H + gap, mid), "iCUE", font=bold, fill=WHITE + (255,), anchor="lm")
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).text((H + gap + w1 + inner, mid - H * 0.03), "lite", font=light, fill=255, anchor="lm")
    colored = rainbow(W, H)
    colored.putalpha(mask)
    out.alpha_composite(colored)
    return out.resize((W // S, height), Image.LANCZOS)


def tile(mark, size):
    S = size * 4
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle((0, 0, S - 1, S - 1), radius=S * .22, fill=(17, 19, 22, 255), outline=BORDER + (255,),
                        width=max(4, S // 90))
    m = mark.resize((int(S * .84), int(S * .84)), Image.LANCZOS)
    out.alpha_composite(m, (int(S * .08), int(S * .08)))
    return out.resize((size, size), Image.LANCZOS)


def card(board, x, y, w, h, tag, title, mark, caption):
    d = ImageDraw.Draw(board)
    d.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=CARD + (255,), outline=BORDER + (255,), width=2)
    d.text((x + w / 2, y + 36), tag, font=ui_font(14), fill=MUTED + (255,), anchor="mm")
    d.text((x + w / 2, y + 68), title, font=font("Exo2-ExtraLight.ttf", 30), fill=WHITE + (255,), anchor="mm")
    big = mark.resize((250, 250), Image.LANCZOS)
    board.alpha_composite(big, (int(x + (w - 250) / 2), y + 100))
    wm = wordmark(mark, 46)
    board.alpha_composite(wm, (int(x + (w - wm.width) / 2), y + 375))
    tiles = [tile(mark, 96), tile(mark, 44), tile(mark, 24)]
    total = sum(t.width for t in tiles) + 2 * 18
    tx = int(x + (w - total) / 2)
    for t in tiles:
        board.alpha_composite(t, (tx, y + 450 + (96 - t.height) // 2))
        tx += t.width + 18
    yy = y + 572
    for ln in caption:
        d.text((x + 28, yy), ln, font=ui_font(15), fill=MUTED + (255,))
        yy += 22


def board(path):
    W, H = 1500, 690
    out = Image.new("RGBA", (W, H), BG + (255,))
    cw = 460
    pistes = [
        ("PISTE A", "Le filaire", mark_a(),
         ["Les six pales du logo iCUE gardent leur forme,", "mais en contour fin lumineux, comme RazerLite."]),
        ("PISTE B", "L'allégé", mark_b(),
         ["Le logo d'origine, mais avec des pales affinées,", "un anneau et un « i » plus fins."]),
        ("PISTE C", "Le contour", mark_c(),
         ["Les six couleurs passent sur les bords de", "l'hexagone ; il reste le bouton marche « i »."]),
    ]
    for k, (tag, title, mark, caption) in enumerate(pistes):
        card(out, 28 + k * (cw + 28), 28, cw, H - 56, tag, title, mark, caption)
    out.convert("RGB").save(path)


def export_mark(path=os.path.join(ASSETS, "mark.png"), size=512):
    """Exporte le symbole retenu (piste A) pour l'appli : icuelite/assets/mark.png."""
    mark = mark_a()
    crop = mark.crop(mark.getbbox())
    side = max(crop.size)  # l'hexagone est plus haut que large : on centre dans un carré sans le déformer
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.alpha_composite(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
    square.resize((size, size), Image.LANCZOS).save(path)


if __name__ == "__main__":
    if sys.argv[1:2] == ["mark"]:
        export_mark()
    else:
        board(sys.argv[1] if len(sys.argv) > 1 else "logo-pistes.png")
