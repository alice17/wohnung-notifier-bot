"""
This package contains all the scraper implementations.
"""
from .base import BaseScraper
from .degewo import DegewoScraper
from .deutschewohnen import DeutscheWohnenScraper
from .immowelt import ImmoweltScraper
from .inberlinwohnen import InBerlinWohnenScraper
from .kleinanzeigen import KleinanzeigenScraper
from .ohnemakler import OhneMaklerScraper

# A dictionary to map scraper names to their classes
SCRAPER_CLASSES = {
    "inberlinwohnen": InBerlinWohnenScraper,
    "immowelt": ImmoweltScraper,
    "kleinanzeigen": KleinanzeigenScraper,
    "ohnemakler": OhneMaklerScraper,
    "deutschewohnen": DeutscheWohnenScraper,
    "degewo": DegewoScraper,
}
