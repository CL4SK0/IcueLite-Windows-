"""Mesures du PC pour la page Surveillance, sans pilote ni droits d'administrateur :
  - processeur, mémoire, disques, réseau et batterie par psutil ;
  - cartes graphiques NVIDIA par nvidia-smi (installé avec le pilote NVIDIA) ;
  - températures du processeur, de la carte mère, des disques et des cartes AMD/Intel par LibreHardwareMonitor,
    s'il est lancé avec son « serveur web » (Options > Remote Web Server > Run), car Windows ne donne pas
    ces températures sans pilote.
"""

import json
import shutil
import subprocess
import sys
import time
import urllib.request

NO_WINDOW = 0x08000000
LHM_URL = "http://localhost:8085/data.json"
NVIDIA_FIELDS = "name,temperature.gpu,utilization.gpu,power.draw,fan.speed,memory.used,clocks.gr"

try:
    import psutil
except ImportError:  # paquet absent en mode script : on se passe de ces mesures
    psutil = None


class PcMonitor:
    def __init__(self):
        self.last_io = None       # (instant, octets disque lus, écrits, réseau reçus, envoyés)
        self.nvidia = shutil.which("nvidia-smi") if sys.platform == "win32" else None
        self.lhm_retry = 0.0      # LibreHardwareMonitor : prochain essai s'il ne répondait pas
        if psutil:
            psutil.cpu_percent(None)  # le premier appel sert de point de départ

    def read(self):
        values = []
        for source in (self._system, self._nvidia, self._lhm):
            try:
                values += source()
            except Exception:  # une source qui manque ou change de format ne doit pas bloquer les autres
                pass
        return {"values": values}

    def _system(self):
        if psutil is None:
            return []
        out = [("Processeur (charge)", psutil.cpu_percent(None), "%")]
        freq = psutil.cpu_freq()
        if freq and freq.current:
            out.append(("Processeur (fréquence)", freq.current, "MHz"))
        mem = psutil.virtual_memory()
        out += [("Mémoire (utilisée)", mem.percent, "%"), ("Mémoire (occupée)", mem.used / 2 ** 30, "Go")]
        for part in psutil.disk_partitions(all=False):
            if "fixed" in part.opts or (sys.platform != "win32" and part.mountpoint == "/"):
                out.append((f"Disque {part.mountpoint.rstrip(chr(92))} (rempli)",
                            psutil.disk_usage(part.mountpoint).percent, "%"))
        now = time.monotonic()
        disk, net = psutil.disk_io_counters(), psutil.net_io_counters()
        current = (now, disk.read_bytes if disk else 0, disk.write_bytes if disk else 0, net.bytes_recv, net.bytes_sent)
        if self.last_io:
            dt = max(0.1, now - self.last_io[0])
            rates = [(b - a) / dt / 2 ** 20 for a, b in zip(self.last_io[1:], current[1:])]
            out += [("Disques (lecture)", rates[0], "Mo/s"), ("Disques (écriture)", rates[1], "Mo/s"),
                    ("Réseau (réception)", rates[2], "Mo/s"), ("Réseau (envoi)", rates[3], "Mo/s")]
        self.last_io = current
        battery = psutil.sensors_battery()
        if battery:
            out.append(("Batterie", battery.percent, "%"))
        return out

    def _nvidia(self):
        if not self.nvidia:
            return []
        text = subprocess.run([self.nvidia, f"--query-gpu={NVIDIA_FIELDS}", "--format=csv,noheader,nounits"],
                              capture_output=True, text=True, timeout=5, creationflags=NO_WINDOW).stdout
        out = []
        for line in text.strip().splitlines():
            name, temp, load, power, fan, used, clock = [f.strip() for f in line.split(",")]
            short = name.replace("NVIDIA ", "").replace("GeForce ", "")
            for label, value, unit in (("température", temp, "°C"), ("charge", load, "%"), ("consommation", power, "W"),
                                       ("ventilateur", fan, "%"), ("mémoire vidéo", used, "Mo"),
                                       ("fréquence", clock, "MHz")):
                try:
                    out.append((f"{short} ({label})", float(value), unit))
                except ValueError:  # « [N/A] » sur certaines cartes
                    pass
        return out

    def _lhm(self):
        if time.monotonic() < self.lhm_retry:
            return []
        try:
            with urllib.request.urlopen(LHM_URL, timeout=0.5) as resp:
                tree = json.loads(resp.read())
        except (OSError, ValueError):
            self.lhm_retry = time.monotonic() + 30
            return []
        return lhm_temperatures(tree)


def lhm_temperatures(tree, limit=16):
    """Températures de l'arbre data.json de LibreHardwareMonitor : [(matériel (capteur), °C, "°C")]."""
    out = []

    def walk(node, hardware, group):
        text, value = node.get("Text", ""), str(node.get("Value", ""))
        children = node.get("Children", [])
        if not children and value.endswith("°C") and group == "Temperatures":
            try:
                out.append((f"{hardware} ({text})", float(value.split()[0].replace(",", ".")), "°C"))
            except ValueError:
                pass
        for child in children:
            # niveaux : racine > PC > matériel > groupe de capteurs (Temperatures, Loads…) > capteur
            if child.get("Children") and any(c.get("Children") for c in child["Children"]):
                walk(child, child.get("Text", hardware), group)
            elif child.get("Children"):
                walk(child, hardware, child.get("Text", ""))
            else:
                walk(child, hardware, group)

    walk(tree, "", "")
    return out[:limit]
