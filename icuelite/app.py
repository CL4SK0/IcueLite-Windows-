"""Interface graphique d'IcueLite : appareils dans la colonne de gauche, détail à droite, comme iCUE."""

import queue
import sys
import threading
from pathlib import Path

import customtkinter as ctk
from PIL import ImageTk

from . import __version__, config, diag, instance, logo, memory, render, updater
from . import theme as t
from .control import Controller
from .devices import CATALOG, MOTHERBOARD, NOTHING, detect
from .drivers import DRIVERS

KIND_LABELS = {"keyboard": "Clavier", "mouse": "Souris", "headset": "Casque", "case": "Boîtier",
               "psu": "Alimentation", "cooler": "Watercooling", "memory": "Mémoire"}


def button(parent, text, command, primary=False, **kw):
    kw.setdefault("height", 34)
    return ctk.CTkButton(parent, text=text, command=command, corner_radius=6,
                         font=ctk.CTkFont(t.FONT, 13, "bold" if primary else "normal"),
                         fg_color=t.ACCENT if primary else t.CARD_HI,
                         hover_color=t.ACCENT_HOVER if primary else t.BORDER,
                         text_color=t.ACCENT_TEXT if primary else t.TEXT, **kw)


def label(parent, text, size=13, color=t.TEXT, bold=False, **kw):
    return ctk.CTkLabel(parent, text=text, text_color=color,
                        font=ctk.CTkFont(t.FONT, size, "bold" if bold else "normal"), **kw)


# Aperçu de l'éclairage sur la photo : quelques couleurs à essayer, zone par zone
SWATCHES = [("D'origine", "origin"), ("Jaune", (255, 212, 0)), ("Rouge", (255, 30, 40)), ("Vert", (40, 230, 90)),
            ("Bleu", (40, 120, 255)), ("Violet", (190, 80, 255)), ("Blanc", (255, 255, 255)), ("Éteint", None)]


def device_image(key, w, h, colors=None):
    """CTkImage de l'appareil (dessinée en double pour les écrans haute densité), ou None sans photo."""
    img = render.compose(key, w * 2, h * 2, colors)
    if img is None:
        return None
    return ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))


