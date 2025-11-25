"""
This module defines the KleinanzeigenScraper class.
"""
import logging
import re
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup

from src.listing import Listing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class KleinanzeigenScraper(BaseScraper):
    """Handles fetching and parsing of apartment listings from kleinanzeigen.de."""

    def __init__(self, name: str):
        super().__init__(name)
        self.url = "https://www.kleinanzeigen.de/s-haus-mieten/berlin/sortierung:neuste/c205l3331r10"
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
        """Fetches the website and returns a dictionary of listings."""
        if not known_listings:
            known_listings = {}

        listings_data: Dict[str, Listing] = {}
        session = requests.Session()
        session.headers.update(self.headers)

        try:
            response = session.get(self.url, timeout=10)
            response.raise_for_status()

            logger.info("Successfully fetched the webpage.")
            soup = BeautifulSoup(response.text, 'html.parser')
            # The selectors are based on the provided JS code and might be outdated.
            all_listing_elements = soup.select('#srchrslt-adtable .ad-listitem')
            logger.info(f"Found {len(all_listing_elements)} listing elements on the page.")
            
            # Filter out empty listing elements (ad spacers, placeholders, etc.)
            listings = [li for li in all_listing_elements if li.select_one('.aditem')]
            logger.info(f"Found {len(listings)} valid listings (filtered out {len(all_listing_elements) - len(listings)} empty elements).")

            for listing_soup in listings:
                listing = self._parse_listing(listing_soup)
                if listing and listing.identifier:
                    listings_data[listing.identifier] = listing

        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred during the request for {self.url}: {e}")
            raise

        return listings_data

    def _parse_listing(self, listing_soup: BeautifulSoup) -> Optional[Listing]:
        """
        Parses a single listing from its BeautifulSoup object.
        
        Args:
            listing_soup: BeautifulSoup object containing the listing HTML
            
        Returns:
            Listing object if parsing successful, None otherwise
            
        Raises:
            None - failures are logged and None is returned
        """
        # Extract core identifiers
        ad_id = self._extract_ad_id(listing_soup)
        if not ad_id:
            return None
        
        url = self._extract_listing_url(listing_soup)
        if not url:
            logger.warning(f"No URL found for ad_id: {ad_id}")
            return None
        
        # Extract listing details
        price = self._extract_price(listing_soup)
        size, rooms = self._extract_size_and_rooms(listing_soup)
        address = self._extract_address(listing_soup)
        borough = self._extract_borough_from_address(address)
        
        return Listing(
            source=self.name,
            address=address,
            borough=borough,
            sqm=size,
            price_cold=price,
            rooms=rooms,
            link=url,
            identifier=ad_id,
        )

    def _extract_ad_id(self, listing_soup: BeautifulSoup) -> Optional[str]:
        """
        Extracts the advertisement ID from the listing.
        
        Args:
            listing_soup: BeautifulSoup object containing the listing HTML
            
        Returns:
            Advertisement ID string or None if not found
        """
        aditem = listing_soup.select_one('.aditem')
        if not aditem:
            logger.warning("Unexpected: No .aditem element found in filtered listing")
            return None
        
        ad_id = aditem.get('data-adid')
        if not ad_id:
            logger.warning("No data-adid attribute found in .aditem element")
            return None
        
        return str(ad_id)

    def _extract_listing_url(self, listing_soup: BeautifulSoup) -> Optional[str]:
        """
        Extracts and constructs the full listing URL.
        
        Args:
            listing_soup: BeautifulSoup object containing the listing HTML
            
        Returns:
            Full URL string or None if URL not found
        """
        # First try: get URL from data-href attribute (most reliable)
        aditem = listing_soup.select_one('.aditem')
        if aditem:
            relative_url = aditem.get('data-href')
            if relative_url:
                return f"https://www.kleinanzeigen.de{relative_url}"
        
        # Second try: find any link with href in the listing
        link_element = listing_soup.select_one('a[href*="/s-anzeige/"]')
        if link_element:
            relative_url = link_element.get('href')
            if relative_url:
                return f"https://www.kleinanzeigen.de{relative_url}"
        
        logger.warning("Could not find URL using any method")
        return None

    def _extract_price(self, listing_soup: BeautifulSoup) -> str:
        """
        Extracts the price from the listing, removing any old prices.
        
        Kleinanzeigen uses German number format, which is normalized to standard format.
        
        Args:
            listing_soup: BeautifulSoup object containing the listing HTML
            
        Returns:
            Normalized price string in standard format or 'N/A' if not found
        """
        price_element = listing_soup.select_one(
            '.aditem-main--middle--price-shipping--price'
        )
        if not price_element:
            return 'N/A'
        
        # Remove strikethrough old price if present
        old_price = price_element.select_one(
            '.aditem-main--middle--price-shipping--old-price'
        )
        if old_price:
            old_price.decompose()
        
        cleaned_price = self._clean_text(price_element.text)
        return self._normalize_german_number(cleaned_price)

    def _extract_size_and_rooms(self, listing_soup: BeautifulSoup) -> tuple[str, str]:
        """
        Extracts square meters and number of rooms from listing tags.
        
        Args:
            listing_soup: BeautifulSoup object containing the listing HTML
            
        Returns:
            Tuple of (size, rooms) where both are strings, defaulting to 'N/A' and '1'
        """
        size_element = listing_soup.select_one('.aditem-main--middle--tags')
        tags_text = size_element.text if size_element else ''
        
        # Extract square meters (e.g., "85 m²" -> "85")
        size_match = re.search(r'(\d+)\s*m²', tags_text)
        size = size_match.group(1) if size_match else 'N/A'
        
        # Extract number of rooms (e.g., "3 Zi." -> "3")
        rooms_match = re.search(r'(\d+)\s*Zi\.', tags_text)
        rooms = rooms_match.group(1) if rooms_match else '1'
        
        return size, rooms

    def _extract_address(self, listing_soup: BeautifulSoup) -> str:
        """
        Extracts and cleans the address, removing distance information.
        
        Args:
            listing_soup: BeautifulSoup object containing the listing HTML
            
        Returns:
            Cleaned address string or 'N/A' if not found
        """
        address_element = listing_soup.select_one('.aditem-main--top--left')
        if not address_element:
            return 'N/A'
        
        address = self._clean_text(address_element.text)
        # Remove distance suffix (e.g., "(6 km)")
        address = re.sub(r'\s*\(\d+\s*km\)', '', address)
        
        return address

    def _extract_borough_from_address(self, address: str) -> str:
        """
        Extracts the borough from an address using its zip code.
        
        Args:
            address: Address string that may contain a zip code
            
        Returns:
            Borough name or 'N/A' if zip code not found or not mapped
        """
        # Extract 5-digit zip code from address
        zip_code_match = re.search(r'\b(\d{5})\b', address)
        if not zip_code_match:
            return "N/A"
        
        zip_code = zip_code_match.group(1)
        return self._get_borough_from_zip(zip_code)

    @staticmethod
    def _clean_text(text: Optional[str]) -> str:
        """Remove extra whitespace and common units."""
        if not text:
            return "N/A"
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace('€', '').replace('m²', '').replace('VB', '').strip()
        return text if text else "N/A"
