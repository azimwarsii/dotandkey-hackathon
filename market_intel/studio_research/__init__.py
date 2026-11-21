"""Market research, source deconstruction and empirical patterns for Part 3."""

from .analysis import deconstruct
from .patterns import pattern_board
from .sources import discover

__all__ = ["deconstruct", "discover", "pattern_board"]
from .sources import ad_lifetime, readback_baseline, recommended_sources

__all__ += ["ad_lifetime", "readback_baseline", "recommended_sources"]
