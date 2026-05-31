# open sessemi
from importlib.metadata import version as _pkg_version, PackageNotFoundError
from .client import Sessemi, ScrapeResult, SessemiError, SessemiTimeout, SessemiUnavailable

__all__ = ["Sessemi", "ScrapeResult", "SessemiError", "SessemiTimeout", "SessemiUnavailable"]

try:
    # Version is baked into wheel/sdist metadata at build time by setuptools_scm,
    # derived from the most recent `v*` git tag. The source has no hardcoded
    # version literal.
    __version__ = _pkg_version("sessemi")
except PackageNotFoundError:
    # Running from source without a pip install (e.g. python -m sessemi.cli
    # straight from a clone). The metadata isn't registered. Surface a clearly
    # bogus value rather than crashing on import.
    __version__ = "0.0.0+unknown"
