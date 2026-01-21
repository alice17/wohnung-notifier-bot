"""
This module defines the ScraperRunner class, which is responsible for running scrapers.

All scrapers are optimized for live updates and support early termination
when known listings are passed. This significantly reduces scraping time
when monitoring for new listings.

Scrapers are executed concurrently using a thread pool for maximum performance,
since scraping is I/O-bound (waiting on HTTP responses).
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Set

from src.core.listing import Listing
from src.scrapers import BaseScraper

logger = logging.getLogger(__name__)

DEFAULT_MAX_WORKERS = 10


class ScraperRunner:
    # pylint: disable=too-few-public-methods
    """
    Manages the concurrent execution of multiple scrapers.
    
    Executes all scrapers in parallel using a thread pool, significantly
    reducing total scraping time compared to sequential execution.
    """

    def __init__(self, scrapers: List[BaseScraper], max_workers: int = DEFAULT_MAX_WORKERS):
        """
        Initializes the scraper runner.
        
        Args:
            scrapers: List of scraper instances to run.
            max_workers: Maximum number of concurrent threads (default: 10).
        """
        self.scrapers = scrapers
        self.max_workers = max_workers

    def run(
        self, known_listings: Dict[str, Listing]
    ) -> Tuple[Dict[str, Dict[str, Listing]], Set[str]]:
        """
        Executes all configured scrapers concurrently and returns their findings.
        
        All scrapers receive known_listings for early termination optimization.
        Since listings are sorted newest-first, scrapers stop processing when
        they encounter a known listing.
        
        Scrapers run in parallel using a thread pool, reducing total execution
        time from O(n * avg_time) to O(max_time) where n is the number of scrapers.
        
        Args:
            known_listings: Previously seen listings for early termination.

        Returns:
            A tuple containing:
            - A dictionary mapping scraper names to their current listings.
            - A set of names of scrapers that failed during execution.
        """
        all_listings_by_scraper: Dict[str, Dict[str, Listing]] = {}
        failed_scrapers: Set[str] = set()

        if not self.scrapers:
            return all_listings_by_scraper, failed_scrapers

        worker_count = min(self.max_workers, len(self.scrapers))
        logger.info(f"Running {len(self.scrapers)} scraper(s) concurrently with {worker_count} workers")

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_scraper = {
                executor.submit(self._run_single_scraper, scraper, known_listings): scraper
                for scraper in self.scrapers
            }

            for future in as_completed(future_to_scraper):
                scraper = future_to_scraper[future]
                try:
                    listings = future.result()
                    all_listings_by_scraper[scraper.name] = listings
                    logger.info(
                        f"Scraper '{scraper.name}' returned {len(listings)} new listing(s)."
                    )
                except Exception as exc:
                    logger.error(f"Error getting listings from {scraper.name}: {exc}")
                    failed_scrapers.add(scraper.name)

        return all_listings_by_scraper, failed_scrapers

    def _run_single_scraper(
        self, scraper: BaseScraper, known_listings: Dict[str, Listing]
    ) -> Dict[str, Listing]:
        """
        Executes a single scraper and returns its listings.
        
        This method is designed to be called from a thread pool.
        
        Args:
            scraper: The scraper instance to run.
            known_listings: Previously seen listings for early termination.
            
        Returns:
            Dictionary mapping listing identifiers to Listing objects.
            
        Raises:
            Exception: Any exception raised by the scraper is propagated.
        """
        logger.debug(f"Starting scraper '{scraper.name}'")
        return scraper.get_current_listings(known_listings)
