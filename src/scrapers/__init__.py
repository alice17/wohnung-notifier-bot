"""
This package contains all the scraper implementations.
"""
from .base import BaseScraper
from .immowelt import ImmoweltScraper
from .inberlinwohnen import InBerlinWohnenScraper
from .kleinanzeigen import KleinanzeigenScraper

# A dictionary to map scraper names to their classes
SCRAPER_CLASSES = {
    "inberlinwohnen": InBerlinWohnenScraper,
    "immowelt": ImmoweltScraper,
    "kleinanzeigen": KleinanzeigenScraper,
}
