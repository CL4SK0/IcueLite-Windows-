"""Visuels des appareils : photos officielles Corsair détourées, préparées par tools/device_art/prepare.py.

Pour chaque appareil du catalogue, assets/devices/ peut contenir :
- <clé>.png : la photo détourée (RGBA), lumières éteintes et logo Corsair effacé ;
- <clé>.json : où poser le symbole ou le logo IcueLite (à la place des logos Corsair), et les zones lumineuses ;
- <clé>_<zone>.png : le masque (niveaux de gris) de chaque zone lumineuse, recoloré à l'affichage.
Une zone sans masque (null) est un logo rétroéclairé : c'est le symbole IcueLite qui prend sa couleur.
Sans photo, l'appli affiche simplement la fiche sans image.
"""

import json
import os

from PIL import Image, ImageChops, ImageFilter

from . import logo

DEVICE_ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "devices")

_photos = {}
_cache = {}


def photo(key):
    """(image RGBA, repères, {zone: masque L}) de l'appareil, ou None s'il n'a pas encore de photo."""
    if key not in _photos:
        path = os.path.join(DEVICE_ART, key + ".png")
        if not os.path.exists(path):
            _photos[key] = None
        else:
            meta = {}
            meta_path = os.path.join(DEVICE_ART, key + ".json")
            if os.path.exists(meta_path):
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
            zones = {name: Image.open(os.path.join(DEVICE_ART, file)).convert("L")
                     for name, file in meta.get("zones", {}).items() if file}
            _photos[key] = (Image.open(path).convert("RGBA"), meta, zones)
    return _photos[key]


def has_photo(key):
    return photo(key) is not None


def zones(key):
    """Noms des zones lumineuses recolorables de l'appareil."""
    p = photo(key)
    return list(p[1].get("zones", {})) if p else []


def _paint(img, color, mask):
    layer = Image.new("RGBA", img.size, tuple(color) + (255,))
    layer.putalpha(mask)
    img.alpha_composite(layer)


def _logo_image(lg, k, color):
    """Symbole (ou logo complet) IcueLite d'un emplacement, à l'échelle, tourné et teinté au besoin."""
    size = max(4, round(lg["size"] * k))
    img = logo.wordmark(size) if lg.get("kind") == "wordmark" else logo.mark(size)
    style = lg.get("style")
    if isinstance(style, list):  # gravé ou imprimé d'une seule couleur
        color = style
    if color is not None:
        flat = Image.new("RGBA", img.size, tuple(color) + (255,))
        if isinstance(style, list):
            flat.putalpha(img.getchannel("A"))
        else:  # rétroéclairage : la couleur choisie, plus claire là où le symbole est lumineux
            flat.putalpha(ImageChops.multiply(img.getchannel("A"), img.convert("L").point(lambda v: min(255, v * 2))))
        img = flat
    if lg.get("rotate"):
        img = img.rotate(lg["rotate"], resample=Image.BICUBIC, expand=True)
    return img


def compose(key, w, h, colors=None, margin=0.92):
    """L'appareil dans un cadre w × h (RGBA transparent) : ombre portée, symbole IcueLite à la place du
    logo Corsair, et chaque zone lumineuse dans sa couleur (colors : zone -> (r, g, b) ; zone absente =
    la lumière de la photo officielle, None = éteinte). Renvoie None si l'appareil n'a pas de photo."""
    p = photo(key)
    if p is None:
        return None
    colors = colors or {}
    cache_key = (key, w, h, margin, tuple(sorted((k, tuple(v) if v else None) for k, v in colors.items())))
    if cache_key in _cache:
        return _cache[cache_key]
    img, meta, masks = p
    k = min(w * margin / img.width, h * margin / img.height)
    size = (max(1, round(img.width * k)), max(1, round(img.height * k)))
    off = ((w - size[0]) // 2, (h - size[1]) // 2)

    def place(im):
        out = Image.new(im.mode, (w, h), 0)
        out.paste(im.resize(size, Image.LANCZOS), off)
        return out

    shape = place(img)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    shadow = Image.new("L", (w, h), 0)
    shadow.paste(shape.getchannel("A"), (0, max(1, round(h * 0.012))))
    _paint(out, (0, 0, 0), shadow.filter(ImageFilter.GaussianBlur(max(1, h * 0.02))).point(lambda v: v * 3 // 4))
    out.alpha_composite(shape)

    # recoloration : on garde le relief de la photo (légendes, grilles) et on remplace seulement la teinte
    gray = shape.convert("L")
    glow = max(1, min(w, h) * 0.012)
    for name, mask in masks.items():
        if name not in colors:
            continue
        m = place(mask)
        strong = m.filter(ImageFilter.MaxFilter(3)).point(lambda v: min(255, v * 3))
        color = colors[name]
        if color:
            lum = gray.point(lambda v: min(255, int(v * 1.7)))
            layer = ImageChops.multiply(Image.new("RGB", (w, h), tuple(color)), Image.merge("RGB", (lum,) * 3))
        else:  # éteinte : diffuseur gris foncé, légendes à peine visibles
            dim = gray.point(lambda v: int(v * 0.32 + 12))
            layer = Image.merge("RGB", (dim,) * 3)
        layer = layer.convert("RGBA")
        layer.putalpha(strong)
        out.alpha_composite(layer)
        if color:
            halo = ImageChops.multiply(m.filter(ImageFilter.GaussianBlur(glow)), shape.getchannel("A"))
            _paint(out, color, halo.point(lambda v: v * 2 // 5))

    for lg in meta.get("logos", []):
        zone = lg.get("zone")
        color = colors.get(zone) if zone else None
        if zone and zone in colors and colors[zone] is None:
            color = (58, 60, 64)  # rétroéclairage éteint : symbole sombre, juste en relief
        sym = _logo_image(lg, k, color)
        x = round(off[0] + lg["at"][0] * k - sym.width / 2)
        y = round(off[1] + lg["at"][1] * k - sym.height / 2)
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layer.paste(sym, (x, y))
        out.alpha_composite(layer)

    if len(_cache) > 40:
        _cache.clear()
    _cache[cache_key] = out
    return out
