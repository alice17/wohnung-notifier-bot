"""
Immowelt Scraper (Optimized for Live Updates).

This module defines the ImmoweltScraper class, optimized for detecting new
apartment listings quickly rather than exhaustive scraping.

Optimization Strategy:
---------------------
1. Only processes first page (sorted newest first via order=DateDesc)
2. Uses early termination when encountering known listings
3. Skips detail page fetches for known listings
4. Minimal parsing overhead for already-seen apartments
"""
import logging
import re
import time
from typing import Dict, Optional, Set

import requests
from bs4 import BeautifulSoup

from src.core.listing import Listing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class ImmoweltScraper(BaseScraper):
    """
    Handles fetching and parsing of apartment listings from immowelt.de.
    
    Optimized for live updates: only processes first page (newest first)
    and implements early termination when known listings are encountered.
    """

    def __init__(self, name: str):
        """
        Initializes the Immowelt scraper.
        
        Args:
            name: Display name for this scraper instance.
        """
        super().__init__(name)
        self.url = (
            "https://www.immowelt.de/classified-search"
            "?distributionTypes=Rent"
            "&estateTypes=Apartment"
            "&locations=AD08DE8634"
            "&projectTypes=Stock"
            "&order=DateDesc"
        )
        self.headers.update(
            {
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
                    "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9"
                ),
                "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
                "Referer": "https://www.google.com/",
                "DNT": "1",
                "Upgrade-Insecure-Requests": "1",
            }
        )

    def get_current_listings(
        self, known_listings: Optional[Dict[str, Listing]] = None
    ) -> Dict[str, Listing]:
        """
        Fetches the website and returns a dictionary of new listings.
        
        Optimized for live updates: uses early termination when a known
        listing is encountered. Since listings are sorted newest first,
        hitting a known listing means all remaining listings are also known.
        
        Args:
            known_listings: Previously seen listings for early termination.
            
        Returns:
            Dictionary mapping identifiers to Listing objects (new listings only).
            
        Raises:
            requests.exceptions.RequestException: If the HTTP request fails.
        """
        if not known_listings:
            known_listings = {}
        
        known_ids: Set[str] = set(known_listings.keys())
        listings_data: Dict[str, Listing] = {}
        session = requests.Session()
        session.headers.update(self.headers)

        try:
            session.get("https://www.immowelt.de/", timeout=10)
            response = session.get(self.url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            listing_elements = soup.find_all(
                'div', 
                attrs={'data-testid': lambda v: v and v.startswith('classified-card-mfe-')}
            )
            logger.debug(f"Found {len(listing_elements)} listings on page.")

            new_count = 0
            for listing_soup in listing_elements:
                # Quick ID extraction before full parsing
                identifier = self._extract_identifier_fast(listing_soup)
                
                if identifier and identifier in known_ids:
                    logger.debug(
                        f"Hit known listing '{identifier}', stopping (newest-first order)"
                    )
                    break
                
                # Full parsing only for new listings
                listing = self._parse_listing(listing_soup)
                if listing and listing.identifier:
                    self._scrape_listing_details(listing, session)
                    time.sleep(0.5)  # Brief delay between detail fetches
                    listings_data[listing.identifier] = listing
                    new_count += 1

            if new_count > 0:
                logger.info(f"Found {new_count} new listing(s) on immowelt.de")
            else:
                logger.debug("No new listings found on immowelt.de")

        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred during the request for {self.url}: {e}")
            raise

        return listings_data

    def _extract_identifier_fast(self, listing_soup: BeautifulSoup) -> Optional[str]:
        """
        Quickly extracts the listing identifier without full parsing.
        
        This enables early termination check before expensive full parsing.
        
        Args:
            listing_soup: BeautifulSoup object for a single listing.
            
        Returns:
            The listing identifier (detail URL) or None if not found.
        """
        link_element = listing_soup.find(
            'a', attrs={'data-testid': 'card-mfe-covering-link-testid'}
        )
        if link_element and link_element.get('href'):
            relative_url = link_element.get('href')
            if relative_url and relative_url.startswith('/'):
                return "https://www.immowelt.de" + relative_url
            return relative_url
        return None

    def _parse_listing(self, listing_soup: BeautifulSoup) -> Optional[Listing]:
        """
        Parses a single listing from its BeautifulSoup object.
        
        Args:
            listing_soup: BeautifulSoup object containing listing HTML
            
        Returns:
            Listing object or None if parsing fails
        """
        url = self._extract_listing_url(listing_soup)
        if not url:
            return None
        
        price_cold = self._extract_price(listing_soup)
        address, borough = self._extract_address_and_borough(listing_soup)
        rooms, sqm = self._extract_key_facts(listing_soup)
        
        return Listing(
            source=self.name,
            address=address,
            borough=borough,
            sqm=sqm,
            price_cold=price_cold,
            rooms=rooms,
            identifier=url,
        )

    def _extract_listing_url(self, listing_soup: BeautifulSoup) -> Optional[str]:
        """
        Extracts and validates the listing URL.
        
        Args:
            listing_soup: BeautifulSoup object containing listing HTML
            
        Returns:
            Full URL string or None if not found
        """
        link_element = listing_soup.find(
            'a', attrs={'data-testid': 'card-mfe-covering-link-testid'}
        )
        
        if not (link_element and link_element.get('href')):
            logger.warning("Skipping a listing because no URL could be determined.")
            return None
        
        relative_url = link_element.get('href')
        if relative_url and relative_url.startswith('/'):
            return "https://www.immowelt.de" + relative_url
        
        return relative_url

    def _extract_price(self, listing_soup: BeautifulSoup) -> str:
        """
        Extracts and cleans the cold rent price.
        
        Immowelt uses German number format (e.g., '2.345' for 2345 EUR).
        This method normalizes to standard format.
        
        Args:
            listing_soup: BeautifulSoup object containing listing HTML
            
        Returns:
            Normalized price string in standard format or 'N/A' if not found
        """
        price_element = listing_soup.find(
            'div', attrs={'data-testid': 'cardmfe-price-testid'}
        )
        
        if not price_element:
            return 'N/A'
        
        price_text = price_element.text.strip().split(' ')[0]
        cleaned_price = self._clean_text(price_text)
        return self._normalize_german_number(cleaned_price)

    def _extract_address_and_borough(
        self, listing_soup: BeautifulSoup
    ) -> tuple[str, str]:
        """
        Extracts address and derives borough from ZIP code.
        
        Args:
            listing_soup: BeautifulSoup object containing listing HTML
            
        Returns:
            Tuple of (address, borough), both strings
        """
        address_element = listing_soup.find(
            'div', attrs={'data-testid': 'cardmfe-description-box-address'}
        )
        address = address_element.text.strip() if address_element else 'N/A'
        
        borough = self._extract_borough_from_address(address)
        
        return address, borough

    def _extract_borough_from_address(self, address: str) -> str:
        """
        Extracts borough from address by finding and looking up ZIP code.
        
        Args:
            address: Full address string
            
        Returns:
            Borough name or 'N/A' if not found
        """
        zip_code_match = re.search(r'\b(\d{5})\b', address)
        if not zip_code_match:
            return "N/A"
        
        zip_code = zip_code_match.group(1)
        return self._get_borough_from_zip(zip_code)

    def _extract_key_facts(self, listing_soup: BeautifulSoup) -> tuple[str, str]:
        """
        Extracts room count and square meters from key facts section.
        
        Args:
            listing_soup: BeautifulSoup object containing listing HTML
            
        Returns:
            Tuple of (rooms, sqm), both as cleaned strings
        """
        key_facts_container = listing_soup.find(
            'div', attrs={'data-testid': 'cardmfe-keyfacts-testid'}
        )
        
        if not key_facts_container:
            return '1', 'N/A'  # Default values
        
        key_facts = self._parse_key_facts_container(key_facts_container)
        rooms = self._extract_rooms_from_facts(key_facts)
        sqm = self._extract_sqm_from_facts(key_facts)
        
        return rooms, sqm

    def _parse_key_facts_container(self, container: BeautifulSoup) -> list[str]:
        """
        Parses key facts container into list of fact strings.
        
        Args:
            container: BeautifulSoup element containing key facts
            
        Returns:
            List of cleaned fact strings
        """
        key_facts_elements = container.find_all('div', class_='css-9u48bm')
        return [
            fact.text.strip()
            for fact in key_facts_elements
            if fact.text.strip() != '·'
        ]

    def _extract_rooms_from_facts(self, key_facts: list[str]) -> str:
        """
        Extracts room count from key facts list.
        
        Normalizes to dot decimal separator (same format as prices).
        
        Args:
            key_facts: List of fact strings
            
        Returns:
            Cleaned room count string with dot decimal separator or '1' as default
        """
        zimmer_fact = next((fact for fact in key_facts if 'Zimmer' in fact), None)
        if not zimmer_fact:
            return '1'
        
        room_count = zimmer_fact.split(' ')[0]
        return self._normalize_rooms_format(self._clean_text(room_count))

    def _extract_sqm_from_facts(self, key_facts: list[str]) -> str:
        """
        Extracts square meters from key facts list.
        
        Normalizes German number format (comma as decimal separator)
        to standard format (period as decimal separator).
        
        Args:
            key_facts: List of fact strings
            
        Returns:
            Cleaned and normalized square meter string or 'N/A' if not found
        """
        size_fact = next((fact for fact in key_facts if 'm²' in fact), None)
        if not size_fact:
            return 'N/A'
        
        cleaned_sqm = self._clean_text(size_fact)
        return self._normalize_german_number(cleaned_sqm)

    def _scrape_listing_details(self, listing: Listing, session: requests.Session):
        """Scrapes additional details from the listing's detail page."""
        if not listing.identifier or not listing.identifier.startswith("http"):
            return

        try:
            logger.info(f"Fetching details from: {listing.identifier}")
            detail_response = session.get(listing.identifier, timeout=10)
            detail_response.raise_for_status()

            detail_soup = BeautifulSoup(detail_response.text, 'html.parser')

            warm_rent_label = detail_soup.find('div', class_='css-8c1m7t', string='Warmmiete')
            if warm_rent_label:
                value_element = warm_rent_label.find_next_sibling('div', class_='css-1grdggd')
                if value_element:
                    span_element = value_element.find('span')
                    if span_element:
                        cleaned_price = self._clean_text(
                            span_element.text.strip().replace('\xa0', ' ')
                        )
                        listing.price_total = self._normalize_german_number(cleaned_price)
                        logger.debug(
                            "  > Success: Found Warmmiete: %s", listing.price_total
                        )

        except requests.exceptions.RequestException as e:
            logger.error(f"  > Error fetching detail page {listing.identifier}: {e}")

    @staticmethod
    def _clean_text(text: Optional[str]) -> str:
        """Remove extra whitespace and common units."""
        if not text:
            return "N/A"
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace('€', '').replace('m²', '').replace('Zi.', '').replace(
            'Zimmer', ''
        ).strip()
        if text.endswith('.') or text.endswith(','):
            text = text[:-1].strip()
        return text if text else "N/A"
