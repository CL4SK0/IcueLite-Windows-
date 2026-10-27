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
    usb_pids: tuple = ()  # appareils vus par Windows hors pilote HID (pilote constructeur)
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
    Spec("h150i", "iCUE H150i RGB Elite", "cooler", "Watercooling 360 mm", "Câble USB interne de la pompe",
         pids=(0x0C37, 0x0C41), keywords=("H150I",),
         features=("Vitesse des ventilateurs", "Mode de la pompe", "Température du liquide", "Éclairage de la pompe")),
    Spec("ax1600i", "AX1600i", "psu", "CP-9020087-EU", "Câble Corsair Link (USB interne, pilote USBXpress de Corsair)",
         usb_pids=(0x1C11,), keywords=("AX1600I",),
         features=("Puissance, tensions, courants", "Températures et rendement", "Mode ventilateur", "OCP mono/multi-rail")),
    Spec("nautilus", "Nautilus 360 RS ARGB", "cooler", "Noir",
         "Prises PWM et ARGB 5 V de la carte mère", support=MOTHERBOARD,
         features=("Éclairage via le contrôleur RGB de la carte mère",),
         note="Pas d'USB : vitesses de la pompe et des ventilateurs dans le BIOS."),
    Spec("vengeance", "Vengeance DDR5", "memory", "CMK… (sans éclairage) ou CMH… (RGB)",
         "Bus SMBus de la carte mère", support=NOTHING,
         note="Version sans éclairage : rien à régler."),
]

BY_KEY = {spec.key: spec for spec in CATALOG}


@dataclass
class Detected:
    spec: Spec
    interfaces: list = field(default_factory=list)
    details: list = field(default_factory=list)  # [(libellé, valeur)] à afficher sur la fiche
    note: str = ""

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


# Interfaces Corsair qui ne sont pas des appareils : le clavier/souris virtuel que crée le pilote « Corsair Bus »
# d'iCUE (pas de nom, pas de numéro d'interface)
VIRTUAL_PIDS = {0x1BF0: "périphérique virtuel d'iCUE (Corsair Bus), à ignorer"}


def match(info):
    """L'appareil du catalogue qui correspond à une interface HID, ou None."""
    name = (info.get("product_string") or "").upper()
    for spec in CATALOG:
        if spec.support == USB and (info.get("product_id") in spec.pids or any(k in name for k in spec.keywords)):
            return spec
    return None


def usb_raw():
    """[(PID, identifiant d'instance)] des appareils USB Corsair, HID ou non (liste vide hors Windows)."""
    hid = backend()
    if hid is None:
        return []
    try:
        return hid.usb_devices(CORSAIR)
    except OSError:
        return []


def memory_detected(modules):
    """Detected des barrettes Corsair d'après les infos de Windows (memory.modules()), ou None."""
    corsair = [m for m in modules if m["part"].upper().startswith("CM")]
    if not corsair:
        return None
    det = Detected(BY_KEY["vengeance"])
    total = sum(m["capacity_gb"] for m in corsair)
    first = corsair[0]
    rgb = first["part"].upper().startswith(("CMH", "CMG", "CMN"))
    det.details = [("Barrettes", f"{len(corsair)} × {first['capacity_gb']} Go ({total} Go), {first['part']}"),
                   ("Éclairage", "RGB" if rgb else "aucun (rien à régler)")]
    if first.get("rated") and first.get("speed"):
        det.details.append(("Vitesse", f"{first['speed']} MT/s (prévue pour {first['rated']} MT/s)"))
        if first["speed"] < first["rated"]:
            det.note = (f"La mémoire tourne à {first['speed']} MT/s au lieu de {first['rated']} : active le profil "
                        "EXPO (ou XMP) dans le BIOS pour en profiter.")
    return det


def detect(raw=None, usb=None, modules=None):
    """{clé du catalogue: Detected} pour chaque appareil branché, + liste des interfaces HID inconnues.

    raw : interfaces HID ; usb : appareils USB hors HID ; modules : barrettes mémoire (None = pas encore lues)."""
    found, unknown = {}, []
    for info in enumerate_raw() if raw is None else raw:
        spec = match(info)
        if spec is None:
            if info.get("product_id") not in VIRTUAL_PIDS:
                unknown.append(info)
            continue
        found.setdefault(spec.key, Detected(spec)).interfaces.append(info)
    for pid, instance in usb_raw() if usb is None else usb:
        for spec in CATALOG:
            if pid in spec.usb_pids and spec.key not in found:
                found[spec.key] = Detected(spec, details=[("Identifiant USB", f"1B1C:{pid:04X} ({instance})")])
    mem = memory_detected(modules or [])
    if mem:
        found["vengeance"] = mem
    return found, unknown
