"""Logo IcueLite : le symbole iCUE (hexagone, six pales, bouton marche « i ») redessiné en contour fin lumineux.

Le symbole est un PNG (assets/mark.png, généré par tools/logo/pistes.py, piste A).
Le texte utilise Michroma (« iCUE ») et Exo 2 ExtraLight (« lite », aux couleurs des pales), polices libres (OFL).
"""

import os

from PIL import Image, ImageDraw, ImageFont

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
WHITE = (240, 242, 245)
# couleurs des pales, dans l'ordre du dégradé de « lite »
RAINBOW = [(255, 0, 0), (249, 211, 0), (51, 196, 129), (85, 217, 255), (33, 96, 196), (197, 102, 232)]

_mark_cache = None


def _mark_source():
    global _mark_cache
    if _mark_cache is None:
        _mark_cache = Image.open(os.path.join(ASSETS, "mark.png")).convert("RGBA")
    return _mark_cache


def mark(size=256):
    """Le symbole seul, en RGBA carré (le halo est inclus dans le PNG)."""
    return _mark_source().resize((size, size), Image.LANCZOS)


def _font(name, size):
    try:
        return ImageFont.truetype(os.path.join(ASSETS, name), size)
    except OSError:
        return ImageFont.load_default()


def _rainbow(width, height):
    strip = Image.new("RGBA", (len(RAINBOW), 1))
    strip.putdata([c + (255,) for c in RAINBOW])
    return strip.resize((width, height), Image.BILINEAR)


def wordmark(height=40):
    """Symbole + « iCUE » (Michroma, blanc) + « lite » (Exo 2 ExtraLight, dégradé des pales)."""
    S = 4
    H = height * S
    sym = mark(H)
    bold = _font("Michroma-Regular.ttf", int(H * 0.40))
    light = _font("Exo2-ExtraLight.ttf", int(H * 0.58))
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    w1 = tmp.textlength("iCUE", font=bold)
    w2 = tmp.textlength("lite", font=light)
    gap, inner = H * 0.22, H * 0.11
    W = int(H + gap + w1 + inner + w2 + H * 0.08)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(sym, (0, 0))
    d = ImageDraw.Draw(out)
    mid = H * 0.53
    d.text((H + gap, mid), "iCUE", font=bold, fill=WHITE + (255,), anchor="lm")
    x = int(H + gap + w1 + inner)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).text((x, mid - H * 0.03), "lite", font=light, fill=255, anchor="lm")
    lite = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lite.paste(_rainbow(int(w2), H), (x, 0))
    lite.putalpha(Image.composite(lite.getchannel("A"), Image.new("L", (W, H), 0), mask))
    out.alpha_composite(lite)
    return out.resize((W // S, height), Image.LANCZOS)


def app_icon(size=256):
    """Icône d'application : symbole sur pastille sombre arrondie."""
    S = size * 4
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    d.rounded_rectangle((S * .03, S * .03, S * .97, S * .97), radius=S * .24, fill=(17, 19, 22, 255),
                        outline=(42, 46, 52, 255), width=int(S * .015))
    out.alpha_composite(mark(int(S * .84)), (int(S * .08), int(S * .08)))
    return out.resize((size, size), Image.LANCZOS)


def small_icon(size):
    """Petites tailles (barre des tâches, titre) : le symbole seul, agrandi au maximum pour rester lisible."""
    src = _mark_source()
    sym = src.crop(src.getbbox())
    S = size * 4
    sym.thumbnail((S, S), Image.LANCZOS)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.alpha_composite(sym, ((S - sym.width) // 2, (S - sym.height) // 2))
    return out.resize((size, size), Image.LANCZOS)


ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]


def save_ico(path):
    # Images au format BMP (et non PNG) : l'Explorateur et la barre des tâches les affichent partout.
    frames = [small_icon(s) if s <= 32 else app_icon(s) for s in ICO_SIZES]
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


# --- logo Corsair « lite » : seulement sur les dessins des appareils, à la place du logo d'origine ---

_sails_cache = None


def _sails():
    global _sails_cache
    if _sails_cache is None:
        import json
        with open(os.path.join(ASSETS, "sails.json"), encoding="utf-8") as f:
            _sails_cache = json.load(f)
    return _sails_cache


def _draw_sails(draw, x, y, scale, width, fill):
    """Contour fin des voiles, coin haut-gauche en (x, y), largeur totale = scale."""
    for shape in _sails()["shapes"]:
        pts = [(x + px * scale, y + py * scale) for px, py in shape]
        draw.line(pts + pts[:2], fill=fill, width=width, joint="curve")


def _halo(img, radius):
    from PIL import ImageFilter
    blur = img.filter(ImageFilter.GaussianBlur(radius))
    blur.putalpha(blur.getchannel("A").point(lambda a: min(255, int(a * 1.3))))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(blur)
    out.alpha_composite(img)
    return out


def corsair_mark(size=256, glow=True):
    """Les voiles Corsair en contour fin lumineux (comme le symbole IcueLite), dans un carré RGBA."""
    S = size * 4
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    w, h = _sails()["size"]
    span = S * 0.84
    x, y = (S - w * span) / 2, (S - h * span) / 2
    _draw_sails(ImageDraw.Draw(out), x, y, span, max(4, round(S * 0.028)), WHITE + (255,))
    if glow:
        out = _halo(out, S * 0.025)
    return out.resize((size, size), Image.LANCZOS)


def corsair_wordmark(height=40, glow=False):
    """Voiles + « CORSAIR » en capitales fines espacées : la version « lite » du logo complet."""
    S = 4
    H = height * S
    w, h = _sails()["size"]
    sail_w = H * 0.95 * w / h
    font = _font("Exo2-ExtraLight.ttf", int(H * 0.62))
    tmp = ImageDraw.Draw(Image.new("L", (1, 1)))
    spacing = H * 0.10
    letters = "CORSAIR"
    widths = [tmp.textlength(c, font=font) for c in letters]
    text_w = sum(widths) + spacing * (len(letters) - 1)
    gap = H * 0.28
    W = int(sail_w + gap + text_w + H * 0.1)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)
    _draw_sails(d, 0, H * 0.025, H * 0.95 / h, max(3, round(H * 0.045)), WHITE + (255,))
    cx = sail_w + gap
    for c, cw in zip(letters, widths):
        d.text((cx, H * 0.55), c, font=font, fill=WHITE + (255,), anchor="lm")
        cx += cw + spacing
    if glow:
        out = _halo(out, H * 0.03)
    return out.resize((W // S, height), Image.LANCZOS)
