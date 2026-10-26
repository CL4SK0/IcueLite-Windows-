"""Diagnostic en lecture seule : ce que Windows voit du matériel Corsair. Résultat dans icuelite-diag.txt.

Liste les interfaces HID Corsair (VID 1B1C), les autres périphériques Corsair (l'alim AXi peut passer
par un pont série), la carte mère (pour le Nautilus RS ARGB branché dessus), les références des barrettes
(CMH = RGB, CMK = sans éclairage) et les logiciels qui pourraient parler aux mêmes appareils.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

from . import __version__
from .devices import enumerate_raw, match

NO_WINDOW = 0x08000000


def powershell(command):
    if sys.platform != "win32":
        return []
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", command + " | ConvertTo-Json -Depth 3"],
                             capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW).stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"ERREUR {exc}"
    if not out:
        return []
    try:
        data = json.loads(out)
    except ValueError:
        return out
    return data if isinstance(data, list) else [data]


def _section(lines, title, rows, fields):
    lines.append(title)
    if isinstance(rows, str):
        lines.append("  " + rows)
    elif not rows:
        lines.append("  (rien)")
    for row in rows if isinstance(rows, list) else []:
        lines.append("  " + " | ".join(f"{k}={row.get(k)}" for k in fields))
    lines.append("")


def report():
    lines = [f"IcueLite {__version__} - diagnostic {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"Python {sys.version.split()[0]} sur {sys.platform}", "", "Interfaces HID Corsair (VID 1b1c) :"]
    raw = sorted(enumerate_raw(), key=lambda d: (d["product_id"], d["interface_number"], d["usage_page"]))
    for info in raw:
        spec = match(info)
        lines.append(f"  {info['product_id']:04x} if={info['interface_number']} page={info['usage_page']:04x} "
                     f"usage={info['usage']:04x} out/feat={info.get('output_report_length')}/"
                     f"{info.get('feature_report_length')} {info['product_string']}"
                     f"  -> {spec.name if spec else 'inconnu'}")
    if not raw:
        lines.append("  (aucune)")
    lines.append("")
    _section(lines, "Périphériques Corsair (Gestionnaire de périphériques) :",
             powershell("Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match 'VID_1B1C' "
                        "-or $_.FriendlyName -match 'Corsair|CP210|Silicon Labs' } | "
                        "Select-Object Class,FriendlyName,InstanceId,Status"),
             ("Class", "FriendlyName", "InstanceId", "Status"))
    _section(lines, "Carte mère :", powershell("Get-CimInstance Win32_BaseBoard | Select-Object Manufacturer,Product,Version"),
             ("Manufacturer", "Product", "Version"))
    _section(lines, "BIOS :", powershell("Get-CimInstance Win32_BIOS | Select-Object Manufacturer,SMBIOSBIOSVersion"),
             ("Manufacturer", "SMBIOSBIOSVersion"))
    _section(lines, "Barrettes mémoire :",
             powershell("Get-CimInstance Win32_PhysicalMemory | "
                        "Select-Object BankLabel,Manufacturer,PartNumber,Capacity,ConfiguredClockSpeed"),
             ("BankLabel", "Manufacturer", "PartNumber", "Capacity", "ConfiguredClockSpeed"))
    _section(lines, "Logiciels de contrôle en cours d'exécution :",
             powershell("Get-Process | Where-Object { $_.ProcessName -match "
                        "'iCUE|Corsair|OpenRGB|SignalRgb|FanControl|LightingService|ArmouryCrate|MysticLight|RGBFusion' } "
                        "| Select-Object ProcessName,Path"),
             ("ProcessName", "Path"))
    _section(lines, "Services Corsair :",
             powershell("Get-Service | Where-Object { $_.Name -match 'Corsair|iCUE' -or $_.DisplayName -match 'Corsair' } "
                        "| Select-Object Name,DisplayName,Status"),
             ("Name", "DisplayName", "Status"))
    return "\n".join(lines)


def write(folder=None):
    """Écrit le rapport et renvoie le chemin du fichier."""
    out = Path(folder or Path.cwd()) / "icuelite-diag.txt"
    out.write_text(report(), encoding="utf-8")
    return out
