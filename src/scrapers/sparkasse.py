"""
Sparkasse Immobilien Scraper.

This module defines the SparkasseScraper class for fetching apartment
listings from immobilien.sparkasse.de.

Features:
---------
- Scrapes Berlin rental apartments from Sparkasse Immobilien portal
- Fetches detail pages for exact address extraction
- Extracts both cold rent (Nettokaltmiete) and warm rent (Warmmiete)
- Uses early termination when encountering known listings
"""
import logging
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

from src.core.listing import Listing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

DETAIL_PAGE_DELAY = 0.5


class SparkasseScraper(BaseScraper):
    """
    Scraper for apartment listings from immobilien.sparkasse.de.

    Fetches Berlin rental apartments and visits detail pages to extract
    exact addresses including street names.
    """

    def __init__(self, name: str):
        """
        Initializes the Sparkasse Immobilien scraper.

        Args:
            name: Display name for this scraper instance.
        """
        super().__init__(name)
        self.url = (
            "https://immobilien.sparkasse.de/immobilien/treffer"
            "?marketingType=rent"
            "&objectType=flat"
            "&perimeter=10"
            "&sortBy=date_desc"
            "&usageType=residential"
            "&zipCityEstateId=62422__Berlin"
        )
        self.base_url = "https://immobilien.sparkasse.de"
        self.headers.update(
            {
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8"
                ),
                "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://immobilien.sparkasse.de/",
                "DNT": "1",
            }
        )

    def _fetch_raw_items(self) -> list:
        """
        Fetches the search results page and returns listing URLs.

        Creates a session for reuse across detail page fetches.

        Returns:
            List of full listing URLs (strings).
        """
        self._active_session = requests.Session()
        self._active_session.headers.update(self.headers)

        response = self._active_session.get(self.url, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        links = self._extract_listing_links(soup)

        return [
            self.base_url + link if link.startswith("/") else link
            for link in links
        ]

    def _extract_identifier_fast(self, url: str) -> Optional[str]:
        """The raw item is already the URL/identifier."""
        return url

    def _parse_item(self, url: str) -> Optional[Listing]:
        """
        Fetches and parses a listing from its detail page.

        Args:
            url: Full URL to the listing detail page.

        Returns:
            Listing object or None if parsing fails.
        """
        listing = self._parse_listing_from_detail(url, self._active_session)
        if listing:
            time.sleep(DETAIL_PAGE_DELAY)
        return listing

    def _extract_listing_links(self, soup: BeautifulSoup) -> list[str]:
        """
        Extracts all listing links from the main search results page.

        Args:
            soup: BeautifulSoup object of the search results page.

        Returns:
            List of relative URLs to listing detail pages.
        """
        links = []
        expose_pattern = re.compile(r"/expose/[\w\-]+\.html")

        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "")
            if expose_pattern.match(href) and href not in links:
                links.append(href)

        return links

    def _parse_listing_from_detail(
        self, url: str, session: requests.Session
    ) -> Optional[Listing]:
        """
        Fetches and parses listing details from a detail page.

        Args:
            url: Full URL to the listing detail page.
            session: Active requests session.

        Returns:
            Listing object or None if parsing fails.
        """
        try:
            logger.debug(f"Fetching details from: {url}")
            response = session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            address = self._extract_address(soup)
            borough = self._extract_borough_from_soup(soup)
            price_cold = self._extract_price_cold(soup)
            price_total = self._extract_price_total(soup)
            sqm = self._extract_sqm(soup)
            rooms = self._extract_rooms(soup)

            return Listing(
                source=self.name,
                address=address,
                borough=borough,
                sqm=sqm,
                price_cold=price_cold,
                price_total=price_total,
                rooms=rooms,
                wbs=False,
                identifier=url,
            )

        except requests.exceptions.RequestException as exc:
            logger.error(f"Error fetching detail page {url}: {exc}")
            return None

    def _extract_address(self, soup: BeautifulSoup) -> str:
        """
        Extracts the full address from the detail page.

        Combines street, PLZ, and city from the Objektdaten section.

        Args:
            soup: BeautifulSoup object of the detail page.

        Returns:
            Formatted address string or 'N/A' if not found.
        """
        street = self._find_objektdaten_value(soup, "Straße")
        plz = self._find_objektdaten_value(soup, "PLZ")
        ort = self._find_objektdaten_value(soup, "Ort")

        if street and plz and ort:
            return f"{street}, {plz} {ort}"
        if plz and ort:
            return f"{plz} {ort}"

        address_elem = soup.find(
            string=lambda t: t and "Vollständige Adresse" not in t,
            attrs={"class": lambda c: c and "address" in str(c).lower()}
        )
        if address_elem:
            return address_elem.strip()

        return "N/A"

    def _find_objektdaten_value(self, soup: BeautifulSoup, label: str) -> str:
        """
        Finds a value in the Objektdaten section by its label.

        The Objektdaten section uses a definition list pattern where
        labels and values are siblings.

        Args:
            soup: BeautifulSoup object of the detail page.
            label: The label text to search for.

        Returns:
            The corresponding value or empty string if not found.
        """
        label_elem = soup.find(string=re.compile(rf"^\s*{label}\s*$"))
        if label_elem:
            parent = label_elem.find_parent()
            if parent:
                # Skip over <style> tags to find actual content sibling
                sibling = parent.find_next_sibling()
                while sibling and sibling.name == "style":
                    sibling = sibling.find_next_sibling()

                if sibling:
                    text = sibling.get_text(strip=True)
                    # Reject CSS content
                    if not self._is_css_content(text):
                        return text

        return ""

    def _extract_borough_from_soup(self, soup: BeautifulSoup) -> str:
        """
        Extracts the borough from the detail page using PLZ lookup.

        Args:
            soup: BeautifulSoup object of the detail page.

        Returns:
            Borough name or 'N/A' if not found.
        """
        plz = self._find_objektdaten_value(soup, "PLZ")
        if plz and len(plz) == 5:
            return self._get_borough_from_zip(plz)

        text_content = soup.get_text()
        zip_match = re.search(r"\b(1\d{4})\b", text_content)
        if zip_match:
            return self._get_borough_from_zip(zip_match.group(1))

        return "N/A"

    def _extract_price_cold(self, soup: BeautifulSoup) -> str:
        """
        Extracts the cold rent (Nettokaltmiete) from the detail page.

        Args:
            soup: BeautifulSoup object of the detail page.

        Returns:
            Normalized price string or 'N/A' if not found.
        """
        price_text = self._find_price_by_label(soup, "Nettokaltmiete")
        return self._parse_price(price_text)

    def _extract_price_total(self, soup: BeautifulSoup) -> str:
        """
        Extracts the warm rent (Warmmiete) from the detail page.

        Args:
            soup: BeautifulSoup object of the detail page.

        Returns:
            Normalized price string or 'N/A' if not found.
        """
        price_text = self._find_price_by_label(soup, "Warmmiete")
        return self._parse_price(price_text)

    def _find_price_by_label(self, soup: BeautifulSoup, label: str) -> str:
        """
        Finds a price value by its label text.

        Args:
            soup: BeautifulSoup object of the detail page.
            label: The label text (e.g., 'Nettokaltmiete', 'Warmmiete').

        Returns:
            Raw price text or empty string if not found.
        """
        label_elem = soup.find(string=re.compile(rf"^\s*{label}\s*$"))
        if label_elem:
            parent = label_elem.find_parent()
            if parent:
                # Skip over <style> tags to find actual content sibling
                sibling = parent.find_next_sibling()
                while sibling and sibling.name == "style":
                    sibling = sibling.find_next_sibling()

                if sibling:
                    # Remove any nested style tags
                    for style in sibling.find_all("style"):
                        style.decompose()

                    text = sibling.get_text(strip=True)

                    # Reject if it looks like CSS content
                    if self._is_css_content(text):
                        # Try extracting just numeric content with € symbol
                        price_match = re.search(
                            r"[\d.,]+\s*€", sibling.get_text(" ", strip=True)
                        )
                        if price_match:
                            return price_match.group(0)
                        return ""

                    return text

        return ""

    @staticmethod
    def _is_css_content(text: str) -> bool:
        """
        Checks if text appears to be CSS content rather than actual data.

        Args:
            text: Text to check.

        Returns:
            True if the text looks like CSS, False otherwise.
        """
        if not text:
            return False

        css_indicators = [
            "css-",
            "{margin:",
            "{padding:",
            "font-size:",
            "font-family:",
            "line-height:",
            "@media",
            "var(--",
        ]
        return any(indicator in text for indicator in css_indicators)

    def _extract_sqm(self, soup: BeautifulSoup) -> str:
        """
        Extracts the square meters from the detail page.

        Args:
            soup: BeautifulSoup object of the detail page.

        Returns:
            Normalized square meters string or 'N/A' if not found.
        """
        sqm_text = self._find_objektdaten_value(soup, "Wohnfläche")
        if sqm_text:
            cleaned = self._clean_text(sqm_text)
            return self._normalize_german_number(cleaned)

        return "N/A"

    def _extract_rooms(self, soup: BeautifulSoup) -> str:
        """
        Extracts the number of rooms from the detail page.

        Args:
            soup: BeautifulSoup object of the detail page.

        Returns:
            Normalized room count string or '1' if not found.
        """
        rooms_text = self._find_objektdaten_value(soup, "Anzahl Zimmer")
        if rooms_text:
            cleaned = self._clean_text(rooms_text)
            return self._normalize_rooms_format(cleaned)

        return "1"

    def _parse_price(self, price_text: str) -> str:
        """
        Parses and normalizes a price string.

        Removes currency symbol and normalizes German number format.

        Args:
            price_text: Raw price text (e.g., '1.800 €').

        Returns:
            Normalized price string or 'N/A' if empty or invalid.
        """
        if not price_text:
            return "N/A"

        # Reject CSS content that slipped through
        if self._is_css_content(price_text):
            return "N/A"

        cleaned = self._clean_text(price_text)

        # Ensure the result is actually a number
        if cleaned and cleaned != "N/A":
            normalized = self._normalize_german_number(cleaned)
            # Validate that result looks like a price (numeric)
            if normalized and re.match(r"^[\d.]+$", normalized):
                return normalized

        return "N/A"

    @staticmethod
    def _clean_text(text: Optional[str]) -> str:
        """
        Removes extra whitespace and common units from text.

        Args:
            text: Raw text string.

        Returns:
            Cleaned text or 'N/A' if empty.
        """
        if not text:
            return "N/A"

        text = re.sub(r"\s+", " ", text).strip()
        text = text.replace("€", "").replace("m²", "").strip()

        if text.endswith(".") or text.endswith(","):
            text = text[:-1].strip()

        return text if text else "N/A"
