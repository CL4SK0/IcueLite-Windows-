"""Pilotage des appareils en arrière-plan : ouvre les pilotes, applique et mémorise les réglages.

Les échanges USB passent tous par un seul fil de travail, pour ne jamais bloquer l'interface et ne jamais
envoyer deux paquets en même temps au même appareil. Les réglages sont rangés dans la config
(config["devices"][clé]) et réappliqués à chaque démarrage.
"""

import queue
import threading
import time

from . import config as cfgmod
from .drivers import DriverError, has_driver, open_driver

DEFAULTS = {
    "colors": {},          # zone -> [r, g, b] ou None (éteint)
    "brightness": 100,
    "dpi": [800, 1600, 3200],
    "dpi_active": 1,
    "poll": 1000,
    "fan": None,           # None = le hub gère, sinon consigne en %
}


class Controller:
    def __init__(self, cfg, notify=None):
        self.cfg = cfg
        self.notify = notify or (lambda key, text, error=False: None)
        self.drivers = {}
        self.errors = {}
        self.sensors = {}
        self.jobs = queue.Queue()
        self.stopping = False
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    # --- réglages mémorisés ---
    def settings(self, key):
        stored = self.cfg.setdefault("devices", {}).setdefault(key, {})
        for name, value in DEFAULTS.items():
            stored.setdefault(name, value if not isinstance(value, (dict, list)) else type(value)(value))
        return stored

    def save(self, key=None, touched=None):
        """Enregistre la config ; touched note un réglage choisi par l'utilisateur (seuls ceux-là sont
        réappliqués au démarrage : sans ça, on écraserait les réglages embarqués de l'appareil)."""
        if key and touched:
            names = self.settings(key).setdefault("touched", [])
            if touched not in names:
                names.append(touched)
        cfgmod.save(self.cfg)

    # --- fil de travail ---
    def submit(self, key, action, *args, label=""):
        self.jobs.put((key, action, args, label))

    def _loop(self):
        last_tick = time.monotonic()
        while not self.stopping:
            try:
                key, action, args, label = self.jobs.get(timeout=0.5)
            except queue.Empty:
                key = None
            if key is not None:
                self._run(key, action, args, label)
            if time.monotonic() - last_tick >= 4:
                last_tick = time.monotonic()
                self._tick()

    def _run(self, key, action, args, label):
        if action == "_call":
            return args[0]()
        driver = self.drivers.get(key)
        if driver is None:
            return
        try:
            result = getattr(driver, action)(*args)
        except (DriverError, OSError) as exc:
            self.notify(key, f"{label or action} : {exc}", True)
            return
        if label:
            self.notify(key, f"{label} : appliqué.")
        return result

    def _tick(self):
        for key, driver in list(self.drivers.items()):
            try:
                driver.keepalive()
                if driver.sensors:
                    self.sensors[key] = driver.read_sensors()
            except (DriverError, OSError) as exc:
                self.errors[key] = str(exc)

    # --- appareils ---
    def attach(self, found):
        """Ouvre les pilotes des appareils détectés (et ferme ceux qui ont disparu), puis réapplique leurs réglages."""
        for key in list(self.drivers):
            if key not in found:
                gone = self.drivers.pop(key)
                self.jobs.put((key, "_call", (lambda d=gone: self._close(d),), ""))
        for key, detected in found.items():
            if key in self.drivers or not has_driver(key):
                continue
            try:
                self.drivers[key] = open_driver(detected)
                self.errors.pop(key, None)
            except DriverError as exc:
                self.errors[key] = str(exc)
                continue
            self.apply_all(key)

    def apply_all(self, key):
        driver = self.drivers.get(key)
        if driver is None:
            return
        s = self.settings(key)
        touched = s.get("touched", [])
        if driver.zones and "colors" in touched:
            self.apply_colors(key)
        if driver.dpi_range and "dpi" in touched:
            self.submit(key, "set_dpi", list(s["dpi"]), s["dpi_active"])
        if driver.poll_rates and "poll" in touched and s["poll"] in driver.poll_rates:
            self.submit(key, "set_poll_rate", s["poll"])
        if driver.fans and "fan" in touched and s["fan"] is not None:
            self.submit(key, "set_fan_duty", s["fan"])

    def apply_colors(self, key, label=""):
        s = self.settings(key)
        if not s["colors"]:
            # tout « d'origine » : l'appareil reprend son propre éclairage
            self.submit(key, "release", label=label)
            return
        colors = {zone: (tuple(c) if c else None) for zone, c in s["colors"].items()}
        self.submit(key, "set_colors", colors, s["brightness"], label=label)

    def firmware(self, key, callback):
        def job():
            driver = self.drivers.get(key)
            try:
                callback(driver.firmware() if driver else None)
            except (DriverError, OSError):
                callback(None)
        self.jobs.put((key, "_call", (job,), ""))

    def journal(self):
        """Derniers échanges de chaque pilote, pour le diagnostic."""
        lines = []
        for key, driver in self.drivers.items():
            lines.append(f"[{key}] {type(driver).__name__} interface if={driver.interface.get('interface_number')} "
                         f"page={driver.interface.get('usage_page', 0):04x}")
            lines += [f"  {t} {way} {text}" for t, way, text in driver.log]
        for key, err in self.errors.items():
            lines.append(f"[{key}] erreur : {err}")
        return lines

    @staticmethod
    def _close(driver):
        try:
            driver.close()
        except (DriverError, OSError):
            pass

    def shutdown(self):
        """Rend la main aux appareils (éclairage et ventilation autonomes) et ferme tout."""
        self.stopping = True
        self.thread.join(timeout=3)
        for driver in self.drivers.values():
            self._close(driver)
        self.drivers.clear()
