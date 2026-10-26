"""Catalogue des appareils Corsair d'Erwan et détection de ceux qui sont branchés.

Les identifiants USB (PID) viennent des projets libres (OpenRGB, ckb-next, liquidctl…) et restent à
confirmer par le diagnostic : en plus du PID, on reconnaît chaque appareil au nom qu'il annonce
(« VANGUARD », « IRONCLAW »…), ce qui couvre les variantes de PID qu'on ne connaît pas encore.
"""

import sys
from dataclasses import dataclass, field

CORSAIR = 0x1B1C

# Niveaux de prise en charge, du plus complet au plus limité
USB = "usb"             # appareil USB Corsair, pilotable par IcueLite
MOTHERBOARD = "board"   # branché sur la carte mère : seulement à travers elle
NOTHING = "none"        # rien à piloter


@dataclass(frozen=True)
class Spec:
    key: str
    name: str
    kind: str            # keyboard, mouse, headset, case, psu, cooler, memory
    ref: str             # référence Corsair
    link: str            # comment l'appareil est relié au PC
    support: str = USB
    pids: tuple = ()
    keywords: tuple = ()
    features: tuple = ()
    note: str = ""


CATALOG = [
    Spec("vanguard", "Vanguard Pro 96 Hall Effect", "keyboard", "CH-91E911G-FR", "USB filaire",
         keywords=("VANGUARD",),
         features=("Éclairage par touche", "Point d'actionnement et Rapid Trigger", "Écran 1,9\"",
                   "Molette", "Touches G et macros", "Fréquence d'interrogation"),
         note="Modèle récent : protocole à capturer depuis iCUE."),
    Spec("k100", "K100 RGB OPX", "keyboard", "CH-912A01A-NA-RF", "USB filaire",
         pids=(0x1B7C, 0x1BC5), keywords=("K100",),
         features=("Éclairage par touche", "Molette iCUE", "Touches G et macros", "Fréquence d'interrogation")),
    Spec("ironclaw", "Ironclaw RGB", "mouse", "CH-9307011-EU", "USB filaire",
         pids=(0x1B5D,), keywords=("IRONCLAW",),
         features=("DPI et paliers", "Fréquence d'interrogation", "Éclairage 3 zones", "Boutons")),
    Spec("virtuoso", "Virtuoso RGB Wireless XT", "headset", "CA-9011188-EU",
         "Dongle Slipstream ou câble USB (rien en Bluetooth ni en jack)",
         keywords=("VIRTUOSO",),
         features=("Batterie", "Retour micro", "Égaliseur", "Éclairage", "Veille automatique")),
    Spec("link", "iCUE LINK 5000T LX RGB", "case", "CC-9011298-WW",
         "iCUE LINK System Hub (USB interne) : 3 ventilateurs LX120 RGB + bandes Aurora",
         pids=(0x0C3F,), keywords=("LINK SYSTEM HUB", "ICUE LINK"),
         features=("Vitesse des ventilateurs et courbes", "Éclairage ventilateurs et bandes", "Sondes")),
    Spec("ax1600i", "AX1600i", "psu", "CP-9020087-EU", "Corsair Link (USB interne)",
         pids=(0x1C11,), keywords=("AX1600I", "AXI"),
         features=("Puissance, tensions, courants", "Températures et rendement", "Mode ventilateur", "OCP mono/multi-rail")),
    Spec("nautilus", "Nautilus 360 RS ARGB", "cooler", "Noir",
         "Prises PWM et ARGB 5 V de la carte mère", support=MOTHERBOARD,
         features=("Éclairage via le contrôleur RGB de la carte mère",),
         note="Pas d'USB : vitesses de la pompe et des ventilateurs dans le BIOS."),
    Spec("vengeance", "Vengeance DDR5 64 Go", "memory", "CMK64GX5M2B6000Z30 (à confirmer)",
         "Bus SMBus de la carte mère (2 × 32 Go, 6000 MT/s)", support=NOTHING,
         note="Version sans éclairage (à confirmer par le diagnostic) : rien à régler."),
]

BY_KEY = {spec.key: spec for spec in CATALOG}


@dataclass
class Detected:
    spec: Spec
    interfaces: list = field(default_factory=list)

    @property
    def pid(self):
        return self.interfaces[0]["product_id"] if self.interfaces else None


def backend():
    if sys.platform == "win32":
        from . import winhid
        return winhid
    return None


def enumerate_raw():
    """Toutes les interfaces HID Corsair (liste vide hors Windows)."""
    hid = backend()
    if hid is None:
        return []
    try:
        return hid.enumerate(CORSAIR)
    except OSError:
        return []


def match(info):
    """L'appareil du catalogue qui correspond à une interface HID, ou None."""
    name = (info.get("product_string") or "").upper()
    for spec in CATALOG:
        if spec.support == USB and (info.get("product_id") in spec.pids or any(k in name for k in spec.keywords)):
            return spec
    return None


def detect(raw=None):
    """{clé du catalogue: Detected} pour chaque appareil branché, + liste des interfaces inconnues."""
    found, unknown = {}, []
    for info in enumerate_raw() if raw is None else raw:
        spec = match(info)
        if spec is None:
            unknown.append(info)
            continue
        found.setdefault(spec.key, Detected(spec)).interfaces.append(info)
    return found, unknown
