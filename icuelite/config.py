"""Réglages d'IcueLite, rangés dans %APPDATA%\\IcueLite (ou ~/.config/icuelite hors Windows)."""

import json
import os
import sys
from pathlib import Path


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "IcueLite"
    else:
        base = Path.home() / ".config" / "icuelite"
    base.mkdir(parents=True, exist_ok=True)
    return base


def load():
    try:
        return json.loads((config_dir() / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(cfg):
    path = config_dir() / "config.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
