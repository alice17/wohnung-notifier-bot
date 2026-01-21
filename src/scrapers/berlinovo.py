"""
Berlinovo Scraper.

This module defines the BerlinovoScraper class for fetching apartment
listings from berlinovo.de.

Features:
---------
- Scrapes apartment listings from Berlin's state-owned housing company
- Extracts warm rent, cold rent, rooms, sqm, WBS status
- Handles pagination if needed

Limitations:
-----------
- No creation date sorting available on the website
- Cannot use early termination optimization (must parse all listings)
- Availability date sorting is available but not insertion date
"""
import logging
import re
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup

from src.core.listing import Listing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class BerlinovoScraper(BaseScraper):
    """
    Scraper for apartment listings from berlinovo.de.

    Note: This scraper does not use early termination because berlinovo.de
    does not support sorting by listing creation date. All listings are
    parsed on each run.
    """

    BASE_URL = "https://www.berlinovo.de"
    SEARCH_URL = f"{BASE_URL}/de/wohnungen/suche"

    def __init__(self, name: str):
        """
        Initializes the Berlinovo scraper.

        Args:
            name: Display name for this scraper instance.
        """
        super().__init__(name)
        self.url = self.SEARCH_URL

    def get_current_listings(
        self, known_listings: Optional[Dict[str, Listing]] = None
    ) -> Dict[str, Listing]:
        """
        Fetches all apartment listings from berlinovo.de.

        Note: Early termination is NOT used because the website does not
        support sorting by insertion date. All listings are parsed each run.

        Args:
            known_listings: Previously seen listings (used for filtering only).

        Returns:
            Dictionary mapping identifiers to Listing objects (new listings only).

        Raises:
            requests.exceptions.RequestException: If the HTTP request fails.
        """
        known_ids = set(known_listings.keys()) if known_listings else set()
        all_listings: Dict[str, Listing] = {}

        try:
            page = 0
            while True:
                page_listings = self._fetch_page(page)

                if not page_listings:
                    break

                # Filter to only new listings
                new_on_page = {
                    lid: listing
                    for lid, listing in page_listings.items()
                    if lid not in known_ids
                }
                all_listings.update(new_on_page)

                # Check if there might be more pages
                if len(page_listings) < 10:
                    break

                page += 1

            if all_listings:
                logger.info(f"Found {len(all_listings)} new listing(s) on berlinovo.de")
            else:
                logger.debug("No new listings found on berlinovo.de")

            return all_listings

        except requests.exceptions.RequestException as exc:
            logger.error(f"Error fetching berlinovo.de: {exc}")
            raise

    def _fetch_page(self, page: int = 0) -> Dict[str, Listing]:
        """
        Fetches a single page of listings.

        Args:
            page: Page number (0-indexed).

        Returns:
            Dictionary of listings found on the page.
        """
        params = {
            "sort": "field_available_date",
            "order": "desc",
        }

        if page > 0:
            params["page"] = str(page)

        response = requests.get(
            self.url, headers=self.headers, params=params, timeout=20
        )
        response.raise_for_status()

        return self._parse_html(response.text)

    def _parse_html(self, html_content: str) -> Dict[str, Listing]:
        """
        Parses HTML content and extracts listings.

        Args:
            html_content: Raw HTML content from the page.

        Returns:
            Dictionary mapping identifiers to Listing objects.
        """
        soup = BeautifulSoup(html_content, "lxml")
        listings_data: Dict[str, Listing] = {}

        # Find all listing articles/cards on the page
        listing_cards = soup.select("article.node--type-wohnung")

        if not listing_cards:
            # Try alternative selector for the listing container
            listing_cards = soup.select(".view-wohnungssuche .views-row")

        if not listing_cards:
            # Fallback: look for any teaser-style containers
            listing_cards = soup.select("[class*='teaser'], [class*='listing']")

        if not listing_cards:
            logger.warning("Could not find listing cards on berlinovo.de")
            return {}

        for card in listing_cards:
            listing = self._parse_listing_card(card)
            if listing and listing.identifier:
                listings_data[listing.identifier] = listing

        return listings_data

    def _parse_listing_card(self, card: BeautifulSoup) -> Optional[Listing]:
        """
        Parses a single listing card and extracts details.

        Args:
            card: BeautifulSoup element representing a listing card.

        Returns:
            Listing object or None if parsing fails.
        """
        try:
            # Extract the link to the detail page (identifier)
            link_elem = card.select_one("a[href*='/de/wohnung/']")
            if not link_elem:
                link_elem = card.select_one("a[href]")

            identifier = None
            if link_elem and link_elem.get("href"):
                href = link_elem["href"]
                if href.startswith("/"):
                    identifier = f"{self.BASE_URL}{href}"
                elif href.startswith("http"):
                    identifier = href

            if not identifier:
                logger.debug("Skipping listing without valid URL")
                return None

            # Extract address
            address = self._extract_address(card)
            borough = self._extract_borough_from_address(address)

            # Extract rent prices
            price_total = self._extract_field_value(card, ["Warmmiete", "warmmiete"])
            price_cold = self._extract_field_value(
                card, ["Bruttokaltmiete", "Kaltmiete", "kaltmiete"]
            )

            # Extract rooms
            rooms = self._extract_field_value(card, ["Zimmer", "zimmer"])
            if rooms:
                rooms = self._normalize_rooms_format(rooms.replace(",", "."))

            # Extract square meters
            sqm = self._extract_field_value(card, ["Wohnfläche", "wohnfläche", "m²"])

            # Check for WBS requirement
            wbs = self._check_wbs(card)

            return Listing(
                source=self.name,
                address=address,
                borough=borough,
                sqm=self._clean_numeric(sqm),
                price_cold=self._clean_numeric(price_cold),
                price_total=self._clean_numeric(price_total),
                rooms=rooms if rooms else "N/A",
                wbs=wbs,
                identifier=identifier,
            )

        except (AttributeError, KeyError, ValueError, TypeError) as exc:
            logger.error(f"Error parsing listing card: {exc}")
            return None

    def _extract_address(self, card: BeautifulSoup) -> str:
        """
        Extracts address from a listing card.

        Args:
            card: BeautifulSoup element representing a listing card.

        Returns:
            Address string or 'N/A' if not found.
        """
        # Try common address selectors
        address_selectors = [
            ".field--name-field-adresse",
            ".field--name-field-address",
            "[class*='address']",
            ".location",
        ]

        for selector in address_selectors:
            elem = card.select_one(selector)
            if elem:
                return self._clean_text(elem.get_text())

        # Look for text containing Berlin postal code pattern
        text = card.get_text()
        match = re.search(
            r"([A-Za-zäöüßÄÖÜ\s\-\.]+\s+\d+[a-zA-Z]?\s*,?\s*\d{5}\s+Berlin)",
            text,
            re.IGNORECASE,
        )
        if match:
            return self._clean_text(match.group(1))

        # Try to find street and postal code separately
        street_match = re.search(r"([A-Za-zäöüßÄÖÜ\-\.]+(?:straße|str\.|weg|platz|allee|ring|damm)\s+\d+[a-zA-Z]?)", text, re.IGNORECASE)
        zip_match = re.search(r"(\d{5})\s*Berlin", text)

        if street_match and zip_match:
            return f"{street_match.group(1)}, {zip_match.group(1)} Berlin"

        if zip_match:
            return f"{zip_match.group(1)} Berlin"

        return "N/A"

    def _extract_borough_from_address(self, address: str) -> str:
        """
        Extracts borough from address using ZIP code.

        Args:
            address: Full address string.

        Returns:
            Borough name or 'N/A' if not found.
        """
        zip_match = re.search(r"\b(\d{5})\b", address)
        if zip_match:
            return self._get_borough_from_zip(zip_match.group(1))
        return "N/A"

    def _extract_field_value(
        self, card: BeautifulSoup, field_names: list
    ) -> Optional[str]:
        """
        Extracts a field value by looking for labels.

        Args:
            card: BeautifulSoup element to search in.
            field_names: List of possible field label names.

        Returns:
            Field value or None if not found.
        """
        text = card.get_text(separator="\n")
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        for i, line in enumerate(lines):
            for field_name in field_names:
                if field_name.lower() in line.lower():
                    # Check if value is on the same line after the label
                    after_label = line.split(field_name)[-1].strip()
                    after_label = after_label.lstrip(":").strip()
                    if after_label:
                        return after_label

                    # Check the next line
                    if i + 1 < len(lines):
                        return lines[i + 1]

        return None

    def _check_wbs(self, card: BeautifulSoup) -> bool:
        """
        Checks if the listing requires WBS.

        Args:
            card: BeautifulSoup element representing a listing card.

        Returns:
            True if WBS is required, False otherwise.
        """
        text = card.get_text().lower()
        return "wbs" in text and (
            "erforderlich" in text
            or "wbs-wohnung" in text
            or "wbs nötig" in text
        )

    def _clean_numeric(self, value: Optional[str]) -> str:
        """
        Cleans a numeric value string.

        Args:
            value: Raw value string.

        Returns:
            Cleaned numeric string or 'N/A'.
        """
        if not value:
            return "N/A"

        # Remove currency symbols and units
        cleaned = value.replace("€", "").replace("m²", "").strip()

        # Extract the numeric part
        match = re.search(r"[\d.,]+", cleaned)
        if match:
            number_str = match.group()
            return self._normalize_german_number(number_str)

        return "N/A"

    @staticmethod
    def _clean_text(text: Optional[str]) -> str:
        """
        Cleans text by removing extra whitespace.

        Args:
            text: Raw text to clean.

        Returns:
            Cleaned text or 'N/A' if empty.
        """
        if not text:
            return "N/A"
        cleaned = re.sub(r"\s+", " ", text).strip()
        return cleaned if cleaned else "N/A"
