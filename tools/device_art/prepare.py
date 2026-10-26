"""Prépare les visuels des appareils à partir des photos officielles Corsair.

    python tools/device_art/prepare.py [--config réglages.json] <dossier des photos> [clé…]

Les réglages de chaque appareil sont dans devices.json (à côté de ce script) : nom du fichier source,
recadrage, logo Corsair à effacer, zones lumineuses. Pour chaque appareil, le script :
1. détoure la photo (transparence d'origine, ou fond uni repéré sur les bords puis affiné par GrabCut) ;
2. efface les logos Corsair (le symbole ou le logo IcueLite est posé à leur place par l'appli) ;
3. repère les zones lumineuses (pixels saturés et clairs), que l'appli peut éteindre ou recolorer ;
4. écrit icuelite/assets/devices/<clé>.png, <clé>.json, <clé>_<zone>.png, et un aperçu dans
   <dossier des photos>/apercu/.

Outil de développement seulement : il demande opencv-python-headless et numpy, pas l'appli.
"""

import json
import os
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "icuelite", "assets", "devices")


def load(path):
    """Image BGRA (alpha à 255 si la photo n'en a pas)."""
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"Image illisible : {path}")
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    if img.dtype != np.uint8:
        img = (img / 257).astype(np.uint8)
    return img


def keep_big(mask, min_part=0.02):
    """Garde les morceaux qui pèsent au moins min_part de la surface du plus gros (barrettes, câbles…)."""
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask)
    if n <= 1:
        return mask
    areas = st[1:, cv2.CC_STAT_AREA]
    keep = [1 + i for i, a in enumerate(areas) if a >= areas.max() * min_part]
    return np.where(np.isin(lab, keep), 255, 0).astype(np.uint8)


