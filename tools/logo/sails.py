"""Relève les voiles du logo Corsair sur la photo officielle de l'Ironclaw (logo rétroéclairé, bien net)
et les enregistre en contours normalisés dans icuelite/assets/sails.json.

Usage : python tools/logo/sails.py <dossier des photos officielles>
"""

import json
import os
import sys

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOX = (494, 810, 670, 968)  # x0, y0, x1, y1 du logo sur ironclaw.png (1100 × 1100)


def smooth(points, rounds=2):
    """Lissage de Chaikin : arrondit les marches de pixels sans déplacer les formes."""
    pts = np.asarray(points, float)
    for _ in range(rounds):
        nxt = np.roll(pts, -1, axis=0)
        pts = np.stack([0.75 * pts + 0.25 * nxt, 0.25 * pts + 0.75 * nxt], axis=1).reshape(-1, 2)
    return pts


def main(photos):
    im = cv2.imread(os.path.join(photos, "ironclaw.png"), cv2.IMREAD_COLOR)
    x0, y0, x1, y1 = BOX
    gray = cv2.cvtColor(im[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(cv2.resize(gray, None, fx=8, fy=8, interpolation=cv2.INTER_CUBIC), (0, 0), 3)
    _, mask = cv2.threshold(gray, 110, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    contours = [c for c in contours if cv2.contourArea(c) > 2000]
    allpts = np.concatenate(contours).reshape(-1, 2).astype(float)
    lo, hi = allpts.min(0), allpts.max(0)
    span = (hi - lo).max()
    shapes = []
    for c in sorted(contours, key=lambda c: -cv2.contourArea(c)):
        simple = cv2.approxPolyDP(c, 1.5, True).reshape(-1, 2)
        pts = (smooth(simple) - lo) / span
        shapes.append([[round(x, 4), round(y, 4)] for x, y in pts])
    aspect = (hi - lo) / span
    out = os.path.join(ROOT, "icuelite", "assets", "sails.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"_source": "logo Corsair relevé sur la photo officielle de l'Ironclaw RGB",
                   "size": [round(aspect[0], 4), round(aspect[1], 4)], "shapes": shapes}, f)
    print(out, len(shapes), "formes", [len(s) for s in shapes])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/mnt/project-files/corsairlite/photos-officielles")
