"""
This module defines the ScraperRunner class, which is responsible for running scrapers.
"""
import logging
from typing import List, Dict, Tuple, Set

from src.listing import Listing
from src.scrapers import BaseScraper
from src.scrapers.immowelt import ImmoweltScraper

logger = logging.getLogger(__name__)


class ScraperRunner:
    # pylint: disable=too-few-public-methods
    """Manages the execution of multiple scrapers and collects their results."""

    def __init__(self, scrapers: List[BaseScraper]):
        self.scrapers = scrapers

    def run(
        self, known_listings: Dict[str, Listing]
    ) -> Tuple[Dict[str, Dict[str, Listing]], Set[str]]:
        """
        Executes all configured scrapers and returns their findings.

        Returns:
            A tuple containing:
            - A dictionary mapping scraper names to their current listings.
            - A set of names of scrapers that failed during execution.
        """
        all_listings_by_scraper: Dict[str, Dict[str, Listing]] = {}
        failed_scrapers: Set[str] = set()

        for scraper in self.scrapers:
            try:
                if isinstance(scraper, ImmoweltScraper):
                    listings = scraper.get_current_listings(known_listings)
                else:
                    listings = scraper.get_current_listings()

                all_listings_by_scraper[scraper.name] = listings
                logger.info(f"Scraper '{scraper.name}' successfully returned {len(listings)} listings.")
            except Exception as e:
                logger.error(f"Error getting listings from {scraper.name}: {e}")
                failed_scrapers.add(scraper.name)

        return all_listings_by_scraper, failed_scrapers
