"""Barrettes mémoire vues par Windows (WMI) : référence, capacité, vitesse réelle et vitesse prévue.

La lecture passe par PowerShell (une seconde environ) : elle est faite une fois, en arrière-plan.
"""

import json
import re
import subprocess
import sys

NO_WINDOW = 0x08000000


def parse_part(part):
    """(vitesse prévue en MT/s, latence CL) d'une référence Corsair comme CMK64GX5M2B6000Z40, ou (None, None)."""
    m = re.search(r"X5M\d[A-Z](\d{4})[A-Z](\d{2})", part.upper())
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def modules():
    """[{"part", "capacity_gb", "speed", "rated", "cl"}] des barrettes installées (liste vide en cas d'échec)."""
    if sys.platform != "win32":
        return []
    cmd = ("Get-CimInstance Win32_PhysicalMemory | Select-Object PartNumber,Capacity,ConfiguredClockSpeed "
           "| ConvertTo-Json")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                             timeout=30, creationflags=NO_WINDOW).stdout.strip()
        rows = json.loads(out) if out else []
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []
    if isinstance(rows, dict):
        rows = [rows]
    result = []
    for row in rows:
        part = (row.get("PartNumber") or "").strip()
        rated, cl = parse_part(part)
        result.append({"part": part, "capacity_gb": int(row.get("Capacity") or 0) // 2 ** 30,
                       "speed": row.get("ConfiguredClockSpeed"), "rated": rated, "cl": cl})
    return result