def cut_out(img, tol=14):
    """Masque de l'appareil (0..255)."""
    alpha = img[..., 3]
    if (alpha < 250).mean() > 0.05:  # vraie transparence : la photo est déjà détourée
        return alpha.copy()
    bgr = img[..., :3]
    h, w = alpha.shape
    border = np.concatenate([bgr[0], bgr[-1], bgr[:, 0], bgr[:, -1]]).astype(np.int16)
    bg = np.median(border, axis=0)
    # fond : pixels proches de la couleur du fond et reliés aux bords
    near = (np.abs(bgr.astype(np.int16) - bg).max(axis=2) <= tol).astype(np.uint8)
    n, lab = cv2.connectedComponents(near)
    edge_labels = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    background = np.isin(lab, list(edge_labels)) & (near > 0)
    rough = np.where(background, 0, 255).astype(np.uint8)
    rough = cv2.morphologyEx(rough, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    rough = keep_big(rough)
    # affinage GrabCut sur une bande autour du contour (ombres douces, reflets clairs sur fond blanc)
    band = max(3, round(min(h, w) * 0.006))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * band + 1, 2 * band + 1))
    gc = np.full((h, w), cv2.GC_BGD, np.uint8)
    gc[cv2.dilate(rough, k) > 0] = cv2.GC_PR_BGD
    gc[rough > 0] = cv2.GC_PR_FGD
    gc[cv2.erode(rough, k) > 0] = cv2.GC_FGD
    try:
        cv2.grabCut(bgr, gc, None, np.zeros((1, 65)), np.zeros((1, 65)), 4, cv2.GC_INIT_WITH_MASK)
        mask = np.where((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    except cv2.error:
        mask = rough
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    mask = keep_big(mask)
    return cv2.GaussianBlur(mask, (3, 3), 0)


def poly_mask(shape, polys):
    m = np.zeros(shape, np.uint8)
    for p in polys:
        cv2.fillPoly(m, [np.array(p, np.int32)], 255)
    return m


def light_of(bgr, area, min_sat=90, min_val=70):
    """Intensité (0..255) de la lumière RGB dans area : couleurs vives et claires."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    s, v = hsv[..., 1], hsv[..., 2]
    strength = np.clip((s - min_sat) / max(1, 255 - min_sat) * 2.2, 0, 1) * np.clip((v - min_val) / 120, 0, 1)
    strength = (strength * 255).astype(np.uint8)
    return cv2.bitwise_and(strength, area)


def prepare(key, cfg, src_dir):
    img = load(os.path.join(src_dir, cfg["source"]))
    if cfg.get("rotate"):
        h, w = img.shape[:2]
        rot = cv2.getRotationMatrix2D((w / 2, h / 2), cfg["rotate"], 1)
        img = cv2.warpAffine(img, rot, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    if cfg.get("crop"):
        x0, y0, x1, y1 = cfg["crop"]
        img = img[y0:y1, x0:x1]
    mask = cut_out(img, cfg.get("tolerance", 14))
    ys, xs = np.nonzero(mask > 8)
    pad = 6
    y0, y1 = max(0, ys.min() - pad), min(img.shape[0], ys.max() + pad + 1)
    x0, x1 = max(0, xs.min() - pad), min(img.shape[1], xs.max() + pad + 1)
    img, mask = img[y0:y1, x0:x1], mask[y0:y1, x0:x1]

    def shift(points):  # repères de devices.json : coordonnées de l'image recadrée par "crop"
        return [[x - x0, y - y0] for x, y in points]

    bgr = img[..., :3].copy()
    meta = {"zones": {}}

    # logos Corsair : effacés, l'appli pose le symbole ou le logo IcueLite au même endroit
    meta["logos"] = []
    for lg in cfg.get("logos", []):
        bx0, by0, bx1, by1 = lg["box"]
        (bx0, by0), (bx1, by1) = shift([[bx0, by0], [bx1, by1]])
        hole = np.zeros(mask.shape, np.uint8)
        cv2.rectangle(hole, (bx0, by0), (bx1, by1), 255, -1)
        if lg.get("fill"):  # fond uni (écran, plaque) : on repeint plutôt que de reconstruire
            bgr[hole > 0] = lg["fill"][::-1]
        else:
            bgr = cv2.inpaint(bgr, hole, lg.get("inpaint", 7), cv2.INPAINT_TELEA)
        if lg.get("kind") == "none":
            continue
        meta["logos"].append({"at": [(bx0 + bx1) / 2, (by0 + by1) / 2],
                              "size": lg.get("size", max(bx1 - bx0, by1 - by0)),
                              **{k: lg[k] for k in ("kind", "rotate", "style", "zone") if k in lg}})

    # zones lumineuses : la photo garde sa lumière d'origine, l'appli assombrit puis recolore chaque zone
    zone_masks = {}
    for name, z in cfg.get("zones", {}).items():
        if z.get("logo_only"):  # zone réduite au logo (souris, casque) : pas de masque, le symbole est teinté
            meta["zones"][name] = None
            continue
        if z.get("polys") or z.get("circles"):
            area = poly_mask(mask.shape, [shift(p) for p in z.get("polys", [])])
            for cx, cy, ro, ri in z.get("circles", []):
                (cx, cy), = shift([[cx, cy]])
                cv2.circle(area, (cx, cy), ro, 255, -1)
                cv2.circle(area, (cx, cy), ri, 0, -1)
        else:
            area = mask.copy()
        if z.get("exclude"):
            area[poly_mask(mask.shape, [shift(p) for p in z["exclude"]]) > 0] = 0
        area = cv2.bitwise_and(area, (mask > 128).astype(np.uint8) * 255)
        if z.get("mode") in ("bright", "both"):  # lumière blanche au cœur des ventilateurs : la clarté compte, pas la couleur
            v = cv2.cvtColor(img[..., :3], cv2.COLOR_BGR2HSV)[..., 2].astype(np.float32)
            lo = z.get("min_val", 110)
            light = cv2.bitwise_and((np.clip((v - lo) / max(1, 235 - lo), 0, 1) * 255).astype(np.uint8), area)
            if z["mode"] == "both":  # plus les bords colorés, moins clairs
                light = cv2.max(light, light_of(img[..., :3], area, z.get("min_sat", 90), 40))
        else:
            light = light_of(img[..., :3], area, z.get("min_sat", 90), z.get("min_val", 70))
        if z.get("fill"):  # zone dessinée à la main (bande, anneau) : toute la surface s'allume
            light = cv2.max(light, cv2.GaussianBlur(area, (0, 0), 1.5))
        zone_masks[name] = light
    # mise à l'échelle finale
    k = min(1.0, cfg.get("width", 1100) / img.shape[1], cfg.get("height", 700) / img.shape[0])
    size = (round(img.shape[1] * k), round(img.shape[0] * k))

    def rs(a):
        return cv2.resize(a, size, interpolation=cv2.INTER_AREA)

    os.makedirs(OUT, exist_ok=True)
    rgba = cv2.merge([*cv2.split(rs(bgr)), rs(mask)])
    cv2.imwrite(os.path.join(OUT, f"{key}.png"), rgba, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    for name, light in zone_masks.items():
        file = f"{key}_{slug(name)}.png"
        cv2.imwrite(os.path.join(OUT, file), rs(light), [cv2.IMWRITE_PNG_COMPRESSION, 9])
        meta["zones"][name] = file
    for lg in meta["logos"]:
        lg["at"] = [round(v * k, 1) for v in lg["at"]]
        lg["size"] = round(lg["size"] * k, 1)
    meta["size"] = list(size)
    with open(os.path.join(OUT, f"{key}.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return size


def slug(name):
    table = str.maketrans("àâäéèêëîïôöùûüç ", "aaaeeeeiioouuuc_")
    return "".join(c for c in name.lower().translate(table) if c.isalnum() or c == "_")


def preview(keys, src_dir):
    """Planche de contrôle : chaque appareil d'origine, puis recoloré, sur fond iCUE."""
    sys.path.insert(0, os.path.join(HERE, "..", ".."))
    from PIL import Image
    from icuelite import render
    W, H = 520, 300
    sheet = Image.new("RGBA", (W * 3, H * len(keys)), (12, 13, 15, 255))
    for row, key in enumerate(keys):
        names = render.zones(key)
        for col, colors in enumerate([{}, {n: (255, 0, 64) for n in names}, {n: None for n in names}]):
            tile = render.compose(key, W, H, colors)
            if tile:
                sheet.alpha_composite(tile, (col * W, row * H))
    folder = os.path.join(src_dir, "apercu")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "apercu.png")
    sheet.convert("RGB").save(path)
    return path


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    config_path = os.path.join(HERE, "devices.json")
    if argv[0] == "--config":
        config_path, argv = argv[1], argv[2:]
    src_dir, wanted = argv[0], argv[1:]
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)
    done = []
    for key, cfg in config.items():
        if key.startswith("_") or (wanted and key not in wanted):
            continue
        if not os.path.exists(os.path.join(src_dir, cfg["source"])):
            print(f"{key} : {cfg['source']} absent, ignoré")
            continue
        print(f"{key} : {prepare(key, cfg, src_dir)}")
        done.append(key)
    if done:
        print("Aperçu :", preview(done, src_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
