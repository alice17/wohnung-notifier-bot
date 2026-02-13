"""
Deutsche Wohnen Scraper.

This module defines the DeutscheWohnenScraper class for fetching apartment
listings from deutsche-wohnen.com via their internal API.

Features:
---------
- Uses the Deutsche Wohnen internal API with 'dataSet=deuwo' filter
- Fetches listings sorted by date (newest first via orderBy=date_asc)
- Uses early termination when encountering known listings
- Limits fetch to first batch only (live update mode)

Limitations:
-----------
- Warm rent (price_total) is NOT available from the API
- Therefore, price_total remains 'N/A' for all listings
"""
import logging
from typing import Optional

import requests

from src.core.listing import Listing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

LIVE_UPDATE_BATCH_SIZE = 50


class DeutscheWohnenScraper(BaseScraper):
    """
    Scraper for apartment listings from deutsche-wohnen.com.

    Uses the Deutsche Wohnen internal API to fetch Berlin apartment listings.
    """

    def __init__(self, name: str):
        """
        Initializes the Deutsche Wohnen scraper.

        Args:
            name: Display name for this scraper instance.
        """
        super().__init__(name)
        self.api_url = "https://www.deutsche-wohnen.com/api/deuwo-real-estate/list"
        self.base_url = "https://www.deutsche-wohnen.com"
        self.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
                "Referer": "https://www.deutsche-wohnen.com/",
                "DNT": "1",
            }
        )

    def _fetch_raw_items(self) -> list:
        """
        Fetches the first batch of listings from the Deutsche Wohnen API.

        Uses orderBy=date_asc which, despite the name, returns newest
        listings first (this is the value the website uses for "neuste
        zuerst" / newest first).

        Returns:
            List of listing dictionaries from the API, newest first.
        """
        session = requests.Session()
        session.headers.update(self.headers)
        return self._fetch_listings_batch(
            session, limit=LIVE_UPDATE_BATCH_SIZE, offset=0
        )

    def _extract_identifier_fast(self, listing_data: dict) -> Optional[str]:
        """
        Quickly extracts the listing identifier without full parsing.

        This enables early termination check before expensive full parsing.

        Args:
            listing_data: Dictionary containing listing data from API.

        Returns:
            The listing identifier (detail URL) or None if not found.
        """
        slug = listing_data.get("slug", "")
        if slug:
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

        return data.get("results", [])

    def _build_api_params(self, limit: int, offset: int) -> dict:
        """
        Builds API query parameters for fetching listings.

        Args:
            limit: Maximum number of results to return.
            offset: Starting offset for pagination.

        Returns:
            Dictionary of query parameters.
        """
        return {
            "rentType": "miete",
            "city": "Berlin",
            "immoType": "wohnung",
            "limit": str(limit),
            "offset": str(offset),
            "orderBy": "date_asc",
            "dataSet": "deuwo",
        }

    def _parse_item(self, listing_data: dict) -> Optional[Listing]:
        """
        Parses a single listing from the API response.

        Args:
            listing_data: Dictionary containing listing data from API.

        Returns:
            Listing object or None if parsing fails.
        """
        try:
            wrk_id = listing_data.get("wrk_id", "")
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
                wbs=False,
                identifier=link,
            )

        except Exception as exc:
            logger.debug(f"Error parsing listing: {exc}")
            return None

    def _build_address(self, listing_data: dict) -> str:
        """
        Builds the full address from listing data.

        Args:
            listing_data: Dictionary containing listing data.

        Returns:
            Formatted address string.
        """
        street = listing_data.get("strasse", "").strip()
        plz = listing_data.get("plz", "").strip()
        ort = listing_data.get("ort", "").strip()

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
        ort = listing_data.get("ort", "")
        if "OT" in ort:
            parts = ort.split("OT")
            if len(parts) > 1:
                return parts[1].strip()

        plz = listing_data.get("plz", "")
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
        price = listing_data.get("preis")
        if price:
            return str(price).strip()
        return "N/A"

    def _extract_sqm(self, listing_data: dict) -> str:
        """
        Extracts and formats the square meters.

        Args:
            listing_data: Dictionary containing listing data.

        Returns:
            Formatted square meters string or 'N/A'.
        """
        groesse = listing_data.get("groesse")
        if groesse:
            return str(groesse).strip()
        return "N/A"

    def _extract_rooms(self, listing_data: dict) -> str:
        """
        Extracts and formats the number of rooms.

        Args:
            listing_data: Dictionary containing listing data.

        Returns:
            Formatted room count string with dot decimal separator or 'N/A'.
        """
        rooms = listing_data.get("anzahl_zimmer")
        if rooms:
            return self._normalize_rooms_format(str(rooms).strip())
        return "N/A"

    def _build_listing_url(self, listing_data: dict) -> str:
        """
        Builds the detail page URL for a listing.

        The API returns a slug that already includes the wrk_id.

        Args:
            listing_data: Dictionary containing listing data.

        Returns:
            Full URL to the listing detail page.
        """
        slug = listing_data.get("slug", "")
        if slug:
            return f"{self.base_url}/mieten/mietangebote/{slug}"

        return "N/A"
