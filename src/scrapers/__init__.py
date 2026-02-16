"""
This package contains all the scraper implementations.
"""
from .base import BaseScraper
from .berlinovo import BerlinovoScraper
from .deutschewohnen import DeutscheWohnenScraper
from .immobilienscout import ImmobilienScoutScraper
from .immowelt import ImmoweltScraper
from .inberlinwohnen import InBerlinWohnenScraper
from .kleinanzeigen import KleinanzeigenScraper
from .ohnemakler import OhneMaklerScraper
from .sparkasse import SparkasseScraper
from .vonovia import VonoviaScraper

# A dictionary to map scraper names to their classes
SCRAPER_CLASSES = {
    "berlinovo": BerlinovoScraper,
    "inberlinwohnen": InBerlinWohnenScraper,
    "immobilienscout": ImmobilienScoutScraper,
    "immowelt": ImmoweltScraper,
    "kleinanzeigen": KleinanzeigenScraper,
    "ohnemakler": OhneMaklerScraper,
    "deutschewohnen": DeutscheWohnenScraper,
    "sparkasse": SparkasseScraper,
    "vonovia": VonoviaScraper,
}
