"""
Main application module for the scraper.
"""
import datetime
import logging
import json
import time
from typing import Set, Dict, Optional, List, Tuple

from src.config import Config
from src.filter import ListingFilter
from src.listing import Listing
from src.notifier import TelegramNotifier, escape_markdown_v2
from src.runner import ScraperRunner
from src.scrapers import BaseScraper
from src.store import ListingStore
from src.appliers.wbm import apply_wbm

logger = logging.getLogger(__name__)
GREEN = "\033[92m"
RESET = "\033[0m"

PLZ_BEZIRK_FILE = 'data/plz_bezirk.json'
SUSPENSION_SLEEP_TIME = 600  # 10 minutes
RATE_LIMIT_SLEEP_TIME = 1


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
        self.zip_to_borough_map: Optional[Dict[str, List[str]]] = None
        self.listing_filter: Optional[ListingFilter] = None

    def setup(self) -> None:
        """Initializes the application state by loading data and setting up filters."""
        logger.info(f"Setting up the application with {len(self.scrapers)} sources...")
        self.known_listings = self.store.load()

        if not self.known_listings:
            self._initialize_baseline()

        self._load_zip_to_borough_map()
        self.listing_filter = ListingFilter(self.config, self.zip_to_borough_map)

        if self.zip_to_borough_map:
            for scraper in self.scrapers:
                scraper.set_zip_to_borough_map(self.zip_to_borough_map)

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
                f"and {self.config.suspension_end_hour}:00. Sleeping for {SUSPENSION_SLEEP_TIME} seconds."
            )
            time.sleep(SUSPENSION_SLEEP_TIME)
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

    def _load_zip_to_borough_map(self) -> None:
        """
        Loads the zipcode to borough mapping from the JSON file.
        """
        try:
            with open(PLZ_BEZIRK_FILE, 'r', encoding='utf-8') as f:
                self.zip_to_borough_map = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load or parse {PLZ_BEZIRK_FILE}: {e}")
            self.zip_to_borough_map = {}

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

        Args:
            scraper_name: Name of the scraper being processed.
            current_listings: Dictionary of current listings found by the scraper.
            updated_known_listings: Dictionary of known listings to be updated (in-place).

        Returns:
            True if changes were detected (additions or removals), False otherwise.
        """
        something_changed = False
        known_listings_for_scraper = {
            id: listing
            for id, listing in self.known_listings.items()
            if listing.source == scraper_name
        }

        current_ids = set(current_listings.keys())
        known_ids = set(known_listings_for_scraper.keys())

        # Process new listings
        new_listing_ids = current_ids - known_ids
        if new_listing_ids:
            something_changed = True
            new_listings = {new_id: current_listings[new_id] for new_id in new_listing_ids}
            self._process_new_listings(new_listings)
            updated_known_listings.update(new_listings)

        # Process removed listings
        removed_ids = known_ids - current_ids
        if removed_ids:
            something_changed = True
            logger.info(f"{len(removed_ids)} listing(s) were removed from {scraper_name}.")
            for removed_id in removed_ids:
                if removed_id in updated_known_listings:
                    del updated_known_listings[removed_id]

        return something_changed

    def _process_new_listings(self, new_listings: Dict[str, Listing]) -> None:
        """
        Processes and notifies about new listings.

        Args:
            new_listings: Dictionary of new listings to process.
        """
        logger.info(f"{GREEN}Found {len(new_listings)} new listing(s)!{RESET}")
        for listing in new_listings.values():
            logger.info(f"Processing new listing: {listing}")
            if not self._is_listing_filtered(listing):
                message = self.notifier.format_listing_message(listing)
                self.notifier.send_message(message)
                
                # Check for WBM auto-apply
                if listing.link.startswith("https://www.wbm.de/") or listing.link.startswith("https://https://www.wbm.de/"):
                    apply_wbm(listing.link, self.config.wbm_config, self.notifier)
                    
                time.sleep(RATE_LIMIT_SLEEP_TIME)  # Avoid rate limiting

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
