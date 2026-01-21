"""
Main application module for the scraper.
"""
import datetime
import logging
import time
from typing import Set, Dict, Optional, List, Tuple

from src.appliers import BaseApplier
from src.core.config import Config
from src.core.constants import (
    LISTING_MAX_AGE_DAYS,
    SUSPENSION_SLEEP_SECONDS,
)
from src.core.listing import Listing
from src.scrapers import BaseScraper
from src.services import BoroughResolver
from src.services.filter import ListingFilter
from src.services.listing_processor import ListingProcessor
from src.services.notifier import TelegramNotifier, escape_markdown_v2
from src.services.runner import ScraperRunner
from src.services.store import ListingStore

logger = logging.getLogger(__name__)


class App:
    """The main application class orchestrating the monitoring process."""

    def __init__(
        self,
        config: Config,
        scrapers: List[BaseScraper],
        store: ListingStore,
        notifier: TelegramNotifier,
        appliers: Optional[List[BaseApplier]] = None,
    ):
        """
        Initialize the App with configuration and components.

        Args:
            config: Configuration object with application settings.
            scrapers: List of scraper instances to run.
            store: Store instance for persisting listings.
            notifier: Notifier instance for sending alerts.
            appliers: Optional list of applier instances for auto-apply.
        """
        self.config = config
        self.scrapers = scrapers
        self.store = store
        self.notifier = notifier
        self.appliers = appliers or []
        self.scraper_runner = ScraperRunner(scrapers)
        self.known_listings: Dict[str, Listing] = {}
        self.borough_resolver: Optional[BoroughResolver] = None
        self.listing_processor: Optional[ListingProcessor] = None

    def setup(self) -> None:
        """Initializes the application state by loading data and setting up filters."""
        logger.info(f"Setting up the application with {len(self.scrapers)} sources...")
        
        # Set up borough resolver BEFORE scraping so scrapers can resolve boroughs
        self.borough_resolver = BoroughResolver()
        if self.borough_resolver.is_loaded():
            for scraper in self.scrapers:
                scraper.set_borough_resolver(self.borough_resolver)

        self.known_listings = self.store.load()

        if not self.known_listings:
            self._initialize_baseline()

        listing_filter = ListingFilter(self.config, self.borough_resolver)

        self.listing_processor = ListingProcessor(
            notifier=self.notifier,
            listing_filter=listing_filter,
            appliers=self.appliers,
        )

        logger.info("Application setup complete.")

    def run(self, cron_mode: bool = False) -> None:
        """
        Starts the main monitoring loop.

        Args:
            cron_mode: If True, run once and exit immediately (no sleep, no loop).
        """
        self.setup()
        logger.info("Monitoring started.")

        if cron_mode:
            logger.info("Running in cron mode (single execution).")
            try:
                self._check_for_updates()
            except Exception as e:
                self._handle_unexpected_error(e)
                
        else:
            while True:
                if self._handle_suspension():
                    continue

                try:
                    self._check_for_updates()
                except Exception as e:
                    self._handle_unexpected_error(e)

                logger.info(f"Sleeping for {self.config.poll_interval} seconds...")
                time.sleep(self.config.poll_interval)

    def _handle_suspension(self) -> bool:
        """
        Checks and handles suspension time logic.

        Returns:
            True if the service is suspended and slept, False otherwise.
        """
        if self._is_suspended_time():
            logger.info(
                f"Service is suspended between {self.config.suspension_start_hour}:00 "
                f"and {self.config.suspension_end_hour}:00. Sleeping for {SUSPENSION_SLEEP_SECONDS} seconds."
            )
            time.sleep(SUSPENSION_SLEEP_SECONDS)
            return True
        return False

    def _handle_unexpected_error(self, e: Exception) -> None:
        """
        Handles unexpected errors during the main loop execution.

        Args:
            e: The exception that occurred.
        """
        logger.exception(f"An unexpected error occurred in the main loop: {e}")
        try:
            # Escape error message for MarkdownV2 and limit length
            safe_error = escape_markdown_v2(str(e)[:200])
            self.notifier.send_message(
                f"⚠️ *Bot Error:* An unexpected error occurred: {safe_error}"
            )
        except Exception as notify_err:
            logger.error(f"Failed to send error notification to Telegram: {notify_err}")

    def _get_all_current_listings(
        self,
    ) -> Tuple[Dict[str, Dict[str, Listing]], Set[str], Set[str]]:
        """
        Fetches listings from all configured scrapers using the ScraperRunner.

        Returns:
            A tuple containing:
            - A dictionary mapping scraper names to their new listings.
            - A set of names of scrapers that failed.
            - A set of all seen known listing identifiers (still active).
        """
        return self.scraper_runner.run(self.known_listings)

    def _initialize_baseline(self) -> None:
        """Fetches the initial set of listings to establish a baseline."""
        logger.info("No known listings file found. Fetching baseline.")
        initial_listings_by_scraper, _, _ = self._get_all_current_listings()

        for listings in initial_listings_by_scraper.values():
            self.known_listings.update(listings)

        if self.known_listings:
            self.store.save(self.known_listings)
            logger.info(f"Initial baseline set with {len(self.known_listings)} listings.")
            self.notifier.send_message(
                f"✅ Monitoring started\\. Found {len(self.known_listings)} initial listings\\."
            )
        else:
            logger.warning("Failed to get initial listings. Will retry.")

    def _check_for_updates(self) -> None:
        """Fetches current listings and compares them with the known ones."""
        logger.info("Checking for new listings...")
        
        deleted_count = self.store.cleanup_old_listings(max_age_days=LISTING_MAX_AGE_DAYS)
        if deleted_count > 0:
            # Remove deleted listings from in-memory cache
            self.known_listings = self.store.load()
        
        current_listings_by_scraper, failed_scrapers, seen_known_ids = (
            self._get_all_current_listings()
        )

        # Touch listings that are still active on websites
        if seen_known_ids:
            touched_count = self.store.touch(list(seen_known_ids))
            if touched_count > 0:
                logger.debug(f"Touched {touched_count} existing listings as still active")

        if not any(current_listings_by_scraper.values()) and self.known_listings:
            logger.info("Current check returned no listings.")

        all_new_listings: Dict[str, Listing] = {}

        # Process scrapers that ran successfully
        for _, current_listings in current_listings_by_scraper.items():
            new_listings = self._process_scraper_results(current_listings)
            all_new_listings.update(new_listings)

        if failed_scrapers:
            logger.warning(f"Scrapers {', '.join(failed_scrapers)} failed. Their listings will be preserved.")

        self._save_new_listings(all_new_listings)

    def _save_new_listings(self, new_listings: Dict[str, Listing]) -> None:
        """
        Saves only the new listings to the store and updates in-memory cache.
        
        Only new listings are saved to avoid refreshing updated_at timestamps
        for existing listings. This ensures that listings no longer found by
        scrapers will be automatically cleaned up after LISTING_MAX_AGE_DAYS.

        Args:
            new_listings: Dictionary of newly discovered listings to save.
        """
        if new_listings:
            self.known_listings.update(new_listings)
            self.store.save(new_listings)
            logger.info(f"Saved {len(new_listings)} new listing(s).")
        else:
            logger.info("No new listings found.")

    def _process_scraper_results(
        self,
        current_listings: Dict[str, Listing],
    ) -> Dict[str, Listing]:
        """
        Processes listings from a single scraper and returns new listings.
        
        Note: Scrapers are optimized for live updates and use early termination,
        returning only NEW listings (not all current listings). Therefore, we
        only add new listings and do NOT remove listings based on scraper results.

        Args:
            current_listings: Dictionary of NEW listings found by the scraper.

        Returns:
            Dictionary of new listings that weren't previously known.
        """
        if not current_listings:
            return {}

        # Double-check: filter out any listings we already know about
        # (scrapers should already do this, but this is a safety check)
        new_listings = {
            listing_id: listing
            for listing_id, listing in current_listings.items()
            if listing_id not in self.known_listings
        }

        if new_listings and self.listing_processor:
            self.listing_processor.process_new_listings(new_listings)

        return new_listings

    def _is_suspended_time(self) -> bool:
        """
        Checks if the current time is within the configured suspension period.

        Returns:
            True if the current hour is within the suspension period, False otherwise.
        """
        current_hour = datetime.datetime.now().hour
        start_hour = self.config.suspension_start_hour
        end_hour = self.config.suspension_end_hour
        return start_hour <= current_hour < end_hour
