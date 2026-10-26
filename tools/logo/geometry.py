"""Géométrie du symbole iCUE (hexagone, six pales, « i » dans un bouton marche), relevée sur le logo officiel.

Tout est exprimé dans un carré de 1200 × 1200 centré sur (600, 600) ; les pistes de logo IcueLite
réutilisent ces formes en les allégeant (traits fins, pales affinées, halo).
"""

import math

C = 600
COLORS = {  # sens horaire depuis le haut, comme sur le logo
    "jaune": (249, 211, 0),
    "vert": (51, 196, 129),
    "cyan": (85, 217, 255),
    "bleu": (33, 96, 196),
    "violet": (197, 102, 232),
    "rouge": (255, 0, 0),
}
ORDER = list(COLORS)


def rotate(points, degrees, cx=C, cy=C):
    a = math.radians(degrees)
    ca, sa = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca) for x, y in points]


def bezier(p0, p1, p2, steps=60):
    out = []
    for i in range(steps + 1):
        t = i / steps
        a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t ** 2
        out.append((a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1]))
    return out


def hexagon(radius, cx=C, cy=C):
    """Hexagone pointe en haut."""
    return [(cx + radius * math.cos(math.radians(60 * i - 90)), cy + radius * math.sin(math.radians(60 * i - 90)))
            for i in range(6)]


def rounded_polygon(points, r, steps=10):
    """Polygone aux coins arrondis (rayon r)."""
    out = []
    n = len(points)
    for i in range(n):
        p0, p1, p2 = points[i - 1], points[i], points[(i + 1) % n]
        v1 = (p0[0] - p1[0], p0[1] - p1[1])
        v2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1, l2 = math.hypot(*v1), math.hypot(*v2)
        a = (p1[0] + v1[0] / l1 * r, p1[1] + v1[1] / l1 * r)
        b = (p1[0] + v2[0] / l2 * r, p1[1] + v2[1] / l2 * r)
        out += bezier(a, p1, b, steps)
    return out


def blade(index, thinness=0.0, steps=60):
    """Pale n° index (0 = jaune en haut, puis sens horaire). thinness 0 = pale d'origine, 1 = filament."""
    tip_a, tip_b = (400, 300), (785, 385)
    outer_ctrl = (610, 150)  # sert seulement à affiner
    inner_ctrl = (620, 300)
    # affiner : le bord intérieur se rapproche du bord extérieur
    inner_ctrl = (inner_ctrl[0] + (outer_ctrl[0] - inner_ctrl[0]) * thinness * 0.8,
                  inner_ctrl[1] + (outer_ctrl[1] - inner_ctrl[1]) * thinness * 0.8)
    # bord extérieur : un segment parallèle au bord de l'hexagone, puis une courbe jusqu'à la pointe
    corner = (560, 208)
    outer = [tip_a] + bezier(corner, (705, 255), tip_b, steps)
    inner = bezier(tip_b, inner_ctrl, tip_a, steps)
    return rotate(outer + inner, 60 * index)


def blade_curve(index, steps=80):
    """Ligne médiane d'une pale (pour la version filaire)."""
    return rotate(bezier((400, 300), (612, 170), (785, 385), steps), 60 * index)


def power_ring(r_out=185, r_in=115, gap=90, cy=605, steps=120):
    """Anneau du bouton marche, ouvert en haut (gap en degrés)."""
    start = -90 + gap / 2
    end = 270 - gap / 2
    pts = []
    for i in range(steps + 1):
        a = math.radians(start + (end - start) * i / steps)
        pts.append((C + r_out * math.cos(a), cy + r_out * math.sin(a)))
    for i in range(steps + 1):
        a = math.radians(end - (end - start) * i / steps)
        pts.append((C + r_in * math.cos(a), cy + r_in * math.sin(a)))
    return pts


def power_arc(radius=150, gap=90, cy=605, steps=120):
    start = -90 + gap / 2
    end = 270 - gap / 2
    return [(C + radius * math.cos(math.radians(start + (end - start) * i / steps)),
             cy + radius * math.sin(math.radians(start + (end - start) * i / steps))) for i in range(steps + 1)]


I_DOT = (565, 420, 636, 492)
I_STEM = (565, 537, 636, 658)
