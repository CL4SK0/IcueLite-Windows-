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
from .devices import VIRTUAL_PIDS, enumerate_raw, match

NO_WINDOW = 0x08000000


def icue_running():
    """True si iCUE est lancé : il reprend alors la main sur les appareils et écrase les réglages d'IcueLite."""
    if sys.platform != "win32":
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq iCUE.exe", "/NH"], capture_output=True, text=True,
                             timeout=15, creationflags=NO_WINDOW).stdout
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "icue.exe" in out.lower()


def close_icue():
    """Ferme iCUE (et son hôte de modules, qui parle aussi aux appareils). Renvoie True si quelque chose a été fermé.
    Les services Corsair restent : les arrêter demande les droits d'administrateur, et ils gênent peu."""
    if sys.platform != "win32":
        return False
    closed = False
    for image in ("iCUE.exe", "iCUEDevicePluginHost.exe"):
        try:
            done = subprocess.run(["taskkill", "/IM", image, "/F"], capture_output=True, text=True, timeout=15,
                                  creationflags=NO_WINDOW)
            closed = closed or done.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    return closed


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


def report(extra=None):
    lines = [f"IcueLite {__version__} - diagnostic {time.strftime('%Y-%m-%d %H:%M:%S')}",
             f"Python {sys.version.split()[0]} sur {sys.platform}", "", "Interfaces HID Corsair (VID 1b1c) :"]
    raw = sorted(enumerate_raw(), key=lambda d: (d["product_id"], d["interface_number"], d["usage_page"]))
    for info in raw:
        spec = match(info)
        lines.append(f"  {info['product_id']:04x} if={info['interface_number']} page={info['usage_page']:04x} "
                     f"usage={info['usage']:04x} out/feat={info.get('output_report_length')}/"
                     f"{info.get('feature_report_length')} {info['product_string']}"
                     f"  -> {spec.name if spec else VIRTUAL_PIDS.get(info.get('product_id'), 'inconnu')}")
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
    if extra:
        lines += ["Échanges récents avec les appareils :"] + list(extra) + [""]
    return "\n".join(lines)


# Envoi du rapport par courriel à Erwan, sans mot de passe dans l'exe : d'abord son script Google Apps Script
# (tools/diag_mail.gs), puis FormSubmit en secours (alias fourni par FormSubmit à la place de l'adresse).
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxbkr527gGpGfJ-F4mtVaElYIt0xvkdddR74EcoAEKP0pumlIHG3UV4faVblF6BGv8/exec"
FORMSUBMIT_URL = "https://formsubmit.co/ajax/0549c5a5576e06fbf2ae9e54ac5eb542"
PAGE = "https://github.com/CL4SK0/IcueLite-Windows-"


def _post(url, payload, headers):
    import urllib.request
    from .updater import urlopen
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    with urlopen(req, timeout=90) as resp:
        raw = resp.read()
    try:
        answer = json.loads(raw or b"{}")
    except ValueError:
        raise OSError("réponse inattendue du service d'envoi") from None
    if str(answer.get("success")).lower() != "true":
        raise OSError(answer.get("message") or "envoi refusé")


def send(text, version):
    """Envoie le rapport par courriel. Lève OSError (avec la raison) si aucun service ne l'a accepté."""
    import socket
    payload = {"_subject": f"IcueLite {version} - diagnostic de {socket.gethostname()}",
               "_template": "box", "_captcha": "false", "source": "icuelite",
               "appareil": socket.gethostname(), "version": version, "diagnostic": text}
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               "User-Agent": f"IcueLite/{version}"}
    from .updater import describe
    try:
        return _post(SCRIPT_URL, payload, headers)
    except Exception as exc:
        script_error = describe(exc, "le script Google")
    try:
        # FormSubmit n'accepte que des envois qui semblent venir d'une page web
        _post(FORMSUBMIT_URL, payload, dict(headers, Origin="https://github.com", Referer=PAGE))
    except Exception as exc:
        if isinstance(exc, TimeoutError) or "timed out" in str(getattr(exc, "reason", exc)):
            # FormSubmit envoie souvent le courriel sans répondre à temps
            raise OSError(f"{script_error} ; FormSubmit n'a pas confirmé, le courriel arrive peut-être quand même") from None
        raise OSError(f"{script_error} ; {describe(exc, 'FormSubmit')}") from None


def write(folder=None, extra=None):
    """Écrit le rapport (avec, si fourni, le journal des pilotes) et renvoie le chemin du fichier."""
    out = Path(folder or Path.cwd()) / "icuelite-diag.txt"
    out.write_text(report(extra), encoding="utf-8")
    return out
