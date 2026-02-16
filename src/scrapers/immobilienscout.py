"""
ImmobilienScout24 Scraper.

This module defines the ImmobilienScoutScraper class for fetching apartment
listings from ImmobilienScout24 using the mobile API.

Features:
---------
- Uses the ImmobilienScout24 mobile API directly
- Searches for rental apartments in Berlin (configurable region)
- Extracts warm rent, cold rent, rooms, sqm, address
- Supports pagination for complete listing retrieval

Limitations:
-----------
- API responses may vary, some fields might not always be available
- Rate limiting may apply from ImmobilienScout24
- Cannot determine WBS status from API (defaults to False)
"""
import logging
import re
from typing import Any, Dict, List, Optional

import requests

from src.core.listing import Listing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class ImmobilienScoutScraper(BaseScraper):
    """
    Scraper for apartment listings from ImmobilienScout24.

    Uses the ImmobilienScout24 mobile API directly for reliable access.
    Requests results sorted by activation date (newest first); early
    termination is used when a known listing is encountered.
    """

    BASE_URL = "https://www.immobilienscout24.de"
    API_URL = "https://api.mobile.immobilienscout24.de"
    REGION = "/de/berlin/berlin"
    # Sort by first activation date, newest first (see flathunter SORTING_MAP)
    SORT_NEWEST_FIRST = "-firstactivation"
    # User-Agent format from mobile app (see: github.com/orangecoding/fredy)
    USER_AGENT = "ImmoScout_27.12_26.2_._"

    def __init__(self, name: str):
        """
        Initializes the ImmobilienScout24 scraper.

        Args:
            name: Display name for this scraper instance.
        """
        super().__init__(name)
        self.url = f"{self.BASE_URL}/Suche{self.REGION}"
        self._session: Optional[requests.Session] = None

    @property
    def session(self) -> requests.Session:
        """
        Lazy initialization of the requests session.

        Returns:
            Configured requests.Session instance.
        """
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": self.USER_AGENT,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Connection": "keep-alive",
            })
        return self._session

    def _fetch_raw_items(self) -> list:
        """
        Fetches the first page of listings from the ImmobilienScout24 API.

        Returns:
            List of listing item dictionaries (excluding ads).
        """
        results = self._fetch_page(1)
        if not results:
            return []

        total_results = results.get("totalResults", "unknown")
        page_size = results.get("pageSize", "unknown")
        logger.debug(
            f"ImmobilienScout24 API returned {total_results} total results "
            f"(page size: {page_size})"
        )

        return self._extract_listing_items(results)

    def _extract_identifier_fast(self, item: Dict[str, Any]) -> Optional[str]:
        """
        Quickly extracts the expose URL without full parsing.

        Avoids expensive detail-page fetches for known listings.

        Args:
            item: Dictionary containing listing data from API.

        Returns:
            The listing URL or None if ID not found.
        """
        data = item
        if "item" in data and isinstance(data.get("item"), dict):
            data = data["item"]

        real_estate = (
            data.get("resultlist.realEstate")
            or data.get("realEstate")
            or data.get("listing")
            or data
        )
        expose_id = (
            data.get("@id")
            or data.get("id")
            or data.get("listingId")
            or data.get("exposeId")
            or real_estate.get("@id")
            or real_estate.get("id")
            or real_estate.get("listingId")
        )
        if expose_id:
            return f"{self.BASE_URL}/expose/{expose_id}"
        return None

    def _fetch_page(self, page_number: int = 1) -> Dict[str, Any]:
        """
        Fetches a single page of search results from the mobile API.

        Args:
            page_number: Page number (1-indexed).

        Returns:
            API response dictionary.

        Raises:
            requests.RequestException: If the request fails.
        """
        params = {
            "pricetype": "calculatedtotalrent",
            "realestatetype": "apartmentrent",
            "searchType": "region",
            "geocodes": self.REGION,
            "pagenumber": page_number,
            "sorting": self.SORT_NEWEST_FIRST,
        }

        # Required payload for the mobile API
        payload = {
            "supportedREsultListType": [],
            "userData": {},
        }

        response = self.session.post(
            f"{self.API_URL}/search/list",
            params=params,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _extract_listing_items(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extracts listing items from API response.

        The API response structure may vary, so this method handles
        different possible structures. Filters out advertisements by
        only including items with type 'EXPOSE_RESULT'.

        Args:
            results: Raw API response dictionary.

        Returns:
            List of listing item dictionaries (excluding ads).
        """
        items: List[Dict[str, Any]] = []

        # Current API structure (2024+)
        if "resultListItems" in results:
            items = results["resultListItems"]
        # Try different possible paths in the response
        elif "searchResponseModel" in results:
            search_response = results["searchResponseModel"]
            if "resultlist.resultlist" in search_response:
                result_list = search_response["resultlist.resultlist"]
                if "resultlistEntries" in result_list:
                    entries = result_list["resultlistEntries"]
                    if entries and len(entries) > 0:
                        items = entries[0].get("resultlistEntry", [])
        # Fallback: try direct access
        elif "resultlistEntry" in results:
            items = results["resultlistEntry"]
        # Another fallback structure
        elif "results" in results:
            items = results["results"]
        else:
            logger.debug(f"Unknown API response structure: {list(results.keys())}")
            return []

        # Filter to only include actual listings (exclude advertisements)
        # The mobile API returns items with type 'EXPOSE_RESULT' for real listings
        filtered_items = [
            item for item in items
            if item.get("type") == "EXPOSE_RESULT" or "type" not in item
        ]

        if len(filtered_items) < len(items):
            logger.debug(
                f"Filtered out {len(items) - len(filtered_items)} non-listing items (ads)"
            )

        return filtered_items

    def _fetch_expose_details(self, expose_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches detailed information for a single listing from the expose API.

        Uses the endpoint: GET /expose/{id}

        Args:
            expose_id: The expose ID (numeric ID, not the full URL).

        Returns:
            Expose detail dictionary or None if the request fails.
        """
        try:
            response = self.session.get(
                f"{self.API_URL}/expose/{expose_id}",
                timeout=15,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.debug(f"Failed to fetch expose details for {expose_id}: {exc}")
            return None

    # Company names to exclude (apartment swap services, not real listings)
    BLOCKED_AGENTS = [
        "tauschwohnung gmbh",
        "wohnungsswap.de - relocasa ab -",
    ]

    def _is_blocked_agent(self, expose: Dict[str, Any]) -> bool:
        """
        Checks whether the listing belongs to a blocked agent.

        Inspects the ``AGENTS_INFO`` section of the expose detail response
        and compares the ``company`` field against a blocklist of swap
        services that are not real rental listings.

        Args:
            expose: Expose detail response dictionary.

        Returns:
            True if the listing agent is on the blocklist, False otherwise.
        """
        for section in expose.get("sections", []):
            if section.get("type") == "AGENTS_INFO":
                company = (section.get("company") or "").lower()
                for blocked in self.BLOCKED_AGENTS:
                    if blocked in company:
                        return True
        return False

    def _extract_warm_rent_from_expose(self, expose: Dict[str, Any]) -> str:
        """
        Extracts the warm rent (total rent) from an expose detail response.

        The expose detail API returns a ``sections`` array. The warm rent can
        be found in:

        1. A ``COST_CHECK`` section with a numeric ``totalRent`` field
           (most reliable).
        2. A ``Kosten`` ``ATTRIBUTE_LIST`` section containing a
           "Gesamtmiete:" text attribute.

        Args:
            expose: Expose detail response dictionary.

        Returns:
            Warm rent as a formatted price string, or 'N/A' if not found.
        """
        sections = expose.get("sections", [])

        # 1. Try COST_CHECK section – has a numeric totalRent field
        for section in sections:
            if section.get("type") == "COST_CHECK":
                total_rent = section.get("totalRent")
                if total_rent is not None:
                    return self._format_price(total_rent)

        # 2. Fallback: look for "Gesamtmiete:" in the Kosten ATTRIBUTE_LIST
        for section in sections:
            if (
                section.get("type") == "ATTRIBUTE_LIST"
                and section.get("title") == "Kosten"
            ):
                for attr in section.get("attributes", []):
                    if "Gesamtmiete" in (attr.get("label") or ""):
                        return self._parse_german_price(attr.get("text", ""))

        return "N/A"

    @staticmethod
    def _parse_german_price(text: str) -> str:
        """
        Parses a German-formatted price string like ``1.388,40 €`` into a
        plain numeric string like ``1388.4``.

        Args:
            text: German price string (e.g. "1.388,40 €").

        Returns:
            Numeric price string or 'N/A' if parsing fails.
        """
        cleaned = (
            text.replace("€", "")
            .replace("\xa0", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )
        try:
            return str(round(float(cleaned), 2))
        except ValueError:
            return "N/A"

    def is_listing_active(self, expose_id: str) -> Optional[bool]:
        """
        Checks if a listing is still active on ImmobilienScout24.

        Uses the expose endpoint to verify if the listing still exists.

        Args:
            expose_id: The expose ID (not the full URL).

        Returns:
            True if active, False if not found (404), None if unknown status.
        """
        try:
            response = self.session.get(
                f"{self.API_URL}/expose/{expose_id}",
                timeout=10,
            )

            if response.status_code == 200:
                return True
            if response.status_code == 404:
                return False

            logger.warning(
                f"Unknown status {response.status_code} for listing {expose_id}"
            )
            return None

        except requests.RequestException as exc:
            logger.warning(f"Error checking listing {expose_id}: {exc}")
            return None

    def _parse_item(self, item: Dict[str, Any]) -> Optional[Listing]:
        """
        Parses a single listing item from the API response.

        Args:
            item: Dictionary containing listing data from API.

        Returns:
            Listing object or None if parsing fails.
        """
        try:
            # Handle wrapped structure: {'type': ..., 'item': {...}}
            if "item" in item and isinstance(item.get("item"), dict):
                item = item["item"]

            # Extract the real estate data - try multiple possible structures
            real_estate = (
                item.get("resultlist.realEstate")
                or item.get("realEstate")
                or item.get("listing")
                or item
            )

            # Build the listing URL (identifier) - try multiple ID field names
            expose_id = (
                item.get("@id")
                or item.get("id")
                or item.get("listingId")
                or item.get("exposeId")
                or real_estate.get("@id")
                or real_estate.get("id")
                or real_estate.get("listingId")
            )
            if not expose_id:
                logger.debug(f"Skipping listing without ID. Keys: {list(item.keys())}")
                return None

            identifier = f"{self.BASE_URL}/expose/{expose_id}"

            # Extract address (API uses 'line' field)
            address = self._extract_address(real_estate)
            borough = self._extract_borough(real_estate, address)

            # Extract attributes from the 'attributes' array
            # Format: [{"label": "", "value": "2.440 €"}, {"label": "", "value": "137 m²"}, {"label": "", "value": "4 Zi."}]
            attributes = real_estate.get("attributes", [])
            price_cold, sqm, rooms = self._parse_attributes(attributes)

            # Fetch warm rent from the expose details endpoint
            price_total = "N/A"
            if expose_id:
                expose_details = self._fetch_expose_details(str(expose_id))
                if expose_details:
                    if self._is_blocked_agent(expose_details):
                        logger.debug(
                            f"Skipping listing {expose_id}: blocked agent (swap service)"
                        )
                        return None
                    price_total = self._extract_warm_rent_from_expose(expose_details)

            # WBS status - not typically available in API, default to False
            wbs = False

            return Listing(
                source=self.name,
                address=address,
                borough=borough,
                sqm=sqm,
                price_cold=price_cold,
                price_total=price_total,
                rooms=rooms,
                wbs=wbs,
                identifier=identifier,
            )

        except (KeyError, TypeError, ValueError) as exc:
            logger.debug(f"Error parsing listing: {exc}")
            return None

    def _parse_attributes(self, attributes: List[Dict[str, Any]]) -> tuple:
        """
        Parses the attributes array to extract price, sqm, and rooms.

        The API returns attributes as:
        [{"label": "", "value": "2.440 €"}, {"label": "", "value": "137 m²"}, {"label": "", "value": "4 Zi."}]

        Args:
            attributes: List of attribute dictionaries.

        Returns:
            Tuple of (price_total, sqm, rooms) as strings.
        """
        price_total = "N/A"
        sqm = "N/A"
        rooms = "N/A"

        for attr in attributes:
            value = attr.get("value", "")
            if not value:
                continue

            # Price: contains € symbol
            if "€" in value:
                # Clean: "2.440 €" -> "2440"
                price_str = value.replace("€", "").replace("\xa0", "").replace(".", "").replace(",", ".").strip()
                try:
                    price_total = str(round(float(price_str), 2))
                except ValueError:
                    price_total = price_str

            # Square meters: contains m²
            elif "m²" in value:
                # Clean: "137 m²" -> "137"
                sqm_str = value.replace("m²", "").replace("\xa0", "").replace(",", ".").strip()
                try:
                    sqm = str(round(float(sqm_str), 2))
                except ValueError:
                    sqm = sqm_str

            # Rooms: contains "Zi." or just a number
            elif "Zi" in value:
                # Clean: "4 Zi." -> "4"
                rooms_str = value.replace("Zi.", "").replace("Zi", "").replace("\xa0", "").replace(",", ".").strip()
                try:
                    rooms_float = float(rooms_str)
                    if rooms_float == int(rooms_float):
                        rooms = str(int(rooms_float))
                    else:
                        rooms = str(rooms_float)
                except ValueError:
                    rooms = rooms_str

        return price_total, sqm, rooms

    def _extract_address(self, real_estate: Dict[str, Any]) -> str:
        """
        Extracts the address from listing data.

        Args:
            real_estate: Real estate data dictionary.

        Returns:
            Formatted address string or 'N/A'.
        """
        address_obj = real_estate.get("address", {})

        # API uses 'line' field with full address: "Falkenberger Straße 143 g, 13088 Berlin, Weißensee"
        if address_obj.get("line"):
            return address_obj["line"]

        # Fallback to structured fields
        street = address_obj.get("street") or address_obj.get("streetName") or ""
        house_number = address_obj.get("houseNumber") or address_obj.get("streetNumber") or ""
        postcode = address_obj.get("postcode") or address_obj.get("zipCode") or ""
        city = address_obj.get("city") or "Berlin"
        quarter = address_obj.get("quarter") or address_obj.get("district") or ""

        parts = []
        if street:
            street_part = f"{street} {house_number}".strip() if house_number else street
            parts.append(street_part)

        if postcode or city:
            location = f"{postcode} {city}".strip()
            if quarter and quarter not in location:
                location = f"{location} ({quarter})"
            parts.append(location)

        if parts:
            return ", ".join(parts)

        return "N/A"

    def _extract_borough(
        self, real_estate: Dict[str, Any], address: str
    ) -> str:
        """
        Extracts the borough from listing data.

        Args:
            real_estate: Real estate data dictionary.
            address: Already extracted address string.

        Returns:
            Borough name or 'N/A'.
        """
        # Try to extract zip from address string (e.g., "..., 13088 Berlin, Weißensee")
        zip_match = re.search(r"\b(\d{5})\b", address)
        if zip_match:
            return self._get_borough_from_zip(zip_match.group(1))

        # Fallback to structured address fields
        address_obj = real_estate.get("address", {})
        postcode = address_obj.get("postcode") or address_obj.get("zipCode") or ""
        if postcode:
            return self._get_borough_from_zip(str(postcode))

        return "N/A"

    def _format_price(self, value: Any) -> str:
        """Formats a price value to string."""
        try:
            return str(round(float(value), 2))
        except (ValueError, TypeError):
            return str(value)

    def _extract_rooms(self, real_estate: Dict[str, Any]) -> str:
        """
        Extracts room count from listing data.

        Args:
            real_estate: Real estate data dictionary.

        Returns:
            Room count as string or 'N/A'.
        """
        # Try multiple field names
        for field in ["numberOfRooms", "rooms", "roomCount", "noRooms"]:
            rooms = real_estate.get(field)
            if rooms is not None:
                try:
                    rooms_float = float(rooms)
                    if rooms_float == int(rooms_float):
                        return str(int(rooms_float))
                    return str(rooms_float)
                except (ValueError, TypeError):
                    return str(rooms)

        return "N/A"

    def _extract_sqm(self, real_estate: Dict[str, Any]) -> str:
        """
        Extracts square meters from listing data.

        Args:
            real_estate: Real estate data dictionary.

        Returns:
            Square meters as string or 'N/A'.
        """
        # Try multiple field names
        for field in ["livingSpace", "area", "size", "squareMeters", "livingArea"]:
            sqm = real_estate.get(field)
            if sqm is not None:
                try:
                    return str(round(float(sqm), 2))
                except (ValueError, TypeError):
                    return str(sqm)

        return "N/A"

