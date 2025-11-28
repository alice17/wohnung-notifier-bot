"""
Listing processing pipeline for new listings.

This module handles the orchestration of filtering, notification,
and auto-apply logic for new apartment listings.
"""
import logging
import time
from typing import Dict, List, Optional

from src.appliers.base import BaseApplier
from src.core.constants import Colors, RATE_LIMIT_SLEEP_SECONDS
from src.core.listing import Listing
from src.services.filter import ListingFilter
from src.services.notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class ListingProcessor:
    """
    Orchestrates the processing pipeline for new listings.
    
    Handles filtering, notification, and auto-apply logic in a single
    cohesive component, separating these concerns from the main App class.
    """

    def __init__(
        self,
        notifier: TelegramNotifier,
        listing_filter: Optional[ListingFilter] = None,
        appliers: Optional[List[BaseApplier]] = None,
    ):
        """
        Initialize the ListingProcessor with required components.

        Args:
            notifier: Service for sending Telegram notifications.
            listing_filter: Optional filter for excluding listings.
            appliers: Optional list of auto-appliers to use.
        """
        self._notifier = notifier
        self._filter = listing_filter
        self._appliers = appliers or []

    def process_new_listings(self, new_listings: Dict[str, Listing]) -> int:
        """
        Process new listings through the complete pipeline.

        Each listing is filtered, notified (if passing filters),
        and auto-applied to if applicable.

        Args:
            new_listings: Dictionary mapping listing IDs to Listing objects.

        Returns:
            Number of listings that passed filters and were notified.
        """
        if not new_listings:
            return 0

        logger.info(
            f"{Colors.GREEN}Found {len(new_listings)} new listing(s)!{Colors.RESET}"
        )

        processed_count = 0
        for listing in new_listings.values():
            logger.info(f"Processing new listing: {listing}")
            if self._process_single_listing(listing):
                processed_count += 1
                time.sleep(RATE_LIMIT_SLEEP_SECONDS)

        return processed_count

    def _process_single_listing(self, listing: Listing) -> bool:
        """
        Process a single listing through filter, notify, and apply steps.

        Args:
            listing: The listing to process.

        Returns:
            True if listing passed filters and was notified, False otherwise.
        """
        if self._is_filtered(listing):
            return False

        self._send_notification(listing)
        self._try_auto_apply(listing)
        return True

    def _is_filtered(self, listing: Listing) -> bool:
        """
        Check if a listing should be filtered out.

        Args:
            listing: The listing to check.

        Returns:
            True if listing should be filtered out, False otherwise.
        """
        if self._filter is None:
            return False
        return self._filter.is_filtered(listing)

    def _send_notification(self, listing: Listing) -> None:
        """
        Send a Telegram notification for the listing.

        Args:
            listing: The listing to notify about.
        """
        message = self._notifier.format_listing_message(listing)
        self._notifier.send_message(message)

    def _try_auto_apply(self, listing: Listing) -> None:
        """
        Attempt auto-apply with all registered appliers.

        Iterates through appliers and attempts to apply with the first
        one that can handle the listing. Sends success notification
        if application succeeds.

        Args:
            listing: The listing to apply for.
        """
        for applier in self._appliers:
            if applier.can_apply(listing):
                result = applier.apply(listing)
                if result.is_success and result.applicant_data:
                    success_message = applier.format_success_message(
                        listing.link, result.applicant_data
                    )
                    self._notifier.send_message(success_message)
                # Only try the first matching applier
                break

