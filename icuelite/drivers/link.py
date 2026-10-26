"""Hub iCUE LINK (System Hub du 5000T LX), d'après FanControl.CorsairLink et OpenRGB.

Rapports de 512 octets, précédés du report ID 0 et de 00 01. Commandes :
  01 03 00 02 / 01 03 00 01   mode logiciel / mode autonome (le hub reprend sa propre courbe)
  0d 01 ee     ouvrir le point d'accès ee      05 01 01   le refermer
  08 01        lire le point ouvert            06 01 LL LL 00 00 tt tt données…   y écrire (type tt)
Points d'accès : 17 régimes (type 25 00), 18 consignes (type 07 00), 21 températures (type 10 00).
Réponse de lecture : type aux octets 4-5, nombre d'entrées à l'octet 6, puis 3 octets par voie
(statut 00 = présent, valeur sur 2 octets : tr/min, ou dixièmes de °C).
"""

import struct

from .base import Driver, DriverError

EP_SPEEDS, EP_SET_SPEED, EP_TEMPS = 0x17, 0x18, 0x21
TYPE_SPEEDS, TYPE_SET_SPEED, TYPE_TEMPS = b"\x25\x00", b"\x07\x00", b"\x10\x00"
MIN_DUTY = 20  # jamais en dessous : un ventilateur à l'arrêt ne refroidit plus rien


def frame(size, *data):
    data = bytes(data)
    if len(data) + 2 > size:
        raise ValueError("paquet trop long")
    return b"\x00\x00\x01" + data + bytes(size - 2 - len(data))


def parse_channels(data, data_type):
    """[(voie, valeur)] des voies présentes d'une réponse de lecture, ou [] si ce n'est pas le bon type."""
    data = bytes(data)
    # le type est attendu aux octets 4-5 ; on tolère un décalage d'un octet (report ID présent ou non)
    start = next((off for off in (4, 3, 5) if data[off:off + 2] == data_type and len(data) > off + 2), None)
    if start is None:
        return []
    count = data[start + 2]
    out = []
    for ch in range(count):
        pos = start + 3 + ch * 3
        if pos + 3 > len(data):
            break
        if data[pos] == 0x00:
            out.append((ch, struct.unpack_from("<H", data, pos + 1)[0]))
    return out


def speed_payload(channels, duty):
    body = bytes([len(channels)])
    for ch in channels:
        body += bytes([ch, 0x00, duty, 0x00])
    return body


class LinkHub(Driver):
    experimental = True
    fans = True
    sensors = True

    def __init__(self, transport, interface=None):
        super().__init__(transport, interface)
        self.size = max(64, (getattr(transport, "output_len", 0) or 513) - 1)
        self.duty = None
        self.fan_channels = []

    def command(self, *data):
        self.flush()
        self.send(frame(self.size, *data))
        return self.receive(400)

    def read_endpoint(self, endpoint, data_type):
        self.command(0x05, 0x01, 0x01)
        self.command(0x0D, 0x01, endpoint)
        data = self.command(0x08, 0x01)
        self.command(0x05, 0x01, 0x01)
        return parse_channels(data, data_type)

    def write_endpoint(self, endpoint, data_type, payload):
        body = data_type + payload
        self.command(0x05, 0x01, 0x01)
        self.command(0x0D, 0x01, endpoint)
        self.command(0x06, 0x01, *struct.pack("<H", len(body)), 0x00, 0x00, *body)
        self.command(0x05, 0x01, 0x01)

    def read_sensors(self):
        speeds = self.read_endpoint(EP_SPEEDS, TYPE_SPEEDS)
        temps = self.read_endpoint(EP_TEMPS, TYPE_TEMPS)
        self.fan_channels = [ch for ch, rpm in speeds]
        return {"fans": [(f"Voie {ch}", rpm) for ch, rpm in speeds],
                "temps": [(f"Sonde {ch}", value / 10) for ch, value in temps]}

    def set_fan_duty(self, percent):
        """percent : consigne fixe en %, ou None pour rendre la main au hub (sa courbe par défaut)."""
        if percent is None:
            self.duty = None
            self.release()
            return
        if not self.fan_channels:
            self.read_sensors()
        if not self.fan_channels:
            raise DriverError("aucun ventilateur détecté sur le hub")
        if not self.software_mode:
            self.command(0x01, 0x03, 0x00, 0x02)
            self.software_mode = True
        self.duty = max(MIN_DUTY, min(100, int(percent)))
        self.write_endpoint(EP_SET_SPEED, TYPE_SET_SPEED, speed_payload(self.fan_channels, self.duty))

    def keepalive(self):
        # en mode logiciel, le hub attend des nouvelles régulières, sinon il repasse en mode autonome
        if self.software_mode and self.duty is not None:
            self.write_endpoint(EP_SET_SPEED, TYPE_SET_SPEED, speed_payload(self.fan_channels, self.duty))

    def release(self):
        if self.software_mode:
            self.command(0x01, 0x03, 0x00, 0x01)
            self.software_mode = False
