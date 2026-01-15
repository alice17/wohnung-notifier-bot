"""
OhneMakler Scraper (Optimized for Live Updates).

This module defines the OhneMaklerScraper class, optimized for detecting
new apartment listings quickly rather than exhaustive scraping.

Optimization Strategy:
---------------------
1. Only processes first page (listings appear newest first by default)
2. Uses early termination when encountering known listings
3. Minimal parsing overhead for already-seen apartments
4. Fetches detail pages for new listings to get accurate total rent
"""
import logging
import re
from typing import Dict, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup

from src.core.listing import Listing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class OhneMaklerScraper(BaseScraper):
    """
    Handles fetching and parsing of apartment listings from ohne-makler.net.
    
    Optimized for live updates: only processes first page and implements
    early termination when known listings are encountered.
    """

    BASE_URL = "https://www.ohne-makler.net"

    def __init__(self, name: str):
        """
        Initializes the OhneMaklerScraper.
        
        Args:
            name: The name identifier for this scraper instance.
        """
        super().__init__(name)
        self.url = f"{self.BASE_URL}/immobilien/wohnung-mieten/berlin/berlin/"

    def get_current_listings(
        self, known_listings: Optional[Dict[str, Listing]] = None
    ) -> Dict[str, Listing]:
        """
        Fetches the website and returns a dictionary of new listings.
        
        Optimized for live updates: uses early termination when a known
        listing is encountered. Since listings typically appear newest first,
        hitting a known listing suggests remaining listings are also known.
        
        Args:
            known_listings: Previously seen listings for early termination.
            
        Returns:
            Dictionary mapping identifiers to Listing objects (new listings only).
            
        Raises:
            requests.exceptions.RequestException: If the HTTP request fails.
        """
        known_ids: Set[str] = set(known_listings.keys()) if known_listings else set()
        
        try:
            with requests.get(self.url, headers=self.headers, timeout=20) as response:
                response.raise_for_status()
                return self._parse_html_optimized(response.text, known_ids)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching website {self.url}: {e}")
            raise

    def _parse_html_optimized(
        self, html_content: str, known_ids: Set[str]
    ) -> Dict[str, Listing]:
        """
        Parses HTML with early termination optimization.
        
        Stops processing when encountering a known listing since results
        typically appear newest first - subsequent listings would be known.
        
        Args:
            html_content: The raw HTML content from the website.
            known_ids: Set of known listing identifiers.
            
        Returns:
            Dictionary of new listings only.
        """
        soup = BeautifulSoup(html_content, 'lxml')
        listings_data: Dict[str, Listing] = {}

        listing_items = soup.find_all('a', href=re.compile(r'^/immobilie/\d+/$'))
        
        if not listing_items:
            logger.warning("No listing items found on the page.")
            return {}

        logger.debug(f"Found {len(listing_items)} listings on page.")

        new_count = 0
        for item_soup in listing_items:
            # Quick ID extraction before full parsing
            identifier = self._extract_identifier_fast(item_soup)
            
            if identifier and identifier in known_ids:
                logger.debug(
                    f"Hit known listing '{identifier}', stopping (newest-first order)"
                )
                break
            
            # Full parsing only for new listings
            listing = self._parse_listing_details(item_soup)
            if listing and listing.identifier:
                listings_data[listing.identifier] = listing
                new_count += 1
            else:
                logger.warning("Skipping a listing: no identifier found.")

        if new_count > 0:
            logger.info(f"Found {new_count} new listing(s) on ohne-makler.net")
        else:
            logger.debug("No new listings found on ohne-makler.net")

        return listings_data

    def _extract_identifier_fast(self, listing_soup: BeautifulSoup) -> Optional[str]:
        """
        Quickly extracts the listing identifier (URL) without full parsing.
        
        This enables early termination check before expensive full parsing.
        The identifier must match what's stored in the Listing object (the URL).
        
        Args:
            listing_soup: BeautifulSoup object for a single listing.
            
        Returns:
            The listing URL as identifier, or None if not found.
        """
        href = listing_soup.get('href')
        if href:
            return f"{self.BASE_URL}{href}"
        return None

    def _parse_listing_details(self, listing_soup: BeautifulSoup) -> Optional[Listing]:
        """
        Parses details from an individual listing's BeautifulSoup object.
        
        Fetches the detail page to get accurate Warmmiete (total rent).
        
        Args:
            listing_soup: BeautifulSoup object representing a single listing.
            
        Returns:
            Listing object with extracted details, or None if parsing fails.
        """
        details = {}

        # Extract listing ID from data-om-id attribute
        listing_id = listing_soup.get('data-om-id')
        if not listing_id:
            logger.warning("Listing has no data-om-id attribute.")
            return None

        # Extract URL - used as the unique identifier
        href = listing_soup.get('href')
        if not href:
            logger.warning("Listing has no href attribute.")
            return None

        details['identifier'] = f"{self.BASE_URL}{href}"

        # Extract Kaltmiete from listing page (as fallback)
        price_span = listing_soup.find(
            'span', 
            class_=re.compile(r'.*text-primary-500.*text-xl.*')
        )
        if price_span:
            cleaned_price = self._clean_text(price_span.get_text(strip=True))
            details['price_cold'] = self._normalize_german_number(cleaned_price)

        # Extract address and borough
        address_container = listing_soup.find('div', class_='flex items-center text-slate-800')
        if address_container:
            address_span = address_container.find('span')
            if address_span:
                address_text = self._clean_text(address_span.get_text(separator=' ', strip=True))
                
                # Extract zip code and determine borough from mapping
                zip_code_match = re.search(r'\b(\d{5})\b', address_text)
                if zip_code_match:
                    zip_code = zip_code_match.group(1)
                    details['borough'] = self._get_borough_from_zip(zip_code)
                    
                    # Clean address: remove borough in parentheses and keep "zip Berlin"
                    # Format: "10245 Berlin (Friedrichshain)" -> "10245 Berlin"
                    cleaned_address = re.sub(r'\s*\([^)]*\)', '', address_text).strip()
                    details['address'] = cleaned_address
                else:
                    # No zip code found, keep original address
                    details['address'] = address_text

        # Extract rooms - look for div with title="Zimmer"
        rooms_div = listing_soup.find('div', title='Zimmer')
        if rooms_div:
            rooms_span = rooms_div.find('span', class_=re.compile(r'.*text-slate-700.*font-medium.*'))
            if rooms_span:
                rooms_text = self._clean_text(rooms_span.get_text(strip=True))
                details['rooms'] = self._normalize_rooms_format(rooms_text)

        # Extract square meters - look for div with title="Wohnfläche"
        sqm_div = listing_soup.find('div', title='Wohnfläche')
        if sqm_div:
            sqm_span = sqm_div.find('span', class_=re.compile(r'.*text-slate-700.*font-medium.*'))
            if sqm_span:
                sqm_text = self._clean_text(sqm_span.get_text(strip=True))
                details['sqm'] = self._normalize_german_number(sqm_text)

        # Fetch detail page to get accurate pricing (Warmmiete)
        price_cold, price_total = self._fetch_detail_page_pricing(details['identifier'])
        if price_cold:
            details['price_cold'] = price_cold
        if price_total:
            details['price_total'] = price_total

        details['source'] = self.name
        details['wbs'] = False
        return Listing(**details)

    def _fetch_detail_page_pricing(
        self, detail_url: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Fetches the detail page to extract accurate Kaltmiete and Warmmiete.
        
        The listing page only shows Kaltmiete. The detail page contains
        a "Miete & Nebenkosten" section with Kaltmiete + Nebenkosten.
        
        Args:
            detail_url: URL of the listing's detail page.
            
        Returns:
            Tuple of (price_cold, price_total) as formatted strings,
            or (None, None) if extraction fails.
        """
        try:
            with requests.get(
                detail_url, headers=self.headers, timeout=15
            ) as response:
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'lxml')
                
                return self._extract_pricing_from_detail(soup)
                
        except requests.exceptions.RequestException as request_error:
            logger.warning(
                f"Failed to fetch detail page {detail_url}: {request_error}"
            )
            return None, None

    def _extract_pricing_from_detail(
        self, soup: BeautifulSoup
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts Kaltmiete and calculates Warmmiete from the detail page.
        
        Parses the "Miete & Nebenkosten" table to find:
        - Kaltmiete (cold rent)
        - Summe Nebenkosten/Heizkosten (total additional costs)
        
        Args:
            soup: BeautifulSoup object of the detail page.
            
        Returns:
            Tuple of (price_cold, price_total) as normalized strings.
        """
        price_cold = None
        nebenkosten_total = None
        
        # Find all table rows in the pricing section
        rows = soup.find_all('tr')
        
        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 2:
                continue
                
            label = cells[0].get_text(strip=True).lower()
            value = cells[1].get_text(strip=True)
            
            if 'kaltmiete' in label:
                price_cold = self._extract_price_value(value)
            elif 'summe nebenkosten' in label or 'summe nebenkosten/heizkosten' in label:
                nebenkosten_total = self._extract_price_value(value)
        
        # Calculate Warmmiete (total rent)
        price_total = None
        if price_cold and nebenkosten_total:
            try:
                cold_value = float(self._normalize_german_number(price_cold))
                nk_value = float(self._normalize_german_number(nebenkosten_total))
                total_value = cold_value + nk_value
                price_total = str(int(total_value))
            except ValueError:
                logger.warning("Could not calculate Warmmiete from extracted values")
        
        # Normalize price_cold to standard format
        if price_cold:
            price_cold = self._normalize_german_number(price_cold)
        
        return price_cold, price_total

    def _extract_price_value(self, text: str) -> Optional[str]:
        """
        Extracts the numeric price value from a price string.
        
        Handles German number format (e.g., "1.800 € (zzgl. NK)" -> "1.800").
        
        Args:
            text: Price text that may contain currency symbols and notes.
            
        Returns:
            Cleaned price string or None if no price found.
        """
        # Match German price format: digits with optional thousand separators and decimals
        match = re.search(r'([\d.,]+)\s*€', text)
        if match:
            price = match.group(1).strip()
            # Normalize: keep German format (1.800 or 1.800,50)
            return price
        return None

    @staticmethod
    def _clean_text(text: Optional[str]) -> str:
        """
        Remove extra whitespace and common units from text.
        
        Args:
            text: The text to clean.
            
        Returns:
            Cleaned text string, or "N/A" if text is empty or None.
        """
        if not text:
            return "N/A"
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Remove common symbols and units
        text = text.replace('€', '').replace('m²', '').strip()
        # Remove trailing punctuation
        if text.endswith('.') or text.endswith(','):
            text = text[:-1].strip()
        return text if text else "N/A"

