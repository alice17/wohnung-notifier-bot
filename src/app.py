"""
Main application module for the scraper.
"""
import datetime
import logging
import time
from typing import Set, Dict, Optional, List, Tuple

from src.appliers import WBMApplier
from src.core.config import Config
from src.core.constants import (
    Colors,
    LISTING_MAX_AGE_DAYS,
    RATE_LIMIT_SLEEP_SECONDS,
    SUSPENSION_SLEEP_SECONDS,
)
from src.core.listing import Listing
from src.scrapers import BaseScraper
from src.services import BoroughResolver
from src.services.filter import ListingFilter
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
    ):
        """
        Initialize the App with configuration and components.

        Args:
            config: Configuration object with application settings.
            scrapers: List of scraper instances to run.
            store: Store instance for persisting listings.
            notifier: Notifier instance for sending alerts.
        """
        self.config = config
        self.scrapers = scrapers
        self.store = store
        self.notifier = notifier
        self.scraper_runner = ScraperRunner(scrapers)
        self.known_listings: Dict[str, Listing] = {}
        self.borough_resolver: Optional[BoroughResolver] = None
        self.listing_filter: Optional[ListingFilter] = None
        self.wbm_applier = WBMApplier(config.wbm_config)

    def setup(self) -> None:
        """Initializes the application state by loading data and setting up filters."""
        logger.info(f"Setting up the application with {len(self.scrapers)} sources...")
        self.known_listings = self.store.load()

        if not self.known_listings:
            self._initialize_baseline()

        self.borough_resolver = BoroughResolver()
        self.listing_filter = ListingFilter(self.config, self.borough_resolver)

        if self.borough_resolver.is_loaded():
            for scraper in self.scrapers:
                scraper.set_borough_resolver(self.borough_resolver)

        logger.info("Application setup complete.")

    def run(self) -> None:
        """Starts the main monitoring loop."""
        self.setup()
        logger.info("Monitoring started.")

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

    def _get_all_current_listings(self) -> Tuple[Dict[str, Dict[str, Listing]], Set[str]]:
        """
        Fetches listings from all configured scrapers using the ScraperRunner.

        Returns:
            A tuple containing:
            - A dictionary mapping scraper names to their current listings.
            - A set of names of scrapers that failed.
        """
        return self.scraper_runner.run(self.known_listings)

    def _initialize_baseline(self) -> None:
        """Fetches the initial set of listings to establish a baseline."""
        logger.info("No known listings file found. Fetching baseline.")
        initial_listings_by_scraper, _ = self._get_all_current_listings()

        for listings in initial_listings_by_scraper.values():
            self.known_listings.update(listings)

        if self.known_listings:
            self.store.save(self.known_listings)
            logger.info(f"Initial baseline set with {len(self.known_listings)} listings.")
            self.notifier.send_message(
                f"✅ Monitoring started. Found {len(self.known_listings)} initial listings."
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
        
        current_listings_by_scraper, failed_scrapers = self._get_all_current_listings()

        if not any(current_listings_by_scraper.values()) and self.known_listings:
            logger.info("Current check returned no listings.")

        updated_known_listings = self.known_listings.copy()
        total_changes = False

        # Process scrapers that ran successfully
        for scraper_name, current_listings in current_listings_by_scraper.items():
            scraper_changed = self._process_scraper_results(
                scraper_name, current_listings, updated_known_listings
            )
            if scraper_changed:
                total_changes = True

        if failed_scrapers:
            logger.warning(f"Scrapers {', '.join(failed_scrapers)} failed. Their listings will be preserved.")

        self._save_changes_if_needed(updated_known_listings, total_changes)

    def _save_changes_if_needed(
        self, updated_known_listings: Dict[str, Listing], changes_detected: bool
    ) -> None:
        """
        Saves the updated listings to the store if changes were detected.

        Args:
            updated_known_listings: The new state of known listings.
            changes_detected: Whether any changes were detected.
        """
        if changes_detected:
            self.known_listings = updated_known_listings
            self.store.save(self.known_listings)
            logger.info("Changes detected and saved.")
        else:
            logger.info("No changes detected.")

    def _process_scraper_results(
        self,
        scraper_name: str,
        current_listings: Dict[str, Listing],
        updated_known_listings: Dict[str, Listing],
    ) -> bool:
        """
        Processes listings from a single scraper, updating known listings.
        
        Note: Scrapers are optimized for live updates and use early termination,
        returning only NEW listings (not all current listings). Therefore, we
        only add new listings and do NOT remove listings based on scraper results.

        Args:
            scraper_name: Name of the scraper being processed.
            current_listings: Dictionary of NEW listings found by the scraper.
            updated_known_listings: Dictionary of known listings to be updated (in-place).

        Returns:
            True if new listings were added, False otherwise.
        """
        if not current_listings:
            return False

        # Double-check: filter out any listings we already know about
        # (scrapers should already do this, but this is a safety check)
        new_listings = {
            listing_id: listing
            for listing_id, listing in current_listings.items()
            if listing_id not in self.known_listings
        }

        if not new_listings:
            return False

        self._process_new_listings(new_listings)
        updated_known_listings.update(new_listings)

        return True

    def _process_new_listings(self, new_listings: Dict[str, Listing]) -> None:
        """
        Processes and notifies about new listings.

        Args:
            new_listings: Dictionary of new listings to process.
        """
        logger.info(f"{Colors.GREEN}Found {len(new_listings)} new listing(s)!{Colors.RESET}")
        for listing in new_listings.values():
            logger.info(f"Processing new listing: {listing}")
            if not self._is_listing_filtered(listing):
                message = self.notifier.format_listing_message(listing)
                self.notifier.send_message(message)
                
                # Check for WBM auto-apply
                self._try_auto_apply(listing)
                    
                time.sleep(RATE_LIMIT_SLEEP_SECONDS)

    def _try_auto_apply(self, listing: Listing) -> None:
        """
        Attempts to auto-apply for a listing using available appliers.

        Args:
            listing: The listing to apply for.
        """
        if self.wbm_applier.can_apply(listing):
            result = self.wbm_applier.apply(listing)
            if result.is_success and result.applicant_data:
                telegram_message = self.wbm_applier.format_success_message(
                    listing.link, result.applicant_data
                )
                self.notifier.send_message(telegram_message)

    def _is_listing_filtered(self, listing: Listing) -> bool:
        """
        Checks if a listing should be filtered out based on criteria.

        Args:
            listing: The listing to check.

        Returns:
            True if the listing should be filtered out, False otherwise.
        """
        if self.listing_filter:
            return self.listing_filter.is_filtered(listing)
        return False

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
