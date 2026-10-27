"""Socle commun des pilotes : choix de l'interface USB, envoi des paquets et journal pour le diagnostic.

Chaque pilote annonce ce qu'il sait faire par des attributs simples (zones, dpi, poll_rates, fans…) ;
l'interface n'affiche que les réglages correspondants.
"""

import time
from collections import deque


class DriverError(Exception):
    pass


def hexdump(data, limit=24):
    data = bytes(data)
    text = " ".join(f"{b:02x}" for b in data[:limit])
    return text + (" …" if len(data) > limit else "")


def pick_interface(interfaces, usage_pages=None, min_output=0):
    """L'interface « constructeur » (usage page FFxx) qui accepte des rapports de sortie assez longs."""
    candidates = [i for i in interfaces if i.get("usage_page", 0) >= 0xFF00
                  and i.get("output_report_length", 0) >= min_output]
    if usage_pages:
        preferred = [i for i in candidates if i.get("usage_page") in usage_pages]
        candidates = preferred or candidates
    if not candidates:
        raise DriverError("aucune interface de commande trouvée (lance le diagnostic)")
    return sorted(candidates, key=lambda i: (i.get("interface_number", 0), i.get("usage_page", 0)))[0]


class Driver:
    """Pilote d'un appareil. Les sous-classes remplissent les capacités et les méthodes qu'elles gèrent."""

    experimental = False   # protocole tiré des projets libres mais pas encore vérifié sur l'appareil
    zones = ()             # zones lumineuses réglables, dans les noms des visuels (Logo, Molette, Touches…)
    brightness = False     # luminosité générale (0-100 %)
    dpi_range = None       # (min, max, pas) si la souris accepte des paliers DPI
    dpi_stage_count = 0
    poll_rates = ()        # fréquences d'interrogation possibles, en Hz
    fans = False           # vitesse des ventilateurs
    min_duty = 20          # vitesse fixe minimale, en %
    pump_modes = ()        # modes de pompe proposés (watercooling)
    sensors = False        # régimes et températures à lire

    def __init__(self, transport, interface=None):
        self.transport = transport
        self.interface = interface or {}
        self.log = deque(maxlen=150)
        self.software_mode = False
        self.reopen = None        # fonction qui rouvre l'appareil (fournie par open_driver)
        self.polling = False      # lecture périodique des capteurs : seules les premières sont notées
        self.polls_logged = 0

    def note(self, way, text):
        if self.polling and way != "!":
            if self.polls_logged >= 6:
                return
            self.polls_logged += 1
        self.log.append((time.strftime("%H:%M:%S"), way, text))

    def _reconnect(self, exc):
        """L'appareil s'est reconnecté (changement de fréquence, mise en veille, iCUE…) : la poignée ouverte
        ne vaut plus rien. On le rouvre, en repartant du mode autonome."""
        if self.reopen is None:
            return False
        for attempt in range(8):
            # l'appareil met une ou deux secondes à revenir après une reconnexion
            time.sleep(0.5)
            try:
                transport, interface = self.reopen()
                break
            except (OSError, DriverError) as err:
                last = err
        else:
            self.note("!", f"réouverture impossible : {last}")
            return False
        try:
            self.transport.close()
        except OSError:
            pass
        self.transport, self.interface = transport, interface
        self.software_mode = False
        self.after_reconnect()
        self.note("*", f"appareil rouvert après « {exc} »")
        return True

    def after_reconnect(self):
        """Oublie l'état propre à l'ancienne connexion (à surcharger)."""

    # --- échanges ---
    def send(self, packet):
        packet = bytes(packet)
        self.note(">", hexdump(packet))
        try:
            self.transport.write(packet)
        except OSError as exc:
            self.note("!", str(exc))
            if not self._reconnect(exc):
                raise DriverError(f"envoi impossible : {exc}") from exc
            try:
                self.transport.write(packet)
            except OSError as again:
                self.note("!", str(again))
                raise DriverError(f"envoi impossible : {again}") from again

    def receive(self, timeout_ms=500):
        try:
            data = self.transport.read(timeout_ms)
        except OSError as exc:
            self.note("!", str(exc))
            raise DriverError(f"lecture impossible : {exc}") from exc
        self.note("<", hexdump(data) if data else "(rien)")
        return data

    def flush(self):
        if hasattr(self.transport, "flush"):
            self.transport.flush()

    # --- capacités (à surcharger) ---
    def firmware(self):
        return None

    def set_colors(self, colors, brightness=100):
        """colors : {zone: (r, g, b) ou None pour éteindre}."""
        raise DriverError("éclairage non géré")

    def set_dpi(self, stages, active):
        raise DriverError("DPI non géré")

    def set_poll_rate(self, hz):
        raise DriverError("fréquence non gérée")

    def set_fan_duty(self, percent):
        raise DriverError("ventilateurs non gérés")

    def set_pump_mode(self, name):
        raise DriverError("pompe non gérée")

    def read_sensors(self):
        """{"fans": [(nom, tr/min)], "temps": [(nom, °C)]}."""
        return {"fans": [], "temps": []}

    def keepalive(self):
        """Appelé régulièrement : certains appareils reviennent à leur mode autonome sans nouvelles."""

    def release(self):
        """Rend la main à l'appareil (éclairage et réglages embarqués) avant de fermer."""

    def close(self):
        try:
            self.release()
        except DriverError:
            pass
        self.transport.close()
