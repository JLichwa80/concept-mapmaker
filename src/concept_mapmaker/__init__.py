"""Build interactive concept maps from Markdown."""

from importlib.metadata import PackageNotFoundError, version

from .builder import build, build_map, load_spec, parse

__all__ = ["build", "build_map", "load_spec", "parse"]

try:
    __version__ = version("concept-mapmaker")
except PackageNotFoundError:  # Running directly from an unpacked source tree.
    __version__ = "0+unknown"

