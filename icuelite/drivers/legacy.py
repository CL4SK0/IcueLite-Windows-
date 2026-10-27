"""Protocole Corsair « ancienne génération » (souris et claviers d'avant 2020), d'après ckb-next et OpenRGB.

Paquets de 64 octets précédés du report ID 0. Commandes utiles :
  07 04 02 / 07 04 01      mode logiciel / mode autonome (éclairage et réglages embarqués)
  0e 01                    infos appareil (firmware aux octets 8-9)
  07 22 n 01 [i r g b]×n   couleurs des zones d'une souris
  07 13 d0+s 00 00 x x y y DPI du palier s ; 07 13 05 00 masque des paliers actifs ; 07 13 02 00 s palier courant
  07 0a 00 00 ms           intervalle d'interrogation (1 ms = 1000 Hz)
"""

from .base import Driver, DriverError

SIZE = 64


def packet(*data):
    data = bytes(data)
    if len(data) > SIZE:
        raise ValueError("paquet trop long")
    return b"\x00" + data + bytes(SIZE - len(data))


def software_mode(on):
    return packet(0x07, 0x04, 0x02 if on else 0x01)


def mouse_colors(leds):
    """leds : [(index, (r, g, b))]."""
    body = [0x07, 0x22, len(leds), 0x01]
    for index, (r, g, b) in leds:
        body += [index, r, g, b]
    return packet(*body)


def dpi_stage(stage, dpi):
    return packet(0x07, 0x13, 0xD0 + stage, 0x00, 0x00, dpi & 0xFF, dpi >> 8, dpi & 0xFF, dpi >> 8)


def dpi_enabled(mask):
    return packet(0x07, 0x13, 0x05, 0x00, mask)


def dpi_current(stage):
    return packet(0x07, 0x13, 0x02, 0x00, stage)


def poll_interval(hz):
    return packet(0x07, 0x0A, 0x00, 0x00, max(1, 1000 // hz))


def scale(color, brightness):
    if color is None:
        return (0, 0, 0)
    return tuple(round(c * brightness / 100) for c in color)


class LegacyMouse(Driver):
    """Souris Corsair ancienne génération. Les sous-classes donnent l'index de chaque zone."""

    LEDS = {}
    zones = ()
    brightness = True
    dpi_range = (100, 18000, 50)
    dpi_stage_count = 5
    poll_rates = (125, 250, 500, 1000)

    def send(self, packet):
        # La souris répond à chaque commande par un écho (07 xx …) : on le lit pour le journal du diagnostic,
        # sans attendre longtemps s'il ne vient pas.
        self.flush()
        super().send(packet)
        if packet[1] == 0x07:
            self.receive(150)

    def ensure_software(self):
        if not self.software_mode:
            self.send(software_mode(True))
            self.software_mode = True

    def firmware(self):
        self.flush()
        self.send(packet(0x0E, 0x01))
        for _ in range(4):
            data = self.receive(300)
            if len(data) > 10 and data[1:3] == b"\x0e\x01":
                return f"{data[10]:x}.{data[9]:02x}"
        return None

    def set_colors(self, colors, brightness=100):
        self.ensure_software()
        leds = [(index, scale(colors.get(zone, (255, 255, 255)), brightness)) for zone, index in self.LEDS.items()]
        self.send(mouse_colors(leds))

    def set_dpi(self, stages, active):
        lo, hi, step = self.dpi_range
        stages = [min(hi, max(lo, round(d / step) * step)) for d in stages][:self.dpi_stage_count]
        if not stages:
            raise DriverError("aucun palier DPI")
        # le palier 0 est le mode « sniper » : nos paliers sont les numéros 1 à 5
        for i, dpi in enumerate(stages, start=1):
            self.send(dpi_stage(i, dpi))
        self.send(dpi_enabled(sum(1 << i for i in range(1, len(stages) + 1))))
        self.send(dpi_current(min(max(active, 0), len(stages) - 1) + 1))
        return stages

    def set_poll_rate(self, hz):
        if hz not in self.poll_rates:
            raise DriverError(f"fréquence {hz} Hz non prise en charge")
        self.send(poll_interval(hz))

    def release(self):
        if self.software_mode:
            self.send(software_mode(False))
            self.software_mode = False


class Ironclaw(LegacyMouse):
    # Numéros de zones des souris dans ckb-next : 1 avant, 2 arrière (logo), 4 molette
    LEDS = {"Logo": 2, "Molette": 4, "Avant": 1}
    zones = ("Logo", "Molette", "Avant")
