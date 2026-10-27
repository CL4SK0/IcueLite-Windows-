"""IcueLite : un iCUE allégé pour Windows, sans le logiciel Corsair."""

__version__ = "0.3.0"

try:  # numéro de version fixé par le build automatique (voir .github/workflows/release.yml)
    from ._build import VERSION as __version__  # noqa: F811
except ImportError:
    pass
