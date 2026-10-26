"""Visuels des appareils : photos officielles Corsair détourées, préparées par tools/device_art/prepare.py.

Pour chaque appareil du catalogue, assets/devices/ peut contenir :
- <clé>.png : la photo détourée (RGBA), lumières éteintes et logo Corsair effacé ;
- <clé>.json : le centre et la taille du symbole IcueLite, et les zones lumineuses ;
- <clé>_<zone>.png : le masque (niveaux de gris) de chaque zone lumineuse, recoloré à l'affichage.
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
                     for name, file in meta.get("zones", {}).items()}
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


def compose(key, w, h, colors=None, margin=0.92):
    """L'appareil dans un cadre w × h (RGBA transparent) : ombre portée, symbole IcueLite à la place du
    logo Corsair, et chaque zone lumineuse dans sa couleur (colors : zone -> (r, g, b) ; zone absente =
    sa lumière d'origine, None = éteinte). Renvoie None si l'appareil n'a pas de photo."""
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

    glow = max(1, min(w, h) * 0.012)
    for name, mask in masks.items():
        color = colors.get(name, meta.get("colors", {}).get(name))
        if not color:
            continue
        m = place(mask)
        _paint(out, color, m)
        halo = ImageChops.multiply(m.filter(ImageFilter.GaussianBlur(glow)), shape.getchannel("A"))
        _paint(out, color, halo.point(lambda v: v * 3 // 5))

    if "logo" in meta:
        cx, cy, d = meta["logo"]
        side = max(4, round(d * k))
        sym = logo.mark(side)
        out.alpha_composite(sym, (max(0, round(off[0] + cx * k - side / 2)), max(0, round(off[1] + cy * k - side / 2))))

    if len(_cache) > 40:
        _cache.clear()
    _cache[cache_key] = out
    return out
