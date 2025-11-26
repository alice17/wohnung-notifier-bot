"""
Base scraper for websites using the Wohnraumkarte.de API.

This module provides an abstract base class for scrapers that fetch listings
from the wohnraumkarte.de platform (used by Deutsche Wohnen, Vonovia, etc.).

Features:
---------
- Fetches listings sorted by date (newest first)
- Uses early termination when encountering known listings
- Limits fetch to first batch only (live update mode)
- Pure API-based approach (no HTML parsing required)

Limitations:
-----------
- Warm rent (price_total) is NOT available from the API
- Therefore, price_total remains 'N/A' for all listings
"""
import logging
from abc import abstractmethod
from typing import Dict, Optional, Set

import requests

from src.core.listing import Listing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Number of listings to fetch per request (optimized for live updates)
LIVE_UPDATE_BATCH_SIZE = 50


class WohnraumkarteScraper(BaseScraper):
    """
    Abstract base class for scrapers using the wohnraumkarte.de API.

    Subclasses must implement:
    - _get_listing_url_path(): Returns the URL path pattern for listings
    - _get_extra_api_params(): Returns any additional API parameters
    - _get_domain_name(): Returns the domain name for logging

    The base class handles all common logic for:
    - Fetching listings from the API
    - Parsing listing data
    - Early termination optimization
    - Address/borough/price extraction
    """

    def __init__(self, name: str, base_url: str, referer: str):
        """
        Initializes the Wohnraumkarte-based scraper.

        Args:
            name: Display name for this scraper instance.
            base_url: The base URL for building listing detail pages.
            referer: The referer header value for API requests.
        """
        super().__init__(name)
        self.api_url = "https://www.wohnraumkarte.de/api/getImmoList"
        self.base_url = base_url
        self.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
                "Referer": referer,
                "DNT": "1",
            }
        )

    @abstractmethod
    def _get_listing_url_path(self, slug: str, wrk_id: str) -> str:
        """
        Returns the URL path for a listing detail page.

        Args:
            slug: The URL-friendly listing slug.
            wrk_id: The wohnraumkarte listing ID.

        Returns:
            The path portion of the listing URL (without base URL).
        """
        raise NotImplementedError

    def _get_extra_api_params(self) -> dict:
        """
        Returns additional API parameters specific to this scraper.

        Override this method to add parameters like 'dataSet'.

        Returns:
            Dictionary of extra API parameters (empty by default).
        """
        return {}

    def _get_domain_name(self) -> str:
        """
        Returns the domain name for use in log messages.

        Returns:
            The domain name (e.g., 'vonovia.de').
        """
        return self.base_url.replace("https://www.", "").replace("https://", "")

    def get_current_listings(
        self, known_listings: Optional[Dict[str, Listing]] = None
    ) -> Dict[str, Listing]:
        """
        Fetches apartment listings from the API (optimized for live updates).

        Only fetches the first batch of listings sorted by date descending.
        Implements early termination when a known listing is encountered,
        since all subsequent listings would also be known.

        Args:
            known_listings: Previously seen listings for early termination.

        Returns:
            Dictionary mapping identifiers to Listing objects (new listings only).

        Raises:
            requests.exceptions.RequestException: If the HTTP request fails.
        """
        known_ids: Set[str] = set(known_listings.keys()) if known_listings else set()
        listings_data: Dict[str, Listing] = {}
        session = requests.Session()
        session.headers.update(self.headers)

        try:
            batch_listings = self._fetch_listings_batch(
                session, limit=LIVE_UPDATE_BATCH_SIZE, offset=0
            )
            domain = self._get_domain_name()
            logger.debug(f"Fetched {len(batch_listings)} listings from {domain} API.")

            new_count = 0
            for listing_data in batch_listings:
                identifier = self._extract_identifier_fast(listing_data)

                if identifier and identifier in known_ids:
                    logger.debug(
                        f"Hit known listing '{identifier}', stopping (newest-first order)"
                    )
                    break

                listing = self._parse_listing(listing_data)
                if listing and listing.identifier:
                    listings_data[listing.identifier] = listing
                    new_count += 1

            if new_count > 0:
                logger.info(f"Found {new_count} new listing(s) on {domain}")
            else:
                logger.debug(f"No new listings found on {domain}")

        except requests.exceptions.RequestException as exc:
            logger.error(
                f"An error occurred during the request for {self.api_url}: {exc}"
            )
            raise

        return listings_data

    def _extract_identifier_fast(self, listing_data: dict) -> Optional[str]:
        """
        Quickly extracts the listing identifier without full parsing.

        This enables early termination check before expensive full parsing.

        Args:
            listing_data: Dictionary containing listing data from API.

        Returns:
            The listing identifier (detail URL) or None if not found.
        """
        slug = listing_data.get('slug', '')
        wrk_id = listing_data.get('wrk_id', '')
        if slug and wrk_id:
            return self._build_listing_url(listing_data)
        return None

    def _fetch_listings_batch(
        self, session: requests.Session, limit: int, offset: int
    ) -> list:
        """
        Fetches a batch of listings from the API.

        Args:
            session: Active requests session.
            limit: Maximum number of listings to fetch.
            offset: Starting offset for pagination.

        Returns:
            List of listing dictionaries from the API.
        """
        params = self._build_api_params(limit=limit, offset=offset)

        response = session.get(self.api_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        return data.get('results', [])

    def _build_api_params(self, limit: int, offset: int) -> dict:
        """
        Builds API query parameters for fetching listings.

        Args:
            limit: Maximum number of results to return.
            offset: Starting offset for pagination.

        Returns:
            Dictionary of query parameters.
        """
        params = {
            'rentType': 'miete',
            'city': 'Berlin',
            'immoType': 'wohnung',
            'limit': str(limit),
            'offset': str(offset),
            'orderBy': 'date_desc',
        }
        params.update(self._get_extra_api_params())
        return params

    def _parse_listing(self, listing_data: dict) -> Optional[Listing]:
        """
        Parses a single listing from the API response.

        Args:
            listing_data: Dictionary containing listing data from API.

        Returns:
            Listing object or None if parsing fails.
        """
        try:
            wrk_id = listing_data.get('wrk_id', '')
            if not wrk_id:
                logger.warning("Skipping listing without wrk_id")
                return None

            address = self._build_address(listing_data)
            borough = self._extract_borough(listing_data)
            price_cold = self._extract_price(listing_data)
            sqm = self._extract_sqm(listing_data)
            rooms = self._extract_rooms(listing_data)
            link = self._build_listing_url(listing_data)

            return Listing(
                source=self.name,
                address=address,
                borough=borough,
                sqm=sqm,
                price_cold=price_cold,
                rooms=rooms,
                link=link,
                identifier=link,
            )

        except Exception as exc:
            logger.error(f"Error parsing listing: {exc}")
            return None

    def _build_address(self, listing_data: dict) -> str:
        """
        Builds the full address from listing data.

        Args:
            listing_data: Dictionary containing listing data.

        Returns:
            Formatted address string.
        """
        street = listing_data.get('strasse', '').strip()
        plz = listing_data.get('plz', '').strip()
        ort = listing_data.get('ort', '').strip()

        if street and plz and ort:
            return f"{street}, {plz} {ort}"
        if plz and ort:
            return f"{plz} {ort}"
        if street:
            return street

        return "N/A"

    def _extract_borough(self, listing_data: dict) -> str:
        """
        Extracts borough from listing data.

        Args:
            listing_data: Dictionary containing listing data.

        Returns:
            Borough name or 'N/A' if not found.
        """
        # Try to extract from 'ort' field (e.g., "Berlin OT Wedding")
        ort = listing_data.get('ort', '')
        if 'OT' in ort:
            parts = ort.split('OT')
            if len(parts) > 1:
                return parts[1].strip()

        # Fallback to ZIP code lookup
        plz = listing_data.get('plz', '')
        if plz:
            return self._get_borough_from_zip(plz)

        return "N/A"

    def _extract_price(self, listing_data: dict) -> str:
        """
        Extracts and formats the cold rent price.

        Args:
            listing_data: Dictionary containing listing data.

        Returns:
            Formatted price string or 'N/A'.
        """
        price = listing_data.get('preis')
        if price:
            return str(price).strip()
        return 'N/A'

    def _extract_sqm(self, listing_data: dict) -> str:
        """
        Extracts and formats the square meters.

        Args:
            listing_data: Dictionary containing listing data.

        Returns:
            Formatted square meters string or 'N/A'.
        """
        groesse = listing_data.get('groesse')
        if groesse:
            return str(groesse).strip()
        return 'N/A'

    def _extract_rooms(self, listing_data: dict) -> str:
        """
        Extracts and formats the number of rooms.

        The API returns rooms with dot decimal separator (e.g., "2.5"),
        which is the standard format (same as prices).

        Args:
            listing_data: Dictionary containing listing data.

        Returns:
            Formatted room count string with dot decimal separator or '1'.
        """
        rooms = listing_data.get('anzahl_zimmer')
        if rooms:
            return self._normalize_rooms_format(str(rooms).strip())
        return '1'

    def _build_listing_url(self, listing_data: dict) -> str:
        """
        Builds the detail page URL for a listing.

        Args:
            listing_data: Dictionary containing listing data.

        Returns:
            Full URL to the listing detail page.
        """
        slug = listing_data.get('slug', '')
        wrk_id = listing_data.get('wrk_id', '')

        if slug and wrk_id:
            path = self._get_listing_url_path(slug, wrk_id)
            return f"{self.base_url}{path}"

        return 'N/A'

