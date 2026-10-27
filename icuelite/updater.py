"""Mises à jour automatiques depuis les « Releases » GitHub du projet.

Chaque modification poussée sur GitHub fabrique une nouvelle version (voir .github/workflows/release.yml),
avec deux fichiers : IcueLite.exe et IcueLite-pack.zip. L'appli regarde la dernière version publiée,
la propose, puis remplace elle-même ses fichiers et redémarre.

Le dépôt est lu dans _build.py (écrit par le workflow), ou dans le fichier update-repo.txt à côté du programme.
"""

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from . import __version__

EXE_ASSET = "IcueLite.exe"
ZIP_ASSET = "IcueLite-pack.zip"
TIMEOUT = 15
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW
DETACHED = 0x00000008  # DETACHED_PROCESS


def frozen():
    return bool(getattr(sys, "frozen", False))


def install_dir() -> Path:
    """Dossier à mettre à jour : celui de l'.exe, ou la racine du pack en mode script."""
    if frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def repo():
    """« propriétaire/dépôt » GitHub, ou None si les mises à jour ne sont pas configurées."""
    try:
        from ._build import REPO
        if REPO:
            return REPO
    except ImportError:
        pass
    path = install_dir() / "update-repo.txt"
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    value = value.removeprefix("https://github.com/").strip("/")
    return value if value.count("/") == 1 else None


def parse_version(text):
    parts = []
    for p in text.strip().lstrip("vV").split("."):
        digits = "".join(c for c in p if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts + [0] * (3 - len(parts)))


def ssl_context():
    """Contexte HTTPS : vérification par Windows lui-même (truststore), qui télécharge au besoin les certificats
    racines manquants et accepte ceux qu'ajoute un antivirus ; à défaut, les racines de certifi en plus de
    celles du magasin Windows (Python seul ne voit que les racines déjà présentes, d'où des « certificat refusé »)."""
    import ssl
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        pass
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except (ImportError, OSError):
        pass
    return ctx


def urlopen(req, timeout=TIMEOUT):
    return urllib.request.urlopen(req, timeout=timeout, context=ssl_context())


def _get(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": f"IcueLite/{__version__}"})
    with urlopen(req) as resp:
        return resp.read()


def _latest_release(name):
    """(tag, notes, {nom: url}) de la dernière version. L'API GitHub limite les appels anonymes (60 par heure et
    par adresse IP) : si elle refuse ou ne répond pas, on suit la redirection de la page « latest » du site."""
    try:
        data = json.loads(_get(f"https://api.github.com/repos/{name}/releases/latest"))
        assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}
        return data.get("tag_name", ""), (data.get("body") or "").strip(), assets
    except (OSError, ValueError):
        req = urllib.request.Request(f"https://github.com/{name}/releases/latest",
                                     headers={"User-Agent": f"IcueLite/{__version__}"})
        with urlopen(req) as resp:
            tag = resp.geturl().rstrip("/").rsplit("/", 1)[-1]
        if "tag" not in resp.geturl():
            raise OSError("aucune version publiée trouvée")
        base = f"https://github.com/{name}/releases/download/{tag}"
        return tag, "", {n: f"{base}/{n}" for n in (EXE_ASSET, ZIP_ASSET)}


def describe(exc, site="GitHub"):
    """Message lisible pour une erreur réseau (site : le serveur contacté)."""
    import ssl
    import urllib.error
    reason = getattr(exc, "reason", None)
    if isinstance(exc, urllib.error.HTTPError):
        return f"{site} a répondu {exc.code}"
    if isinstance(reason, ssl.SSLError) or isinstance(exc, ssl.SSLError):
        return "certificat refusé (antivirus ou pare-feu qui filtre le HTTPS ?)"
    if isinstance(exc, TimeoutError) or "timed out" in str(reason or exc):
        return f"{site} ne répond pas (connexion ou pare-feu ?)"
    if reason is not None:
        return f"connexion impossible ({reason})"
    return f"{type(exc).__name__} : {exc}"


def check():
    """Renvoie la nouvelle version disponible (dict) ou None. Lève OSError si GitHub est injoignable."""
    name = repo()
    if not name:
        return None
    version, notes, assets = _latest_release(name)
    if parse_version(version) <= parse_version(__version__):
        return None
    url = assets.get(EXE_ASSET if frozen() else ZIP_ASSET)
    if not url:
        return None
    return {"version": version.lstrip("vV"), "notes": notes, "url": url}


def download(url, dest, progress=None):
    req = urllib.request.Request(url, headers={"User-Agent": f"IcueLite/{__version__}"})
    with urlopen(req) as resp, open(dest, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while chunk := resp.read(256 * 1024):
            out.write(chunk)
            done += len(chunk)
            if progress and total:
                progress(done / total)


def install(info, progress=None):
    """Télécharge et installe la mise à jour, puis lance le redémarrage. L'appli doit quitter juste après."""
    if frozen():
        _install_exe(info, progress)
    else:
        _install_pack(info, progress)


def _install_exe(info, progress):
    # Windows interdit d'écraser un .exe en cours d'exécution : un petit script attend
    # la fermeture d'IcueLite, remplace le fichier et le relance.
    exe = Path(sys.executable).resolve()
    new = exe.with_name(exe.stem + ".new.exe")
    download(info["url"], new, progress)
    script = Path(tempfile.gettempdir()) / "icuelite-update.cmd"
    script.write_text(
        "@echo off\r\n"
        f'set "EXE={exe}"\r\n'
        f'set "NEW={new}"\r\n'
        "for /l %%i in (1,1,40) do (\r\n"
        '  move /y "%NEW%" "%EXE%" >nul 2>&1 && goto ok\r\n'
        "  timeout /t 1 /nobreak >nul\r\n"
        ")\r\n"
        "exit /b 1\r\n"
        ":ok\r\n"
        'start "" "%EXE%" --after-update\r\n'
        '(goto) 2>nul & del "%~f0"\r\n',
        encoding="mbcs")
    subprocess.Popen(["cmd", "/c", str(script)], creationflags=NO_WINDOW | DETACHED, close_fds=True, env=clean_env())


def clean_env():
    """Environnement sans les variables internes de l'.exe en cours.

    Sinon le nouvel .exe se croit « enfant » de l'ancien et cherche ses fichiers dans le dossier
    temporaire _MEI… de l'ancien, effacé à sa fermeture (erreur « Failed to load Python DLL »).
    """
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("_PYI", "_MEIPASS"))}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def _install_pack(info, progress):
    root = install_dir()
    archive = Path(tempfile.gettempdir()) / ZIP_ASSET
    download(info["url"], archive, progress)
    extract_pack(archive, root)
    archive.unlink(missing_ok=True)
    flags = NO_WINDOW if os.name == "nt" else 0
    # les modules nécessaires ont pu changer : on les met à jour discrètement
    subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--quiet", "-r", str(root / "requirements.txt")],
                   creationflags=flags, check=False)
    subprocess.Popen([sys.executable, str(root / "IcueLite.pyw"), "--after-update"], cwd=root, creationflags=flags, close_fds=True)


def extract_pack(archive, root):
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            # le zip contient un dossier « icuelite/ » qui enveloppe tout le pack
            rel = Path(*Path(member.filename).parts[1:])
            if not rel.parts or member.is_dir() or ".." in rel.parts:
                continue
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(member) as src, open(target, "wb") as dst:
                dst.write(src.read())
