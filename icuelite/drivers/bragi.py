"""Protocole Corsair récent (« Bragi », claviers depuis le K100), d'après OpenRGB (CorsairPeripheralV2).

Chaque paquet commence par 08 (appareil filaire) suivi d'une commande :
  08 01 pp 00 vv…   écrire la propriété pp      08 02 pp 00   la lire (réponse : 00 02 statut valeur…)
  08 0d hh rr       ouvrir la ressource rr sur la poignée hh   08 05 01 hh   la refermer
  08 06 hh LLLLLLLL données…   écrire (longueur sur 4 octets)   08 07 hh données…   suite de l'écriture
Propriétés : 01 fréquence d'interrogation, 02 luminosité (0-1000), 03 mode (1 autonome, 2 logiciel),
13 firmware. Ressource 01 : couleurs des LED, rangées R…R G…G B…B.
"""

import struct

from .base import Driver, DriverError

WIRED = 0x08
PROP_POLL, PROP_BRIGHTNESS, PROP_MODE, PROP_FIRMWARE = 0x01, 0x02, 0x03, 0x13
MODE_HARDWARE, MODE_SOFTWARE = 0x01, 0x02
RES_LIGHTING = 0x01
# codes de fréquence d'interrogation
POLL_CODES = {125: 0x01, 250: 0x02, 500: 0x03, 1000: 0x04, 2000: 0x05, 4000: 0x06, 8000: 0x07}


def frame(size, *data):
    """Paquet complet : report ID 0 puis les données, complété à `size` octets de données."""
    data = bytes(data)
    if len(data) > size:
        raise ValueError("paquet trop long")
    return b"\x00" + data + bytes(size - len(data))


def set_property(size, prop, value, width=2):
    return frame(size, WIRED, 0x01, prop, 0x00, *value.to_bytes(width, "little"))


def get_property(size, prop):
    return frame(size, WIRED, 0x02, prop, 0x00)


def planar(colors):
    """[(r, g, b)] -> R…R G…G B…B."""
    return bytes(c[0] for c in colors) + bytes(c[1] for c in colors) + bytes(c[2] for c in colors)


def write_resource(size, handle, payload):
    """Paquets d'écriture d'une ressource ouverte : un premier avec la longueur, puis des suites."""
    first_room = size - 7
    packets = [frame(size, WIRED, 0x06, handle, *struct.pack("<I", len(payload)), *payload[:first_room])]
    rest = payload[first_room:]
    room = size - 3
    while rest:
        packets.append(frame(size, WIRED, 0x07, handle, *rest[:room]))
        rest = rest[room:]
    return packets


class BragiKeyboard(Driver):
    LED_COUNT = 0          # nombre de LED du tableau de couleurs de l'appareil
    zones = ("Touches",)
    brightness = True
    poll_rates = (125, 250, 500, 1000)

    def __init__(self, transport, interface=None):
        super().__init__(transport, interface)
        self.size = max(64, (getattr(transport, "output_len", 0) or 65) - 1)
        self.lighting_open = False

    def command(self, packet, wait=True):
        """Envoie un paquet ; si wait, renvoie sa réponse (00 cmd statut valeur…), notée dans le journal.

        Les réponses aux paquets envoyés sans attendre arrivent quand même : on saute celles dont l'octet de
        commande n'est pas le bon, pour ne pas prendre la réponse d'un paquet précédent."""
        self.send(packet)
        if not wait:
            return b""
        for _ in range(4):
            data = self.receive(300)
            if not data:
                return b""
            # Windows renvoie le report ID en tête : on le retire
            data = data[1:] if len(data) > self.size else data
            if len(data) > 1 and data[1] == packet[2]:
                return data
        return b""

    def firmware(self):
        data = self.command(get_property(self.size, PROP_FIRMWARE))
        if len(data) >= 6 and data[1] == 0x02 and data[2] == 0x00:
            return f"{data[3]}.{data[4]}.{data[5]}"
        return None

    def ensure_software(self):
        if not self.software_mode:
            self.command(set_property(self.size, PROP_MODE, MODE_SOFTWARE))
            self.software_mode = True
        if not self.lighting_open:
            self.command(frame(self.size, WIRED, 0x05, 0x01, 0x00), wait=False)  # poignée restée ouverte ?
            self.command(frame(self.size, WIRED, 0x0D, 0x00, RES_LIGHTING))
            self.lighting_open = True

    def set_colors(self, colors, brightness=100):
        if not self.LED_COUNT:
            raise DriverError("nombre de LED inconnu pour cet appareil")
        color = colors.get("Touches", (255, 255, 255)) or (0, 0, 0)
        self.ensure_software()
        self.command(set_property(self.size, PROP_BRIGHTNESS, round(brightness * 10)))
        for packet in write_resource(self.size, 0x00, planar([color] * self.LED_COUNT)):
            self.command(packet, wait=False)

    def set_poll_rate(self, hz):
        if hz not in self.poll_rates:
            raise DriverError(f"fréquence {hz} Hz non prise en charge")
        # le clavier se reconnecte aussitôt à la nouvelle fréquence : l'envoi suivant le rouvrira
        self.command(set_property(self.size, PROP_POLL, POLL_CODES[hz], width=1))

    def after_reconnect(self):
        self.lighting_open = False

    def release(self):
        if self.lighting_open:
            self.command(frame(self.size, WIRED, 0x05, 0x01, 0x00), wait=False)
            self.lighting_open = False
        if self.software_mode:
            self.command(set_property(self.size, PROP_MODE, MODE_HARDWARE), wait=False)
            self.software_mode = False


class K100(BragiKeyboard):
    experimental = True
    LED_COUNT = 193  # touches + LightEdge + molette et logo, comme dans la table d'OpenRGB
    poll_rates = (125, 250, 500, 1000, 2000, 4000, 8000)


class Vanguard(BragiKeyboard):
    # Clavier sorti en 2025, pas encore dans OpenRGB : même famille de protocole supposée, à vérifier
    experimental = True
    LED_COUNT = 128
    poll_rates = (125, 250, 500, 1000, 2000, 4000, 8000)
