"""Surveillance façon iCUE : une tuile par mesure (valeur, minimum, maximum, petite courbe) et une grande
courbe pour la mesure choisie. Les valeurs viennent de Controller.history, rempli toutes les 4 secondes."""

import tkinter as tk

import customtkinter as ctk

from . import theme as t

# couleur de la courbe selon le type de mesure, comme dans iCUE (orange pour les températures…)
COLORS = {"°C": "#ff9a3c", "tr/min": "#3cb4ff", "W": "#b56cff", "V": "#b56cff", "A": "#b56cff", "%": "#4ad66d",
          "MHz": "#ffd400", "Go": "#5ad1c8", "Mo": "#5ad1c8", "Mo/s": "#ff6fa8"}


def readings(sensors):
    """Données d'un pilote ({"fans", "temps", "values"}) -> [(nom, valeur, unité)]."""
    out = [(name, rpm, "tr/min") for name, rpm in sensors.get("fans", [])]
    out += [(name, temp, "°C") for name, temp in sensors.get("temps", [])]
    out += list(sensors.get("values", []))
    return out


def fmt(value, unit):
    if unit in ("tr/min", "W", "MHz", "Mo", "%") or abs(value) >= 100:
        return f"{value:.0f}"
    return f"{value:.1f}" if unit == "°C" else f"{value:.2f}"


def draw_curve(canvas, points, w, h, color, pad=4, fill=True):
    """Courbe des points (valeurs) sur toute la largeur du canevas."""
    canvas.delete("curve")
    if len(points) < 2:
        return
    lo, hi = min(points), max(points)
    if hi - lo < 1e-6:
        lo, hi = lo - 1, hi + 1
    step = (w - 2 * pad) / (len(points) - 1)
    coords = []
    for i, v in enumerate(points):
        coords += [pad + i * step, h - pad - (v - lo) / (hi - lo) * (h - 2 * pad)]
    if fill:
        canvas.create_polygon(pad, h, *coords, w - pad, h, fill=t.CARD_HI, outline="", tags="curve")
    canvas.create_line(*coords, fill=color, width=2, smooth=True, tags="curve")


class Tile(ctk.CTkFrame):
    """Tuile d'une mesure : valeur actuelle, plus bas et plus haut depuis l'ouverture, courbe récente."""

    W, H = 210, 34

    def __init__(self, parent, name, unit, on_click):
        super().__init__(parent, fg_color=t.CARD, corner_radius=8, border_width=1, border_color=t.BORDER)
        self.unit, self.color = unit, COLORS.get(unit, t.ACCENT)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 0))
        self.value = ctk.CTkLabel(top, text="…", text_color=self.color, font=ctk.CTkFont(t.FONT, 20, "bold"))
        self.value.pack(side="left")
        ctk.CTkLabel(top, text=f" {unit}", text_color=self.color, font=ctk.CTkFont(t.FONT, 12)).pack(
            side="left", pady=(6, 0))
        ctk.CTkLabel(self, text=name, text_color=t.TEXT, font=ctk.CTkFont(t.FONT, 12), anchor="w").pack(
            fill="x", padx=12)
        self.range = ctk.CTkLabel(self, text="", text_color=t.MUTED, font=ctk.CTkFont(t.FONT, 11), anchor="w")
        self.range.pack(fill="x", padx=12)
        self.canvas = tk.Canvas(self, width=self.W, height=self.H, bg=t.CARD, highlightthickness=0)
        self.canvas.pack(padx=8, pady=(2, 8))
        for widget in (self, top, self.value, self.range, self.canvas):
            widget.bind("<Button-1>", lambda _e: on_click())

    def update_values(self, points, selected=False):
        self.configure(border_color=self.color if selected else t.BORDER)
        if not points:
            return
        self.value.configure(text=fmt(points[-1], self.unit))
        self.range.configure(text=f"min {fmt(min(points), self.unit)}   max {fmt(max(points), self.unit)}")
        draw_curve(self.canvas, points[-60:], self.W, self.H, self.color)


class Graph(ctk.CTkFrame):
    """Grande courbe de la mesure choisie, sur tout l'historique gardé (une dizaine de minutes)."""

    W, H = 640, 170

    def __init__(self, parent):
        super().__init__(parent, fg_color=t.CARD, corner_radius=10, border_width=1, border_color=t.BORDER)
        self.title = ctk.CTkLabel(self, text="", text_color=t.TEXT, font=ctk.CTkFont(t.FONT, 15, "bold"), anchor="w")
        self.title.pack(fill="x", padx=16, pady=(12, 0))
        self.legend = ctk.CTkLabel(self, text="", text_color=t.MUTED, font=ctk.CTkFont(t.FONT, 11), anchor="w")
        self.legend.pack(fill="x", padx=16)
        self.canvas = tk.Canvas(self, width=self.W, height=self.H, bg=t.CARD, highlightthickness=0)
        self.canvas.pack(padx=12, pady=(4, 12))
        for i in range(1, 4):
            y = self.H * i / 4
            self.canvas.create_line(4, y, self.W - 4, y, fill=t.BORDER, dash=(2, 4))

    def show(self, name, unit, points, seconds):
        self.title.configure(text=name)
        if points:
            span = f"{seconds // 60} min {seconds % 60:02d} s" if seconds >= 60 else f"{seconds} s"
            self.legend.configure(text=f"{fmt(points[-1], unit)} {unit} maintenant   ·   min {fmt(min(points), unit)}"
                                       f"   max {fmt(max(points), unit)}   ·   sur les {span} écoulées")
        draw_curve(self.canvas, points, self.W, self.H, COLORS.get(unit, t.ACCENT), pad=8)
