"""Pilotes des appareils Corsair : un par famille de protocole."""

from .base import DriverError, pick_interface
from .bragi import K100, Vanguard
from .hydro import Hydro
from .legacy import Ironclaw
from .link import LinkHub

# clé du catalogue -> (classe du pilote, usage pages préférées, longueur minimale des rapports de sortie)
DRIVERS = {
    "ironclaw": (Ironclaw, (0xFFC2,), 64),
    "k100": (K100, (0xFF42,), 64),
    "vanguard": (Vanguard, (0xFF42,), 64),
    "link": (LinkHub, (0xFF42,), 64),
    "h150i": (Hydro, (0xFF00,), 64),
}


def has_driver(key):
    return key in DRIVERS


def open_driver(detected):
    """Ouvre le pilote d'un appareil détecté (devices.Detected). Lève DriverError si impossible."""
    entry = DRIVERS.get(detected.spec.key)
    if entry is None:
        raise DriverError("pas encore de pilote pour cet appareil")
    cls, pages, min_output = entry
    info = pick_interface(detected.interfaces, pages, min_output)
    from .. import winhid
    try:
        transport = winhid.Transport(info["path"])
    except OSError as exc:
        raise DriverError(f"ouverture impossible ({exc}) : iCUE est-il encore lancé ?") from exc

    def reopen():
        # après une reconnexion USB, le chemin Windows de l'interface peut changer : on la recherche
        from ..devices import enumerate_raw
        same = [i for i in enumerate_raw() if i.get("product_id") == info.get("product_id")]
        fresh = pick_interface(same, pages, min_output) if same else info
        return winhid.Transport(fresh["path"]), fresh

    driver = cls(transport, info)
    driver.reopen = reopen
    return driver


__all__ = ["DRIVERS", "DriverError", "has_driver", "open_driver"]
