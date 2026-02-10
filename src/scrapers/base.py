"""
This module defines the BaseScraper abstract base class.

The BaseScraper implements the Template Method pattern: get_current_listings()
provides the common orchestration logic (known-ID tracking, early termination,
logging, error handling), while subclasses implement _fetch_raw_items() and
_parse_item() for scraper-specific data fetching and parsing.
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, Optional, Set, Tuple, TYPE_CHECKING

import requests

from src.core.constants import DEFAULT_USER_AGENT
from src.core.listing import Listing

if TYPE_CHECKING:
    from src.services import BoroughResolver

logger = logging.getLogger(__name__)

# Type alias for scraper results: (new_listings, seen_known_ids)
ScraperResult = Tuple[Dict[str, Listing], Set[str]]


class BaseScraper(ABC):
    """Abstract base class for a scraper.

    Subclasses must implement:
        _fetch_raw_items(): Fetch raw data items (API responses, HTML elements, etc.)
        _parse_item(): Parse a single raw item into a Listing

    Subclasses may override:
        _extract_identifier_fast(): Quick identifier extraction for early termination
        supports_early_termination: Set to False to disable early termination
    """

    supports_early_termination: bool = True

    def __init__(self, name: str):
        self.name = name
        self.url: str = ""
        self.headers = {'User-Agent': DEFAULT_USER_AGENT}
        self.borough_resolver: Optional[BoroughResolver] = None

    def set_borough_resolver(self, borough_resolver: BoroughResolver) -> None:
        """
        Sets the borough resolver for the scraper.

        Args:
            borough_resolver: Service for resolving zip codes to boroughs.
        """
        self.borough_resolver = borough_resolver

    def get_current_listings(
        self, known_listings: Optional[Dict[str, Listing]] = None
    ) -> ScraperResult:
        """
        Fetches the website/API and returns new listings and seen known IDs.

        This template method handles the common orchestration logic:
        extracting known IDs, iterating raw items, checking for early
        termination, and logging results. Subclasses implement
        _fetch_raw_items() and _parse_item() for the scraper-specific logic.

        Args:
            known_listings: Previously seen listings for early termination.

        Returns:
            Tuple containing:
            - Dictionary mapping identifiers to new Listing objects
            - Set of known listing identifiers that were seen (still active)

        Raises:
            requests.RequestException: If an HTTP request fails.
        """
        known_ids: Set[str] = set(known_listings.keys()) if known_listings else set()
        new_listings: Dict[str, Listing] = {}
        seen_known_ids: Set[str] = set()

        try:
            raw_items = self._fetch_raw_items()
            logger.debug(f"Fetched {len(raw_items)} items from {self.name}")

            for item in raw_items:
                # Try fast identifier extraction (avoids expensive full parse)
                identifier = self._extract_identifier_fast(item)

                if identifier and identifier in known_ids:
                    seen_known_ids.add(identifier)
                    if self.supports_early_termination:
                        logger.debug(
                            f"Hit known listing '{identifier}', "
                            f"stopping (newest-first order)"
                        )
                        break
                    continue

                # Full parse
                listing = self._parse_item(item)
                if listing and listing.identifier:
                    if listing.identifier in known_ids:
                        seen_known_ids.add(listing.identifier)
                        if self.supports_early_termination:
                            logger.debug(
                                f"Hit known listing '{listing.identifier}', "
                                f"stopping (newest-first order)"
                            )
                            break
                    else:
                        new_listings[listing.identifier] = listing

            if new_listings:
                logger.info(
                    f"Found {len(new_listings)} new listing(s) on {self.name}"
                )
            else:
                logger.debug(f"No new listings found on {self.name}")

        except requests.RequestException as exc:
            logger.error(f"Error fetching {self.name}: {exc}")
            raise

        return new_listings, seen_known_ids

    @abstractmethod
    def _fetch_raw_items(self) -> list:
        """
        Fetch raw items to process.

        Returns a list of raw items (API dicts, BeautifulSoup elements, URLs,
        etc.) that will be iterated by get_current_listings().

        Subclasses should handle session creation, HTTP requests, HTML parsing,
        and pagination in this method.
        """

    @abstractmethod
    def _parse_item(self, raw_item) -> Optional[Listing]:
        """
        Parse a single raw item into a Listing.

        Args:
            raw_item: A single element from the list returned by
                      _fetch_raw_items().

        Returns:
            Listing object or None if parsing fails.
        """

    def _extract_identifier_fast(self, raw_item) -> Optional[str]:
        """
        Quickly extract the listing identifier without full parsing.

        Override this method to enable fast early-termination checks
        before expensive full parsing. Returns None by default, which
        causes the template to fall through to full parsing.

        Args:
            raw_item: A single element from the list returned by
                      _fetch_raw_items().

        Returns:
            The listing identifier or None if not extractable.
        """
        return None

    def _get_borough_from_zip(self, zip_code: str) -> str:
        """
        Finds the borough for a given zip code.

        Args:
            zip_code: A 5-digit Berlin zip code.

        Returns:
            The borough name or "N/A" if not found.
        """
        if self.borough_resolver:
            return self.borough_resolver.get_borough_or_default(zip_code, "N/A")
        return "N/A"

    @staticmethod
    def _normalize_german_number(value_str: str) -> str:
        """
        Normalizes German number format to standard format.

        Converts German format (period as thousands, comma as decimal)
        to standard format (no thousands separator, period as decimal).

        Examples:
            '2.345' -> '2345' (thousands)
            '2.345,67' -> '2345.67' (thousands + decimal)
            '1.200' -> '1200'

        Args:
            value_str: Number string in German format

        Returns:
            Number string in standard format or original if not applicable
        """
        if not value_str or value_str == 'N/A':
            return value_str

        # German format uses period for thousands and comma for decimals
        # Remove thousands separators (periods) and convert decimal separator (comma to period)
        value_str = value_str.replace('.', '')  # Remove thousands separator
        value_str = value_str.replace(',', '.')  # Convert decimal separator

        return value_str

    @staticmethod
    def _normalize_rooms_format(value_str: str) -> str:
        """
        Normalizes room count format to use dot as decimal separator.

        Converts comma decimal separator to dot for consistent display
        (same format as prices).

        Examples:
            '2,5' -> '2.5' (comma to dot)
            '2.5' -> '2.5' (already correct)
            '3' -> '3' (whole number unchanged)

        Args:
            value_str: Room count string (may use dot or comma as decimal separator)

        Returns:
            Room count string with dot as decimal separator
        """
        if not value_str or value_str == 'N/A':
            return value_str

        # Replace comma with dot for decimal separator (same as prices)
        return value_str.replace(',', '.')

    @staticmethod
    def _clean_text(text: str) -> str:
        """
        Cleans text by removing extra whitespace and common units.

        Args:
            text: Raw text to clean.

        Returns:
            Cleaned text or 'N/A' if empty.
        """
        if not text:
            return "N/A"
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace('€', '').replace('m²', '').replace('VB', '').strip()
        if text.endswith('.') or text.endswith(','):
            text = text[:-1].strip()
        return text if text else "N/A"

    def __str__(self):
        return f"Scraper({self.name})"