def status_of(spec, found):
    """(texte, couleur) de l'état d'un appareil."""
    if spec.support == MOTHERBOARD:
        return "Via la carte mère", t.WARNING
    if spec.support == NOTHING:
        return "Rien à piloter", t.FAINT
    if spec.key in found:
        return "Branché", t.OK
    return "Non détecté", t.FAINT


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.cfg = config.load()
        self.update_info = None
        self.found, self.unknown = {}, []
        self.current = None
        self._from_threads = queue.Queue()
        self.ctrl = Controller(self.cfg, notify=lambda key, text, error=False:
                               self.from_thread(self.on_driver_message, key, text, error))
        self.sensor_labels = None
        self.icue_warning = False   # iCUE lancé à l'ouverture d'IcueLite
        self.memory_modules = None  # barrettes lues par Windows, en arrière-plan (une seconde environ)

        self.title("IcueLite")
        self.geometry(self.cfg.get("geometry", "1120x720"))
        self.minsize(900, 600)
        self.configure(fg_color=t.BG)
        self.set_icon()
        self.protocol("WM_DELETE_WINDOW", self.quit_app)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.build_sidebar()
        self.build_main()

        self.refresh_devices()
        threading.Thread(target=lambda: self.from_thread(self.memory_read, memory.modules()), daemon=True).start()
        threading.Thread(target=lambda: diag.icue_running() and self.from_thread(self.warn_icue), daemon=True).start()
        self.after(100, self.run_thread_calls)
        self.after(700, self.watch_show_requests)
        self.after(1500, self.check_updates)
        self.after(2000, self.refresh_sensors)

    # --- mise en page ---
    def set_icon(self):
        try:
            self._icon = ImageTk.PhotoImage(logo.app_icon(64))
            self.iconphoto(True, self._icon)
        except Exception:
            pass
        # Sous Windows, la barre des tâches lit l'icône .ico. L'appel à iconbitmap empêche aussi
        # customtkinter de remettre sa propre icône bleue 200 ms après l'ouverture.
        path = logo.ico_path()
        if sys.platform == "win32" and path:
            try:
                self.iconbitmap(default=path)
            except Exception:
                pass

    def build_sidebar(self):
        side = ctk.CTkFrame(self, fg_color=t.SIDEBAR, corner_radius=0, width=270)
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)
        side.grid_rowconfigure(2, weight=1)
        mark = logo.wordmark(68)  # dessiné en double pour rester net sur les écrans haute densité
        self._wordmark = ctk.CTkImage(light_image=mark, dark_image=mark, size=(mark.width // 2, mark.height // 2))
        ctk.CTkLabel(side, image=self._wordmark, text="").grid(row=0, column=0, padx=22, pady=(24, 18), sticky="w")
        self.home_btn = self.nav_button(side, "Tableau de bord", self.show_home)
        self.home_btn.grid(row=1, column=0, padx=12, sticky="ew")
        self.device_list = ctk.CTkScrollableFrame(side, fg_color="transparent")
        self.device_list.grid(row=2, column=0, padx=4, pady=(10, 0), sticky="nsew")
        foot = ctk.CTkFrame(side, fg_color="transparent")
        foot.grid(row=3, column=0, padx=12, pady=14, sticky="ew")
        button(foot, "Rechercher une mise à jour", lambda: self.check_updates(manual=True)).pack(fill="x")
        button(foot, "Diagnostic", self.run_diag).pack(fill="x", pady=(8, 0))
        label(foot, f"Version {__version__}", 11, t.FAINT).pack(pady=(10, 0))
        side.grid_columnconfigure(0, weight=1)

    def nav_button(self, parent, text, command):
        return ctk.CTkButton(parent, text=text, command=command, anchor="w", height=36, corner_radius=6,
                             fg_color="transparent", hover_color=t.CARD_HI, text_color=t.TEXT,
                             font=ctk.CTkFont(t.FONT, 13))

    def build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=26, pady=(22, 10))
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        self.banner = ctk.CTkFrame(main, fg_color=t.CARD_HI, corner_radius=8, border_width=1, border_color=t.ACCENT)
        self.banner_text = label(self.banner, "", 13, justify="left", anchor="w")
        self.banner_text.pack(side="left", padx=16, pady=10, fill="x", expand=True)
        self.banner_later = button(self.banner, "Plus tard", self.hide_update, height=30, width=90)
        self.banner_later.pack(side="right", padx=(6, 12))
        self.banner_go = button(self.banner, "Mettre à jour", self.install_update, primary=True, height=30, width=120)
        self.banner_go.pack(side="right")
        self.banner_bar = ctk.CTkProgressBar(self.banner, width=140, progress_color=t.ACCENT)

        self.content = ctk.CTkScrollableFrame(main, fg_color="transparent")
        self.content.grid(row=1, column=0, sticky="nsew")
        self.content.grid_columnconfigure((0, 1), weight=1, uniform="col")
        self.status_label = label(main, "", 12, t.MUTED, anchor="w")
        self.status_label.grid(row=2, column=0, sticky="ew", pady=(8, 0))

    def clear(self):
        for child in self.content.winfo_children():
            child.destroy()

    # --- appareils ---
    def warn_icue(self):
        self.icue_warning = True
        self.status("iCUE est lancé : quitte-le (icône près de l'horloge > Quitter), sinon il écrase les réglages "
                    "d'IcueLite.", True)

    def memory_read(self, modules):
        self.memory_modules = modules
        self.refresh_devices()

    def shown_specs(self):
        """Appareils à afficher : ceux qui sont détectés, ou tout le catalogue si on l'a demandé."""
        if self.cfg.get("show_all"):
            return list(CATALOG)
        return [spec for spec in CATALOG if spec.key in self.found]

    def toggle_show_all(self):
        self.cfg["show_all"] = not self.cfg.get("show_all")
        config.save(self.cfg)
        self.refresh_devices()

    def refresh_devices(self):
        self.found, self.unknown = detect(modules=self.memory_modules)
        self.ctrl.attach(self.found)
        for child in self.device_list.winfo_children():
            child.destroy()
        for spec in self.shown_specs():
            text, color = status_of(spec, self.found)
            self.device_row(spec, text, color).pack(fill="x", padx=4, pady=1)
        connected = sum(1 for s in CATALOG if s.key in self.found)
        if self.icue_warning:
            self.warn_icue()
        else:
            self.status(f"{connected} appareil(s) Corsair branché(s) reconnu(s)."
                        + (f" {len(self.unknown)} interface(s) Corsair inconnue(s) : lance le diagnostic."
                           if self.unknown else ""))
        if self.current and (self.current.key in self.found or self.cfg.get("show_all")):
            self.show_device(self.current)
        else:
            self.show_home()

    def device_row(self, spec, text, color):
        """Ligne de la colonne de gauche : nom de l'appareil et son état, cliquable comme un bouton."""
        row = ctk.CTkFrame(self.device_list, fg_color="transparent", corner_radius=6)
        name = label(row, spec.name, 13, t.TEXT if color != t.FAINT else t.MUTED, anchor="w", height=20)
        name.pack(anchor="w", padx=10, pady=(6, 0))
        state = label(row, f"● {text}", 11, color, anchor="w", height=16)
        state.pack(anchor="w", padx=10, pady=(0, 6))
        for widget in (row, name, state):
            widget.bind("<Button-1>", lambda _e: self.show_device(spec))
            widget.bind("<Enter>", lambda _e: row.configure(fg_color=t.CARD_HI))
            widget.bind("<Leave>", lambda _e: row.configure(fg_color="transparent"))
        return row

    def show_home(self):
        self.current = None
        self.clear()
        label(self.content, "Tableau de bord", 24, bold=True).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        specs = self.shown_specs()
        intro = ("Tous les appareils pris en charge par IcueLite." if self.cfg.get("show_all")
                 else "Tes appareils Corsair branchés et ce qu'IcueLite peut en faire.")
        label(self.content, intro, 13, t.MUTED).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 16))
        if not specs:
            label(self.content, "Aucun appareil Corsair détecté. Branche-les, quitte iCUE, puis « Actualiser ».",
                  13, t.FAINT).grid(row=2, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 8))
        for i, spec in enumerate(specs):
            self.device_card(spec).grid(row=2 + i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
        actions = ctk.CTkFrame(self.content, fg_color="transparent")
        actions.grid(row=3 + len(specs) // 2, column=0, columnspan=2, sticky="w", padx=6, pady=(12, 0))
        button(actions, "Actualiser", self.refresh_devices, width=120).pack(side="left")
        button(actions, "Seulement les appareils détectés" if self.cfg.get("show_all")
               else "Voir tous les appareils pris en charge", self.toggle_show_all, width=260).pack(side="left", padx=8)

    def device_card(self, spec):
        card = ctk.CTkFrame(self.content, fg_color=t.CARD, corner_radius=10, border_width=1, border_color=t.BORDER)
        card.grid_columnconfigure(0, weight=1)
        text, color = status_of(spec, self.found)
        texts = ctk.CTkFrame(card, fg_color="transparent")
        texts.grid(row=0, column=0, sticky="nw")
        label(texts, KIND_LABELS.get(spec.kind, "").upper(), 11, t.MUTED).pack(anchor="w", padx=16, pady=(14, 0))
        label(texts, spec.name, 16, bold=True, anchor="w", justify="left", wraplength=200).pack(anchor="w", padx=16)
        label(texts, f"● {text}", 12, color).pack(anchor="w", padx=16, pady=(4, 0))
        button(texts, "Ouvrir", lambda: self.show_device(spec), height=28, width=90).pack(anchor="w", padx=16, pady=(10, 14))
        image = device_image(spec.key, 170, 110, self.preview_colors(spec.key))
        if image:
            pic = ctk.CTkLabel(card, image=image, text="", cursor="hand2")
            pic.grid(row=0, column=1, padx=(0, 10), pady=8, sticky="e")
            pic.bind("<Button-1>", lambda _e: self.show_device(spec))
        return card

    def show_device(self, spec):
        self.current = spec
        self.clear()
        text, color = status_of(spec, self.found)
        label(self.content, KIND_LABELS.get(spec.kind, "").upper(), 12, t.MUTED).grid(row=0, column=0, sticky="w")
        label(self.content, spec.name, 24, bold=True).grid(row=1, column=0, columnspan=2, sticky="w")
        label(self.content, f"● {text}", 13, color).grid(row=2, column=0, sticky="w", pady=(2, 14))
        self.photo_card(spec)

        info = ctk.CTkFrame(self.content, fg_color=t.CARD, corner_radius=10, border_width=1, border_color=t.BORDER)
        info.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        lines = [("Référence", spec.ref), ("Liaison", spec.link)]
        detected = self.found.get(spec.key)
        if detected:
            if detected.interfaces:
                lines.append(("Identifiant USB", f"1B1C:{detected.pid:04X}, {len(detected.interfaces)} interface(s)"))
            lines += detected.details
        for r, (k, v) in enumerate(lines):
            label(info, k, 12, t.MUTED).grid(row=r, column=0, sticky="nw", padx=(16, 12), pady=(12 if r == 0 else 4, 4))
            label(info, v, 13, anchor="w", justify="left", wraplength=560).grid(
                row=r, column=1, sticky="w", pady=(12 if r == 0 else 4, 4))
        note = detected.note if detected and detected.note else spec.note
        if note:
            label(info, note, 12, t.WARNING, anchor="w", justify="left", wraplength=640).grid(
                row=len(lines), column=0, columnspan=2, sticky="w", padx=16, pady=(4, 0))
        ctk.CTkFrame(info, fg_color="transparent", height=10).grid(row=len(lines) + 1, column=0)

        driver = self.ctrl.drivers.get(spec.key)
        self.sensor_labels = None
        self.icue_warning = False   # iCUE lancé à l'ouverture d'IcueLite
        self.memory_modules = None  # barrettes lues par Windows, en arrière-plan (une seconde environ)
        if driver is not None:
            self.settings_panels(spec, driver, row=5)
            if driver.experimental:
                label(info, "Protocole repris des projets libres, pas encore vérifié sur ce modèle : "
                      "si un réglage ne prend pas, lance le diagnostic et envoie-le.", 12, t.WARNING,
                      anchor="w", justify="left", wraplength=640).grid(
                    row=len(lines) + 2, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 10))
            self.ctrl.firmware(spec.key, lambda fw: self.from_thread(self.show_firmware, spec, info, len(lines) + 3, fw))
        elif spec.features:
            box = self.card_frame(row=5)
            label(box, "Réglages", 15, bold=True).pack(anchor="w", padx=16, pady=(14, 6))
            for feat in spec.features:
                label(box, f"•  {feat}", 13, t.MUTED).pack(anchor="w", padx=22, pady=1)
            if spec.key in self.ctrl.errors:
                why = f"Impossible d'ouvrir l'appareil : {self.ctrl.errors[spec.key]}"
            elif spec.key not in DRIVERS:
                why = "Pilote pas encore écrit pour cet appareil : il arrive dans une prochaine version."
            else:
                why = "Branche l'appareil pour régler tout ça (puis « Actualiser » sur le tableau de bord)."
            label(box, why, 12, t.FAINT, anchor="w", justify="left", wraplength=640).pack(anchor="w", padx=16, pady=(8, 14))

    def card_frame(self, row, pady=(0, 12)):
        box = ctk.CTkFrame(self.content, fg_color=t.CARD, corner_radius=10, border_width=1, border_color=t.BORDER)
        box.grid(row=row, column=0, columnspan=2, sticky="ew", pady=pady)
        return box

    def show_firmware(self, spec, info, row, fw):
        if fw and self.current is spec and info.winfo_exists():
            label(info, "Firmware", 12, t.MUTED).grid(row=row, column=0, sticky="nw", padx=(16, 12), pady=(0, 10))
            label(info, fw, 13, anchor="w").grid(row=row, column=1, sticky="w", pady=(0, 10))

    def preview_colors(self, key):
        """Couleurs mémorisées de l'appareil, au format de render.compose."""
        stored = self.ctrl.settings(key)["colors"]
        return {zone: (tuple(c) if c else None) for zone, c in stored.items()}

    def on_driver_message(self, key, text, error):
        spec = next((s for s in CATALOG if s.key == key), None)
        self.status(f"{spec.name if spec else key} : {text}", error)

    # --- panneaux de réglages ---
    def settings_panels(self, spec, driver, row):
        s = self.ctrl.settings(spec.key)
        if driver.dpi_range:
            self.dpi_panel(spec, driver, s, row)
            row += 1
        if driver.poll_rates:
            box = self.card_frame(row)
            row += 1
            label(box, "Fréquence d'interrogation", 15, bold=True).pack(anchor="w", padx=16, pady=(14, 6))
            values = [f"{hz} Hz" for hz in driver.poll_rates]
            seg = ctk.CTkSegmentedButton(box, values=values, selected_color=t.ACCENT, selected_hover_color=t.ACCENT_HOVER,
                                         text_color=t.TEXT, font=ctk.CTkFont(t.FONT, 12),
                                         command=lambda v: self.set_poll(spec, int(v.split()[0])))
            seg.set(f"{s['poll']} Hz" if s["poll"] in driver.poll_rates else values[-1])
            seg.pack(anchor="w", padx=16, pady=(0, 14))
        if driver.fans or driver.sensors:
            self.fan_panel(spec, driver, s, row)

    def dpi_panel(self, spec, driver, s, row):
        box = self.card_frame(row)
        label(box, "DPI", 15, bold=True).pack(anchor="w", padx=16, pady=(14, 2))
        label(box, f"Jusqu'à {driver.dpi_stage_count} paliers ; le bouton DPI de la souris passe de l'un à l'autre.",
              12, t.FAINT).pack(anchor="w", padx=16, pady=(0, 6))
        lo, hi, step = driver.dpi_range
        stages = list(s["dpi"])
        active = ctk.IntVar(value=s["dpi_active"])
        rows = ctk.CTkFrame(box, fg_color="transparent")
        rows.pack(anchor="w", fill="x", padx=16)

        def apply():
            s["dpi"] = [int(v) for v in stages]
            s["dpi_active"] = min(active.get(), len(stages) - 1)
            self.ctrl.save(spec.key, "dpi")
            self.ctrl.submit(spec.key, "set_dpi", list(s["dpi"]), s["dpi_active"], label="DPI")

        def draw():
            for child in rows.winfo_children():
                child.destroy()
            for i, value in enumerate(stages):
                line = ctk.CTkFrame(rows, fg_color="transparent")
                line.pack(anchor="w", fill="x", pady=2)
                ctk.CTkRadioButton(line, text=f"Palier {i + 1}", variable=active, value=i, width=100,
                                   fg_color=t.ACCENT, hover_color=t.ACCENT_HOVER, font=ctk.CTkFont(t.FONT, 12),
                                   command=apply).pack(side="left")
                shown = label(line, f"{value} DPI", 12, width=80)
                slider = ctk.CTkSlider(line, from_=lo, to=hi, number_of_steps=(hi - lo) // step, width=380,
                                       button_color=t.ACCENT, button_hover_color=t.ACCENT_HOVER, progress_color=t.ACCENT)
                slider.set(value)

                def moved(v, i=i, shown=shown):
                    stages[i] = int(round(v / step) * step)
                    shown.configure(text=f"{stages[i]} DPI")
                slider.configure(command=moved)
                slider.bind("<ButtonRelease-1>", lambda _e: apply())
                slider.pack(side="left", padx=10)
                shown.pack(side="left")

        def add():
            if len(stages) < driver.dpi_stage_count:
                stages.append(min(hi, (stages[-1] if stages else 800) * 2))
                draw()
                apply()

        def remove():
            if len(stages) > 1:
                stages.pop()
                if active.get() >= len(stages):
                    active.set(len(stages) - 1)
                draw()
                apply()

        draw()
        actions = ctk.CTkFrame(box, fg_color="transparent")
        actions.pack(anchor="w", padx=16, pady=(6, 14))
        button(actions, "Ajouter un palier", add, height=28, width=140).pack(side="left")
        button(actions, "Retirer le dernier", remove, height=28, width=140).pack(side="left", padx=8)

    def set_poll(self, spec, hz):
        self.ctrl.settings(spec.key)["poll"] = hz
        self.ctrl.save(spec.key, "poll")
        self.ctrl.submit(spec.key, "set_poll_rate", hz, label="Fréquence")

    def fan_panel(self, spec, driver, s, row):
        box = self.card_frame(row)
        label(box, "Ventilation", 15, bold=True).pack(anchor="w", padx=16, pady=(14, 6))
        if driver.fans:
            line = ctk.CTkFrame(box, fg_color="transparent")
            line.pack(anchor="w", fill="x", padx=16)
            shown = label(line, "", 12, width=60)
            slider = ctk.CTkSlider(line, from_=driver.min_duty, to=100, number_of_steps=(100 - driver.min_duty) // 5,
                                   width=320, button_color=t.ACCENT,
                                   button_hover_color=t.ACCENT_HOVER, progress_color=t.ACCENT)
            slider.set(s["fan"] or 50)

            def apply_fan():
                self.ctrl.save(spec.key, "fan")
                self.ctrl.submit(spec.key, "set_fan_duty", s["fan"],
                                 label="Ventilateurs" if s["fan"] is None else f"Ventilateurs à {s['fan']} %")

            def mode(value):
                s["fan"] = None if value == "Automatique" else int(slider.get())
                style_slider()
                shown.configure(text="" if s["fan"] is None else f"{s['fan']} %")
                apply_fan()

            def moved(v):
                shown.configure(text=f"{int(v)} %")

            def released(_e):
                if s["fan"] is not None:
                    s["fan"] = int(slider.get())
                    apply_fan()

            def style_slider():
                on = s["fan"] is not None
                slider.configure(state="normal" if on else "disabled", button_color=t.ACCENT if on else t.FAINT,
                                 progress_color=t.ACCENT if on else t.FAINT)

            seg = ctk.CTkSegmentedButton(line, values=["Automatique", "Vitesse fixe"], selected_color=t.ACCENT,
                                         selected_hover_color=t.ACCENT_HOVER, font=ctk.CTkFont(t.FONT, 12), command=mode)
            seg.set("Automatique" if s["fan"] is None else "Vitesse fixe")
            seg.pack(side="left")
            slider.configure(command=moved)
            style_slider()
            slider.bind("<ButtonRelease-1>", released)
            slider.pack(side="left", padx=12)
            shown.configure(text="" if s["fan"] is None else f"{s['fan']} %")
            shown.pack(side="left")
            auto = ("la vitesse suit la température du liquide" if driver.pump_modes
                    else "le hub suit sa propre courbe")
            label(box, f"Automatique : {auto}. Vitesse fixe : jamais sous {driver.min_duty} %.", 12, t.FAINT).pack(
                anchor="w", padx=16, pady=(4, 0))
        if driver.pump_modes:
            line = ctk.CTkFrame(box, fg_color="transparent")
            line.pack(anchor="w", fill="x", padx=16, pady=(10, 0))
            label(line, "Pompe", 12, t.MUTED, width=80, anchor="w").pack(side="left")

            def pump(value):
                s["pump"] = value
                self.ctrl.save(spec.key, "pump")
                self.ctrl.submit(spec.key, "set_pump_mode", value, label=f"Pompe en mode {value.lower()}")
            seg = ctk.CTkSegmentedButton(line, values=list(driver.pump_modes), selected_color=t.ACCENT,
                                         selected_hover_color=t.ACCENT_HOVER, font=ctk.CTkFont(t.FONT, 12), command=pump)
            seg.set(s["pump"] or driver.pump_modes[1])
            seg.pack(side="left")
        if driver.sensors:
            self.sensor_labels = (spec.key, label(box, "Lecture des régimes…", 13, t.MUTED, anchor="w", justify="left"))
            self.sensor_labels[1].pack(anchor="w", padx=16, pady=(8, 14))
        else:
            ctk.CTkFrame(box, fg_color="transparent", height=8).pack()

    def refresh_sensors(self):
        if self.sensor_labels and self.sensor_labels[1].winfo_exists():
            key, widget = self.sensor_labels
            data = self.ctrl.sensors.get(key)
            if data:
                parts = [f"{name} : {rpm} tr/min" for name, rpm in data["fans"]]
                parts += [f"{name} : {temp:.1f} °C" for name, temp in data["temps"]]
                widget.configure(text="   ".join(parts) or "Aucun ventilateur ni sonde détecté sur le hub.")
        self.after(2000, self.refresh_sensors)

    def photo_card(self, spec):
        """Grande photo de l'appareil et, s'il a des zones lumineuses, un aperçu de leurs couleurs."""
        s = self.ctrl.settings(spec.key)
        driver = self.ctrl.drivers.get(spec.key)
        image = device_image(spec.key, 640, 300, self.preview_colors(spec.key))
        if image is None:
            return
        card = ctk.CTkFrame(self.content, fg_color=t.CARD, corner_radius=10, border_width=1, border_color=t.BORDER)
        card.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        pic = ctk.CTkLabel(card, image=image, text="")
        pic.pack(padx=16, pady=(14, 6))
        zones = list(driver.zones) if driver and driver.zones else render.zones(spec.key)
        if not zones:
            ctk.CTkFrame(card, fg_color="transparent", height=8).pack()
            return
        live = bool(driver and driver.zones)
        label(card, "Éclairage" if live else "Aperçu de l'éclairage (sur l'image seulement : appareil non branché "
              "ou pas encore piloté)", 15 if live else 12, t.TEXT if live else t.FAINT, bold=live).pack(
            anchor="w", padx=16, pady=(0, 4))

        def pick(zone, value):
            if value == "origin":
                s["colors"].pop(zone, None)
            elif value == "custom":
                from tkinter import colorchooser
                current = s["colors"].get(zone) or (255, 212, 0)
                chosen = colorchooser.askcolor(color="#%02x%02x%02x" % tuple(current), title=f"Couleur : {zone}")[0]
                if not chosen:
                    return
                s["colors"][zone] = [int(c) for c in chosen]
            else:
                s["colors"][zone] = list(value) if value else None
            self.ctrl.save(spec.key, "colors")
            pic.configure(image=device_image(spec.key, 640, 300, self.preview_colors(spec.key)))
            # l'appareil a pu être pris en main après l'ouverture de la page : on regarde au moment du clic
            current = self.ctrl.drivers.get(spec.key)
            if current and current.zones:
                self.ctrl.apply_colors(spec.key, label="Éclairage")
            else:
                why = self.ctrl.errors.get(spec.key, "pas encore de pilote d'éclairage")
                self.status(f"{spec.name} : couleur gardée pour plus tard, l'appareil n'est pas pris en main ({why}).",
                            True)

        for zone in zones:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(anchor="w", padx=16, pady=(0, 6))
            label(row, zone, 12, t.MUTED, width=110, anchor="w").pack(side="left")
            for name, value in SWATCHES:
                fill = "#%02x%02x%02x" % value if isinstance(value, tuple) else t.CARD_HI
                ctk.CTkButton(row, text=" " if isinstance(value, tuple) else name, width=28 if isinstance(value, tuple) else 70,
                              height=24, corner_radius=12, fg_color=fill, hover_color=fill, border_width=1,
                              border_color=t.BORDER, text_color=t.TEXT, font=ctk.CTkFont(t.FONT, 11),
                              command=lambda z=zone, v=value: pick(z, v)).pack(side="left", padx=2)
            ctk.CTkButton(row, text="Autre…", width=60, height=24, corner_radius=12, fg_color=t.CARD_HI,
                          hover_color=t.BORDER, border_width=1, border_color=t.BORDER, text_color=t.TEXT,
                          font=ctk.CTkFont(t.FONT, 11), command=lambda z=zone: pick(z, "custom")).pack(side="left", padx=2)
        if live and driver.brightness:
            line = ctk.CTkFrame(card, fg_color="transparent")
            line.pack(anchor="w", padx=16, pady=(4, 6))
            label(line, "Luminosité", 12, t.MUTED, width=110, anchor="w").pack(side="left")
            shown = label(line, f"{s['brightness']} %", 12, width=50)
            slider = ctk.CTkSlider(line, from_=0, to=100, number_of_steps=20, width=300, button_color=t.ACCENT,
                                   button_hover_color=t.ACCENT_HOVER, progress_color=t.ACCENT,
                                   command=lambda v: shown.configure(text=f"{int(v)} %"))
            slider.set(s["brightness"])

            def released(_e):
                s["brightness"] = int(slider.get())
                self.ctrl.save(spec.key, "colors")
                self.ctrl.apply_colors(spec.key, label="Luminosité")
            slider.bind("<ButtonRelease-1>", released)
            slider.pack(side="left", padx=(4, 10))
            shown.pack(side="left")
        ctk.CTkFrame(card, fg_color="transparent", height=8).pack()

    def run_diag(self):
        self.status("Diagnostic en cours…")

        def work():
            folder = Path.home() / "Desktop"
            try:
                path = diag.write(folder if folder.is_dir() else updater.install_dir(), extra=self.ctrl.journal())
            except Exception as exc:
                self.from_thread(self.status, f"Diagnostic impossible : {exc}", True)
                return
            self.from_thread(self.status, "Diagnostic enregistré, envoi à Erwan (jusqu'à une minute)…")
            try:
                diag.send(path.read_text(encoding="utf-8"), __version__)
            except Exception as exc:
                self.from_thread(self.status, f"Envoi impossible : {exc}. "
                                 f"Le fichier est sur le Bureau : {path.name}", True)
                return
            self.from_thread(self.status, "Diagnostic envoyé à Erwan. Merci !")

        threading.Thread(target=work, daemon=True).start()

    # --- outils ---
    def status(self, text, error=False):
        self.status_label.configure(text=text, text_color=t.DANGER if error else t.MUTED)

    def from_thread(self, fn, *args):
        """Fait exécuter fn par l'interface (tkinter ne doit être touché que depuis son propre fil)."""
        self._from_threads.put((fn, args))

    def run_thread_calls(self):
        while not self._from_threads.empty():
            fn, args = self._from_threads.get()
            fn(*args)
        self.after(100, self.run_thread_calls)

    def watch_show_requests(self):
        if instance.show_requested():
            self.deiconify()
            self.lift()
            self.focus_force()
        self.after(700, self.watch_show_requests)

    # --- mises à jour ---
    def check_updates(self, manual=False):
        if not manual:
            self.after(6 * 3600 * 1000, self.check_updates)
        if not updater.repo():
            if manual:
                self.status("Mises à jour non configurées (dépôt GitHub inconnu).", True)
            return
        if manual:
            self.status("Recherche d'une mise à jour…")

        def work():
            try:
                info = updater.check()
            except Exception as exc:  # pas d'Internet, GitHub indisponible…
                info = exc
            self.from_thread(self.on_update_checked, info, manual)

        threading.Thread(target=work, daemon=True).start()

    def on_update_checked(self, info, manual):
        if isinstance(info, Exception):
            if manual:
                self.status(f"Impossible de vérifier les mises à jour : {updater.describe(info)}.", True)
            return
        if not info:
            if manual:
                self.status(f"IcueLite est à jour (version {__version__}).")
            return
        self.update_info = info
        notes = info["notes"].splitlines()[0] if info["notes"] else ""
        text = f"Nouvelle version {info['version']} disponible (tu as la {__version__})."
        self.banner_text.configure(text=text + (f"\n{notes[:110]}" if notes else ""))
        self.banner.grid(row=0, column=0, sticky="ew", pady=(0, 14))

    def hide_update(self):
        self.banner.grid_remove()

    def install_update(self):
        info = self.update_info
        if not info:
            return
        self.banner_go.pack_forget()
        self.banner_later.pack_forget()
        self.banner_bar.set(0)
        self.banner_bar.pack(side="right", padx=16)
        self.banner_text.configure(text=f"Téléchargement de la version {info['version']}…")

        def work():
            try:
                updater.install(info, lambda frac: self.from_thread(self.banner_bar.set, frac))
            except Exception as exc:
                self.from_thread(self.update_failed, exc)
                return
            self.from_thread(self.update_done)

        threading.Thread(target=work, daemon=True).start()

    def update_done(self):
        self.banner_text.configure(text="Mise à jour installée, redémarrage…")
        self.after(600, self.quit_app)

    def update_failed(self, exc):
        self.banner_bar.pack_forget()
        self.banner_later.pack(side="right", padx=(6, 12))
        self.banner_go.pack(side="right")
        self.banner_text.configure(text=f"La mise à jour a échoué : {exc}")

    def quit_app(self):
        self.cfg["geometry"] = self.geometry()
        config.save(self.cfg)
        self.ctrl.shutdown()  # les appareils reprennent leur éclairage et leur ventilation autonomes
        self.destroy()


def run(after_update=False):
    # Après une mise à jour, l'ancienne copie est en train de se fermer : on lui laisse le temps.
    lock = instance.acquire(wait=20 if after_update else 0)
    if lock is None:
        instance.ask_existing_to_show()
        return 0
    instance.show_requested()  # efface une vieille demande restée en plan
    if sys.platform == "win32":
        # Identité propre : la barre des tâches n'affiche pas IcueLite comme « Python »
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("IcueLite.App")
        except (AttributeError, OSError):
            pass
    app = App()
    app.mainloop()
    return 0
