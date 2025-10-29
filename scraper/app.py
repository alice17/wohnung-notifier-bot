import datetime
import logging
import re
import time
from typing import Set, Dict, Optional, List

from scraper.config import Config
from scraper.filter import ListingFilter
from scraper.listing import Listing
from scraper.notifier import TelegramNotifier
from scraper.scraper import Scraper
from scraper.store import ListingStore
import json

logger = logging.getLogger(__name__)
GREEN = "\033[92m"
RESET = "\033[0m"

class App:
    """The main application class orchestrating the monitoring process."""

    def __init__(self, config: Config, scraper: Scraper, store: ListingStore, notifier: TelegramNotifier):
        self.config = config
        self.scraper = scraper
        self.store = store
        self.notifier = notifier
        self.known_listing_ids: Set[str] = set()
        self.zip_to_borough_map: Optional[Dict[str, List[str]]] = None
        self.listing_filter: Optional[ListingFilter] = None

    def run(self):
        """Starts the main monitoring loop."""
        logger.info(f"Monitoring started for {self.config.scraper['target_url']}...")
        self.known_listing_ids = self.store.load()

        if not self.known_listing_ids:
            self._initialize_baseline()

        self._load_zip_to_borough_map()
        self.listing_filter = ListingFilter(self.config, self.zip_to_borough_map)

        while True:
            if self._is_suspended_time():
                logger.info("Service is suspended between midnight and 7 AM. Sleeping for 5 minutes.")
                time.sleep(300)
                continue

            try:
                self._check_for_updates()
            except Exception as e:
                logger.error(f"An unexpected error occurred in the main loop: {e}")
                self.notifier.send_message(f"⚠️ *Bot Error:* An unexpected error occurred: {e}")
                logger.info("Waiting 60 seconds before retrying...")
                time.sleep(60)

            logger.info(f"Sleeping for {self.config.scraper['poll_interval_seconds']} seconds...")
            time.sleep(self.config.scraper['poll_interval_seconds'])

    def _load_zip_to_borough_map(self):
        """Loads the zipcode to borough mapping from the JSON file."""
        try:
            with open('data/plz_bezirk.json', 'r', encoding='utf-8') as f:
                self.zip_to_borough_map = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load or parse plz_bezirk.json: {e}")
            self.zip_to_borough_map = {}

    def _initialize_baseline(self):
        """Fetches the initial set of listings to establish a baseline."""
        logger.info("No known listings file found. Fetching baseline.")
        initial_listings = self.scraper.get_current_listings()
        if initial_listings:
            self.known_listing_ids = set(initial_listings.keys())
            self.store.save(self.known_listing_ids)
            logger.info(f"Initial baseline set with {len(self.known_listing_ids)} listings.")
            self.notifier.send_message(
                f"✅ Monitoring started. Found {len(self.known_listing_ids)} initial listings."
            )
        else:
            logger.warning("Failed to get initial listings. Will retry.")

    def _check_for_updates(self):
        """Fetches current listings and compares them with the known ones."""
        logger.debug("Checking for new listings...")
        current_listings = self.scraper.get_current_listings()
        current_ids = set(current_listings.keys())

        if not current_ids and self.known_listing_ids:
            logger.info("Current check returned no listings.")

        new_listing_ids = current_ids - self.known_listing_ids
        if new_listing_ids:
            self._process_new_listings(new_listing_ids, current_listings)

        removed_count = len(self.known_listing_ids - current_ids)
        if removed_count > 0:
            logger.info(f"{removed_count} listing(s) were removed.")

        if new_listing_ids or removed_count > 0:
            self.known_listing_ids = current_ids
            self.store.save(self.known_listing_ids)
        else:
            logger.info("No changes detected.")

    def _process_new_listings(self, new_ids: Set[str], current_listings: Dict[str, Listing]):
        """Processes and notifies about new listings."""

        logger.info(f"{GREEN}Found {len(new_ids)} new listing(s)!{RESET}")
        for new_id in new_ids:
            listing = current_listings[new_id]
            if not self._is_listing_filtered(listing):
                message = self.notifier.format_listing_message(listing)
                self.notifier.send_message(message)
                time.sleep(1)  # Avoid rate limiting

    def _is_listing_filtered(self, listing: Listing) -> bool:
        """Checks if a listing should be filtered out based on criteria."""
        if self.listing_filter:
            return self.listing_filter.is_filtered(listing)
        return False

    @staticmethod
    def _is_suspended_time() -> bool:
        """Checks if the current time is within the suspended period (00:00 - 07:00)."""
        return 0 <= datetime.datetime.now().hour < 7
