from .base_scraper import BaseScraper
from .inberlinwohnen_scraper import InBerlinWohnenScraper
from .immowelt_scraper import ImmoweltScraper

# A dictionary to map scraper names to their classes
SCRAPER_CLASSES = {
    "inberlinwohnen": InBerlinWohnenScraper,
    "immowelt": ImmoweltScraper,
}
