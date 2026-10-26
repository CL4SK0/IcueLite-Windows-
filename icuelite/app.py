"""Interface graphique d'IcueLite : appareils dans la colonne de gauche, détail à droite, comme iCUE."""

import os
import queue
import sys
import threading
from pathlib import Path

import customtkinter as ctk
from PIL import ImageTk

from . import __version__, config, diag, instance, logo, updater
from . import theme as t
from .devices import CATALOG, MOTHERBOARD, NOTHING, detect

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
        self.after(100, self.run_thread_calls)
        self.after(700, self.watch_show_requests)
        self.after(1500, self.check_updates)

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
    def refresh_devices(self):
        self.found, self.unknown = detect()
        for child in self.device_list.winfo_children():
            child.destroy()
        for spec in CATALOG:
            text, color = status_of(spec, self.found)
            self.device_row(spec, text, color).pack(fill="x", padx=4, pady=1)
        connected = sum(1 for s in CATALOG if s.key in self.found)
        self.status(f"{connected} appareil(s) Corsair branché(s) reconnu(s)."
                    + (f" {len(self.unknown)} interface(s) Corsair inconnue(s) : lance le diagnostic." if self.unknown else ""))
        if self.current:
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
        label(self.content, "Tes appareils Corsair et ce qu'IcueLite peut en faire.", 13, t.MUTED).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 16))
        for i, spec in enumerate(CATALOG):
            self.device_card(spec).grid(row=2 + i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
        button(self.content, "Actualiser", self.refresh_devices, width=120).grid(
            row=3 + len(CATALOG) // 2, column=0, sticky="w", padx=6, pady=(12, 0))

    def device_card(self, spec):
        card = ctk.CTkFrame(self.content, fg_color=t.CARD, corner_radius=10, border_width=1, border_color=t.BORDER)
        text, color = status_of(spec, self.found)
        label(card, KIND_LABELS.get(spec.kind, "").upper(), 11, t.MUTED).pack(anchor="w", padx=16, pady=(14, 0))
        label(card, spec.name, 16, bold=True, anchor="w", justify="left", wraplength=360).pack(anchor="w", padx=16)
        label(card, f"● {text}", 12, color).pack(anchor="w", padx=16, pady=(4, 0))
        button(card, "Ouvrir", lambda: self.show_device(spec), height=28, width=90).pack(anchor="w", padx=16, pady=(10, 14))
        return card

    def show_device(self, spec):
        self.current = spec
        self.clear()
        text, color = status_of(spec, self.found)
        label(self.content, KIND_LABELS.get(spec.kind, "").upper(), 12, t.MUTED).grid(row=0, column=0, sticky="w")
        label(self.content, spec.name, 24, bold=True).grid(row=1, column=0, columnspan=2, sticky="w")
        label(self.content, f"● {text}", 13, color).grid(row=2, column=0, sticky="w", pady=(2, 14))

        info = ctk.CTkFrame(self.content, fg_color=t.CARD, corner_radius=10, border_width=1, border_color=t.BORDER)
        info.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        lines = [("Référence", spec.ref), ("Liaison", spec.link)]
        detected = self.found.get(spec.key)
        if detected:
            lines.append(("Identifiant USB", f"1B1C:{detected.pid:04X}, {len(detected.interfaces)} interface(s)"))
        for r, (k, v) in enumerate(lines):
            label(info, k, 12, t.MUTED).grid(row=r, column=0, sticky="nw", padx=(16, 12), pady=(12 if r == 0 else 4, 4))
            label(info, v, 13, anchor="w", justify="left", wraplength=560).grid(
                row=r, column=1, sticky="w", pady=(12 if r == 0 else 4, 4))
        if spec.note:
            label(info, spec.note, 12, t.WARNING, anchor="w", justify="left", wraplength=640).grid(
                row=len(lines), column=0, columnspan=2, sticky="w", padx=16, pady=(4, 0))
        ctk.CTkFrame(info, fg_color="transparent", height=10).grid(row=len(lines) + 1, column=0)

        if spec.features:
            box = ctk.CTkFrame(self.content, fg_color=t.CARD, corner_radius=10, border_width=1, border_color=t.BORDER)
            box.grid(row=4, column=0, columnspan=2, sticky="ew")
            label(box, "Réglages prévus", 15, bold=True).pack(anchor="w", padx=16, pady=(14, 6))
            for feat in spec.features:
                label(box, f"•  {feat}", 13, t.MUTED).pack(anchor="w", padx=22, pady=1)
            label(box, "Les réglages arrivent appareil par appareil dans les prochaines versions.", 12, t.FAINT).pack(
                anchor="w", padx=16, pady=(8, 14))

    def run_diag(self):
        self.status("Diagnostic en cours…")

        def work():
            folder = Path.home() / "Desktop"
            try:
                path = diag.write(folder if folder.is_dir() else updater.install_dir())
            except Exception as exc:
                self.from_thread(self.status, f"Diagnostic impossible : {exc}", True)
                return
            self.from_thread(self.diag_done, path)

        threading.Thread(target=work, daemon=True).start()

    def diag_done(self, path):
        self.status(f"Diagnostic enregistré : {path}")
        if sys.platform == "win32":
            os.startfile(path)

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
                self.status("Impossible de vérifier les mises à jour (connexion ?).", True)
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
