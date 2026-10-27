"""Watercoolings Corsair Hydro « Platinum / Pro XT / Elite RGB » (dont l'iCUE H150i RGB Elite), d'après liquidctl.

Paquets de 64 octets (précédés du report ID 0) : 3f, numéro de séquence (5 bits) << 3 | fonction,
commande, données, puis un CRC-8 (polynôme 07) sur tout ce qui suit le 3f. Chaque paquet reçoit une
réponse de 64 octets, elle aussi terminée par un CRC.
  fonction 000 + commande ff  état : firmware (octets 2-3), liquide (8 + 7/255 °C), ventilateurs 1 et 2
                              (tr/min aux octets 15 et 22), pompe (octet 29) ; fonction 011 = 3e ventilateur
  fonction 000 + commande 14  consignes : mode de la pompe, mode et vitesse de chaque ventilateur
  sans fonction, commande 100 / 101 : couleurs des LED (20 par paquet, ordre B, V, R)
"""

import itertools

from .base import Driver, DriverError

SIZE = 64
PREFIX = 0x3F
FEATURE_COOLING, FEATURE_COOLING2 = 0b000, 0b011
CMD_STATUS, CMD_SET_COOLING = 0xFF, 0x14
CMD_LIGHTING = (0b100, 0b101)
LED_COUNT = 24

# consignes : offsets dans les données (après l'octet de commande)
FAN_MODE = (0x0B - 3, 0x11 - 3)
FAN_DUTY = (0x0B - 3 + 5, 0x11 - 3 + 5)
FAN_PROFILE = (0x1E - 3, 0x2C - 3)
PUMP_MODE = 0x17 - 3
PROFILE_LENGTH = 0x1D - 3
MODE_PROFILE, MODE_FIXED = 0x00, 0x02
MIN_DUTY = 25
# courbe « automatique » (température du liquide en °C, vitesse en %), proche de celle d'origine
AUTO_CURVE = [(20, 30), (25, 35), (30, 45), (33, 60), (36, 80), (40, 100), (60, 100)]
PUMP_MODES = {"Silencieux": 0, "Équilibré": 1, "Performance": 2}


def crc8(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def packet(seq, feature, command, data=b""):
    buf = bytearray(SIZE + 1)
    buf[1] = PREFIX
    buf[2] = (seq & 0x1F) << 3
    if feature is not None:
        buf[2] |= feature
        buf[3] = command
        start = 4
    else:
        buf[2] |= command
        start = 3
    if len(data) > SIZE - start:
        raise ValueError("données trop longues")
    buf[start:start + len(data)] = data
    buf[-1] = crc8(buf[2:-1])
    return bytes(buf)


def byte_of(percent):
    return round(max(0, min(100, percent)) * 255 / 100)


def cooling_data(pump_mode, fans):
    """fans : [(mode, vitesse en %)] pour les emplacements 1 et 2 du paquet."""
    data = bytearray(SIZE - 4 - 1)
    data[0:2] = b"\x00\x03"
    data[PUMP_MODE] = pump_mode
    data[PROFILE_LENGTH] = len(AUTO_CURVE)
    for slot, (mode, duty) in enumerate(fans[:2]):
        data[FAN_MODE[slot]] = mode
        data[FAN_DUTY[slot]] = byte_of(duty or 0)
        for i, (temp, pct) in enumerate(AUTO_CURVE):
            data[FAN_PROFILE[slot] + 2 * i] = temp
            data[FAN_PROFILE[slot] + 2 * i + 1] = byte_of(pct)
    return bytes(data)


def parse_status(reply):
    """Réponse d'état (sans report ID) -> dict, ou None si ce n'en est pas une.

    Le CRC des réponses ne colle pas toujours (liquidctl se contente aussi d'un avertissement, et l'H150i
    Elite du testeur répond avec un CRC différent) : on vérifie seulement l'octet de tête."""
    reply = bytes(reply)
    if len(reply) < 31 or reply[0] != 0xFF:
        return None
    return {"firmware": f"{reply[2] >> 4}.{reply[2] & 0x0F}.{reply[3]}",
            "liquid": reply[8] + reply[7] / 255,
            "fans": [int.from_bytes(reply[15:17], "little"), int.from_bytes(reply[22:24], "little")],
            "pump": int.from_bytes(reply[29:31], "little")}


class Hydro(Driver):
    experimental = True
    zones = ("Pompe",)
    brightness = True
    fans = True
    sensors = True
    fan_count = 3
    pump_modes = tuple(PUMP_MODES)
    min_duty = MIN_DUTY

    def __init__(self, transport, interface=None):
        super().__init__(transport, interface)
        self.sequence = itertools.cycle(range(1, 32))
        self.duty = None          # None = courbe automatique
        self.pump = PUMP_MODES["Équilibré"]

    def exchange(self, feature, command, data=b""):
        self.flush()
        self.send(packet(next(self.sequence), feature, command, data))
        reply = self.receive(500)
        # Windows renvoie le report ID en tête : on le retire
        return reply[1:] if len(reply) == SIZE + 1 else reply

    def status(self, feature=FEATURE_COOLING):
        st = parse_status(self.exchange(feature, CMD_STATUS))
        if st is None:
            raise DriverError("réponse illisible : iCUE tourne-t-il encore ?")
        return st

    def firmware(self):
        return self.status()["firmware"]

    def read_sensors(self):
        st = self.status()
        fans = st["fans"]
        if self.fan_count > 2:
            fans = fans + self.status(FEATURE_COOLING2)["fans"][:1]
        return {"fans": [(f"Ventilateur {i + 1}", rpm) for i, rpm in enumerate(fans[:self.fan_count])]
                + [("Pompe", st["pump"])],
                "temps": [("Liquide", st["liquid"])]}

    def send_cooling(self):
        fan = (MODE_PROFILE, 0) if self.duty is None else (MODE_FIXED, self.duty)
        self.exchange(FEATURE_COOLING, CMD_SET_COOLING, cooling_data(self.pump, [fan, fan]))
        if self.fan_count > 2:
            self.exchange(FEATURE_COOLING2, CMD_SET_COOLING, cooling_data(self.pump, [fan, fan]))

    def set_fan_duty(self, percent):
        """percent : vitesse fixe en %, ou None pour la courbe automatique selon la température du liquide."""
        self.duty = None if percent is None else max(self.min_duty, min(100, int(percent)))
        self.send_cooling()

    def set_pump_mode(self, name):
        if name not in PUMP_MODES:
            raise DriverError(f"mode de pompe inconnu : {name}")
        self.pump = PUMP_MODES[name]
        self.send_cooling()

    def set_colors(self, colors, brightness=100):
        color = colors.get("Pompe", (255, 255, 255)) or (0, 0, 0)
        r, g, b = (round(c * brightness / 100) for c in color)
        leds = bytes([b, g, r]) * LED_COUNT
        self.exchange(None, CMD_LIGHTING[0], leds[:60])
        self.exchange(None, CMD_LIGHTING[1], leds[60:])

    def release(self):
        # Pas de mode autonome à rétablir : on laisse la courbe automatique en partant
        if self.duty is not None:
            self.duty = None
            self.send_cooling()
