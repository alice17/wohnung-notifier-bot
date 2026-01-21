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
from typing import Dict, Optional, Set

import requests
from bs4 import BeautifulSoup

from src.core.listing import Listing
from src.scrapers.base import BaseScraper, ScraperResult

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

    def get_current_listings(
        self, known_listings: Optional[Dict[str, Listing]] = None
    ) -> ScraperResult:
        """
        Fetches the website and returns new listings and seen known IDs.
        
        Optimized for live updates: uses early termination when a known
        listing is encountered. Since listings are sorted newest first,
        hitting a known listing means all remaining listings are also known.
        
        Args:
            known_listings: Previously seen listings for early termination.
            
        Returns:
            Tuple containing:
            - Dictionary mapping identifiers to new Listing objects
            - Set of known listing identifiers that were seen (still active)
            
        Raises:
            requests.exceptions.RequestException: If the HTTP request fails.
        """
        known_ids = self._extract_known_ids(known_listings) if known_listings else set()
        
        try:
            with requests.get(self.url, headers=self.headers, timeout=(10, 40)) as response:
                response.raise_for_status()
                return self._parse_html_optimized(response.text, known_ids)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching website {self.url}: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during parsing: {e}")
            raise

    def _extract_known_ids(self, known_listings: Dict[str, Listing]) -> Set[str]:
        """
        Extracts apartment IDs from known listings for fast lookup.
        
        The identifier is typically the detail page URL. We extract the
        apartment ID pattern for quick comparison.
        
        Args:
            known_listings: Dictionary of known listings.
            
        Returns:
            Set of known listing identifiers for O(1) lookup.
        """
        return set(known_listings.keys())

    def _parse_html_optimized(
        self, html_content: str, known_ids: Set[str]
    ) -> ScraperResult:
        """
        Parses HTML with early termination optimization.
        
        Stops processing when encountering a known listing since results
        are sorted newest first - all subsequent listings would be known.
        
        Args:
            html_content: Raw HTML content from the page.
            known_ids: Set of known listing identifiers.
            
        Returns:
            Tuple containing:
            - Dictionary of new listings only
            - Set of known listing identifiers that were seen (still active)
        """
        soup = BeautifulSoup(html_content, 'lxml')
        listings_data: Dict[str, Listing] = {}
        seen_known_ids: Set[str] = set()

        listings_container = soup.select_one(self.LISTINGS_CONTAINER_SELECTOR)
        if not listings_container:
            logger.error(
                f"Could not find listing container '{self.LISTINGS_CONTAINER_SELECTOR}'"
            )
            return {}, set()

        listing_items = listings_container.select(self.LISTING_ITEM_SELECTOR)
        if not listing_items:
            if "Keine Wohnungen gefunden" in listings_container.get_text():
                logger.info("No listings currently available on the page.")
            else:
                logger.warning(
                    f"Container found, but no items matching "
                    f"'{self.LISTING_ITEM_SELECTOR}'."
                )
            return {}, set()

        new_count = 0
        for item_soup in listing_items:
            # Quick ID extraction before full parsing
            identifier = self._extract_identifier_fast(item_soup)
            
            if identifier and identifier in known_ids:
                # Track this known listing as still active
                seen_known_ids.add(identifier)
                # Early termination: listings are newest first
                logger.debug(
                    f"Hit known listing '{identifier}', stopping (newest-first order)"
                )
                break
            
            # Full parsing only for new listings
            listing = self._parse_listing_details(item_soup)
            if listing.identifier:
                listings_data[listing.identifier] = listing
                new_count += 1
            else:
                logger.warning(
                    "Skipping a listing because no identifier could be determined."
                )

        if new_count > 0:
            logger.info(f"Found {new_count} new listing(s) on inberlinwohnen.de")
        else:
            logger.debug("No new listings found on inberlinwohnen.de")

        return listings_data, seen_known_ids

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
            details['wbs'] = 'erforderlich' in dd_text.lower()

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

    @staticmethod
    def _clean_text(text: Optional[str]) -> str:
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
        text = text.replace('€', '').replace('m²', '').strip()
        if text.endswith('.') or text.endswith(','):
            text = text[:-1].strip()
        return text if text else "N/A"
