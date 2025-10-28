import datetime
import logging
import time
from typing import Set, Dict, Optional

from scraper.config import Config
from scraper.listing import Listing
from scraper.notifier import TelegramNotifier
from scraper.scraper import Scraper
from scraper.store import ListingStore

logger = logging.getLogger(__name__)


class App:
    """The main application class orchestrating the monitoring process."""

    def __init__(self, config: Config, scraper: Scraper, store: ListingStore, notifier: TelegramNotifier):
        self.config = config
        self.scraper = scraper
        self.store = store
        self.notifier = notifier
        self.known_listing_ids: Set[str] = set()

    def run(self):
        """Starts the main monitoring loop."""
        logger.info(f"Monitoring started for {self.config.scraper['target_url']}...")
        self.known_listing_ids = self.store.load()

        if not self.known_listing_ids:
            self._initialize_baseline()

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
        logger.info(f"Found {len(new_ids)} new listing(s)!")
        for new_id in new_ids:
            listing = current_listings[new_id]
            if not self._is_listing_filtered(listing):
                message = self.notifier.format_listing_message(listing)
                self.notifier.send_message(message)
                time.sleep(1)  # Avoid rate limiting

    def _is_listing_filtered(self, listing: Listing) -> bool:
        """Checks if a listing should be filtered out based on criteria."""
        filters = self.config.filters
        if not filters.get("enabled", False):
            return False

        def passes_filter(value: Optional[float], rules: Dict[str, float]) -> bool:
            if value is None:
                return True
            if rules.get("min") is not None and value < rules["min"]:
                return False
            if rules.get("max") is not None and value > rules["max"]:
                return False
            return True

        price_val = self._to_numeric(listing.price_total)
        if not passes_filter(price_val, filters.get("properties", {}).get("price_total", {})):
            logger.debug(f"FILTERED (Price): {listing.price_total}€")
            return True

        sqm_val = self._to_numeric(listing.sqm)
        if not passes_filter(sqm_val, filters.get("properties", {}).get("sqm", {})):
            logger.debug(f"FILTERED (SQM): {listing.sqm}m²")
            return True

        rooms_val = self._to_numeric(listing.rooms)
        if not passes_filter(rooms_val, filters.get("properties", {}).get("rooms", {})):
            logger.debug(f"FILTERED (Rooms): {listing.rooms}")
            return True

        wbs_rules = filters.get("properties", {}).get("wbs", {})
        wbs_allowed = wbs_rules.get("allowed_values", [])
        if wbs_allowed and listing.wbs.strip().lower() not in [v.lower() for v in wbs_allowed]:
            logger.debug(f"FILTERED (WBS): '{listing.wbs}'")
            return True

        return False

    @staticmethod
    def _to_numeric(value_str: str) -> Optional[float]:
        """Converts a formatted string (e.g., '1.234,56') to a float."""
        if not isinstance(value_str, str) or value_str == 'N/A':
            return None
        try:
            return float(value_str.replace('.', '').replace(',', '.'))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _is_suspended_time() -> bool:
        """Checks if the current time is within the suspended period (00:00 - 07:00)."""
        return 0 <= datetime.datetime.now().hour < 7
