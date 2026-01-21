"""
This package contains all the scraper implementations.
"""
from .base import BaseScraper
from .berlinovo import BerlinovoScraper
from .deutschewohnen import DeutscheWohnenScraper
from .immowelt import ImmoweltScraper
from .inberlinwohnen import InBerlinWohnenScraper
from .kleinanzeigen import KleinanzeigenScraper
from .ohnemakler import OhneMaklerScraper
from .vonovia import VonoviaScraper

# A dictionary to map scraper names to their classes
SCRAPER_CLASSES = {
    "berlinovo": BerlinovoScraper,
    "inberlinwohnen": InBerlinWohnenScraper,
    "immowelt": ImmoweltScraper,
    "kleinanzeigen": KleinanzeigenScraper,
    "ohnemakler": OhneMaklerScraper,
    "deutschewohnen": DeutscheWohnenScraper,
    "vonovia": VonoviaScraper,
}
