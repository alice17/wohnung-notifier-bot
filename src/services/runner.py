"""
This module defines the ScraperRunner class, which is responsible for running scrapers.

All scrapers are optimized for live updates and support early termination
when known listings are passed. This significantly reduces scraping time
when monitoring for new listings.
"""
import logging
from typing import List, Dict, Tuple, Set

from src.core.listing import Listing
from src.scrapers import BaseScraper

logger = logging.getLogger(__name__)


class ScraperRunner:
    # pylint: disable=too-few-public-methods
    """Manages the execution of multiple scrapers and collects their results."""

    def __init__(self, scrapers: List[BaseScraper]):
        """
        Initializes the scraper runner.
        
        Args:
            scrapers: List of scraper instances to run.
        """
        self.scrapers = scrapers

    def run(
        self, known_listings: Dict[str, Listing]
    ) -> Tuple[Dict[str, Dict[str, Listing]], Set[str]]:
        """
        Executes all configured scrapers and returns their findings.
        
        All scrapers receive known_listings for early termination optimization.
        Since listings are sorted newest-first, scrapers stop processing when
        they encounter a known listing.
        
        Args:
            known_listings: Previously seen listings for early termination.

        Returns:
            A tuple containing:
            - A dictionary mapping scraper names to their current listings.
            - A set of names of scrapers that failed during execution.
        """
        all_listings_by_scraper: Dict[str, Dict[str, Listing]] = {}
        failed_scrapers: Set[str] = set()

        for scraper in self.scrapers:
            try:
                # All scrapers support known_listings for early termination
                listings = scraper.get_current_listings(known_listings)
                all_listings_by_scraper[scraper.name] = listings
                logger.info(
                    f"Scraper '{scraper.name}' returned {len(listings)} new listing(s)."
                )
            except Exception as e:
                logger.error(f"Error getting listings from {scraper.name}: {e}")
                failed_scrapers.add(scraper.name)

        return all_listings_by_scraper, failed_scrapers
