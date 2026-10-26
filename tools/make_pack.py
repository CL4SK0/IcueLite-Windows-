"""Fabrique IcueLite-pack.zip (tout le pack dans un dossier « icuelite/ »), pour la version script."""

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".git", ".github", "build", "dist", "venv", ".venv", "__pycache__", "tools"}
SKIP_FILES = {"IcueLite-pack.zip", "IcueLite.spec", "tests.log", "notes.txt", "version_info.txt"}


def files():
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT)
        if path.is_file() and not SKIP_DIRS.intersection(rel.parts) and rel.name not in SKIP_FILES:
            yield path, rel


def main(out="IcueLite-pack.zip"):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path, rel in files():
            z.write(path, Path("icuelite") / rel)
    print(f"{out} créé")


if __name__ == "__main__":
    main(*sys.argv[1:])
