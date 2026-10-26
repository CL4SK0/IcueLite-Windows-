"""IcueLite en ligne de commande. Sans argument, ouvre l'interface graphique."""

import argparse
import sys

from . import __version__, diag
from .devices import CATALOG, MOTHERBOARD, NOTHING, detect


def cmd_list(args):
    found, unknown = detect()
    for spec in CATALOG:
        state = {MOTHERBOARD: "via la carte mère", NOTHING: "rien à piloter"}.get(
            spec.support, "branché" if spec.key in found else "non détecté")
        print(f"- {spec.name:<40} {state}")
    for info in unknown:
        print(f"- inconnu {info['product_id']:04x} {info['product_string']}")


def cmd_diag(args):
    path = diag.write()
    print(path.read_text(encoding="utf-8"))
    print(f"Enregistré dans {path}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="icuelite", description="iCUE allégé pour Windows")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--after-update", action="store_true", help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("list", help="liste les appareils reconnus")
    sub.add_parser("diag", help="diagnostic complet (à m'envoyer si ça coince)")
    args = parser.parse_args(argv)
    if not args.cmd:
        from .app import run
        return run(after_update=args.after_update)
    {"list": cmd_list, "diag": cmd_diag}[args.cmd](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
