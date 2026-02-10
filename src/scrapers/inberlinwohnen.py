"""
This module defines the InBerlinWohnenScraper class.

InBerlinWohnen Scraper (Optimized for Live Updates)
===================================================

This scraper fetches apartment listings from inberlinwohnen.de, the official
portal for Berlin's state-owned housing companies (Landeseigene).

Optimization Strategy:
---------------------
The scraper is optimized for live updates by:
1. Only fetching the first page (10 listings, sorted newest first by default)
2. Using early termination when encountering known listings
3. Extracting apartment IDs before full parsing to skip known items
4. Minimal parsing overhead for already-seen apartments

Note: The site uses Laravel Livewire with encrypted state, so there's no
public JSON API. HTML parsing is required but optimized.
"""
import logging
import re
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup

from src.core.listing import Listing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class InBerlinWohnenScraper(BaseScraper):
    """
    Handles fetching and parsing of apartment listings from inberlinwohnen.de.
    
    Optimized for live updates: only processes first page (newest first)
    and implements early termination when known listings are encountered.
    """
    
    LISTINGS_CONTAINER_SELECTOR = r"div[wire\:loading\.remove]"
    LISTING_ITEM_SELECTOR = r"div[id^='apartment-']"

    def __init__(self, name: str):
        """
        Initializes the InBerlinWohnen scraper.
        
        Args:
            name: Display name for this scraper instance.
        """
        super().__init__(name)
        self.url = "https://www.inberlinwohnen.de/wohnungsfinder"

    def _fetch_raw_items(self) -> list:
        """
        Fetches the listing page and returns listing card elements.

        Returns:
            List of BeautifulSoup listing item elements.
        """
        with requests.get(self.url, headers=self.headers, timeout=(10, 40)) as response:
            response.raise_for_status()
            return self._extract_items_from_html(response.text)

    def _extract_items_from_html(self, html_content: str) -> list:
        """
        Extracts listing items from HTML content.

        Handles container and item detection with appropriate logging
        when elements are not found.

        Args:
            html_content: Raw HTML content from the page.

        Returns:
            List of BeautifulSoup listing item elements.
        """
        soup = BeautifulSoup(html_content, 'lxml')

        listings_container = soup.select_one(self.LISTINGS_CONTAINER_SELECTOR)
        if not listings_container:
            logger.error(
                f"Could not find listing container '{self.LISTINGS_CONTAINER_SELECTOR}'"
            )
            return []

        listing_items = listings_container.select(self.LISTING_ITEM_SELECTOR)
        if not listing_items:
            if "Keine Wohnungen gefunden" in listings_container.get_text():
                logger.info("No listings currently available on the page.")
            else:
                logger.warning(
                    f"Container found, but no items matching "
                    f"'{self.LISTING_ITEM_SELECTOR}'."
                )
            return []

        return listing_items

    def _parse_item(self, item_soup) -> Optional[Listing]:
        """
        Parses a single listing item into a Listing.

        Args:
            item_soup: BeautifulSoup element for a single listing.

        Returns:
            Listing object or None if no identifier could be determined.
        """
        listing = self._parse_listing_details(item_soup)
        if not listing.identifier:
            logger.warning(
                "Skipping a listing because no identifier could be determined."
            )
            return None
        return listing

    def _extract_identifier_fast(self, listing_soup: BeautifulSoup) -> Optional[str]:
        """
        Quickly extracts the listing identifier without full parsing.
        
        This enables early termination check before expensive full parsing.
        
        Args:
            listing_soup: BeautifulSoup object for a single listing.
            
        Returns:
            The listing identifier (detail URL) or None if not found.
        """
        link_tag = listing_soup.find('a', string=re.compile(r'Alle Details'))
        if link_tag and link_tag.get('href'):
            return link_tag['href']
        return None

    def _parse_listing_details(self, listing_soup: BeautifulSoup) -> Listing:
        """
        Parses details from an individual listing's BeautifulSoup object.
        
        Extracts: address, borough, rooms, sqm, cold/total rent, WBS status.
        
        Args:
            listing_soup: BeautifulSoup object for a single listing element.
            
        Returns:
            Listing object with extracted details.
        """
        details: Dict[str, str] = {}
        link_tag = listing_soup.find('a', string=re.compile(r'Alle Details'))
        if link_tag and link_tag.get('href'):
            details['identifier'] = link_tag['href']

        dts = listing_soup.find_all('dt')
        for dt in dts:
            dt_text = dt.get_text(strip=True)
            dd = dt.find_next_sibling('dd')
            if dd:
                dd_text = self._clean_text(dd.get_text(separator=' ', strip=True))
                self._extract_field(dt_text, dd, dd_text, details)

        details['source'] = self.name
        return Listing(**details)

    def _extract_field(
        self, field_label: str, dd_element: BeautifulSoup, 
        dd_text: str, details: Dict[str, str]
    ) -> None:
        """
        Extracts a single field value based on the field label.
        
        Args:
            field_label: The label text (e.g., "Adresse:", "Kaltmiete:").
            dd_element: The BeautifulSoup dd element containing the value.
            dd_text: Pre-cleaned text content of the dd element.
            details: Dictionary to update with extracted field.
        """
        if "Adresse:" in field_label:
            address_button = dd_element.find('button')
            address_text = (
                self._clean_text(address_button.get_text(strip=True)) 
                if address_button else dd_text
            )
            details['address'] = address_text
            self._extract_borough_from_address(address_text, details)
        elif "Wohnfläche:" in field_label:
            details['sqm'] = self._normalize_german_number(dd_text)
        elif "Kaltmiete:" in field_label:
            details['price_cold'] = self._normalize_german_number(dd_text)
        elif "Gesamtmiete:" in field_label:
            details['price_total'] = self._normalize_german_number(dd_text)
        elif "Zimmeranzahl:" in field_label:
            details['rooms'] = self._normalize_rooms_format(dd_text)
        elif "WBS:" in field_label:
            details['wbs'] =  not ('nicht erforderlich' in dd_text.lower())

    def _extract_borough_from_address(
        self, address_text: str, details: Dict[str, str]
    ) -> None:
        """
        Extracts borough from address by finding the ZIP code.
        
        Args:
            address_text: Full address string.
            details: Dictionary to update with borough field.
        """
        zip_code_match = re.search(r'\b(\d{5})\b', address_text)
        if zip_code_match:
            zip_code = zip_code_match.group(1)
            details['borough'] = self._get_borough_from_zip(zip_code)
