"""Logo IcueLite : un hexagone « i » maison (aucun élément du logo Corsair), dessiné avec Pillow.

Le texte utilise Michroma (« ICUE ») et Exo 2 ExtraLight (« lite »), polices libres (OFL).
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
YELLOW = (255, 212, 0)
WHITE = (236, 238, 241)


def _font(name, size):
    try:
        return ImageFont.truetype(os.path.join(ASSETS, name), size)
    except OSError:
        return ImageFont.load_default()


def _hexagon(cx, cy, r):
    return [(cx + r * math.cos(math.radians(60 * i - 90)), cy + r * math.sin(math.radians(60 * i - 90)))
            for i in range(6)]


def mark(size=256):
    """Le symbole seul, RGBA carré : hexagone jaune évidé avec un « i » au centre."""
    S = size * 4
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    c = S / 2
    d.polygon(_hexagon(c, c, S * 0.48), fill=YELLOW + (255,))
    d.polygon(_hexagon(c, c, S * 0.36), fill=(0, 0, 0, 0))
    w = S * 0.085
    d.rounded_rectangle((c - w, S * 0.47, c + w, S * 0.74), radius=w * 0.4, fill=YELLOW + (255,))
    d.ellipse((c - w * 1.05, S * 0.245, c + w * 1.05, S * 0.245 + w * 2.1), fill=YELLOW + (255,))
    return out.resize((size, size), Image.LANCZOS)


def wordmark(height=40):
    """Symbole + « ICUE » (Michroma, blanc) + « lite » (Exo 2 ExtraLight, jaune)."""
    S = 4
    H = height * S
    sym = mark(H)
    bold = _font("Michroma-Regular.ttf", int(H * 0.40))
    light = _font("Exo2-ExtraLight.ttf", int(H * 0.56))
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    w1 = tmp.textlength("ICUE", font=bold)
    w2 = tmp.textlength("lite", font=light)
    gap, inner = H * 0.22, H * 0.10
    W = int(H + gap + w1 + inner + w2 + H * 0.08)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(sym, (0, 0))
    d = ImageDraw.Draw(out)
    mid = H * 0.53
    d.text((H + gap, mid), "ICUE", font=bold, fill=WHITE + (255,), anchor="lm")
    d.text((H + gap + w1 + inner, mid - H * 0.03), "lite", font=light, fill=YELLOW + (255,), anchor="lm")
    return out.resize((W // S, height), Image.LANCZOS)


def app_icon(size=256):
    """Icône d'application : symbole sur pastille sombre arrondie."""
    S = size * 4
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle((S * .03, S * .03, S * .97, S * .97), radius=S * .24, fill=(17, 19, 22, 255),
                        outline=(42, 46, 52, 255), width=int(S * .015))
    out.alpha_composite(mark(int(S * .76)), (int(S * .12), int(S * .12)))
    return out.resize((size, size), Image.LANCZOS)


ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]


def save_ico(path):
    # Images au format BMP (et non PNG) : l'Explorateur et la barre des tâches les affichent partout.
    frames = [mark(s) if s <= 32 else app_icon(s) for s in ICO_SIZES]
    frames[-1].save(path, sizes=[(s, s) for s in ICO_SIZES], append_images=frames[:-1], bitmap_format="bmp")


def ico_path():
    """Icône .ico livrée avec le programme (créée à la volée si elle manque)."""
    path = os.path.join(ASSETS, "IcueLite.ico")
    if not os.path.exists(path):
        try:
            save_ico(path)
        except OSError:
            return None
    return path
