"""
This module defines the OhneMaklerScraper class for scraping ohne-makler.net.
"""
import logging
import re
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup

from src.listing import Listing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class OhneMaklerScraper(BaseScraper):
    """
    Handles fetching and parsing of apartment listings from ohne-makler.net.
    
    This scraper targets the Berlin apartment rental listings page and extracts
    information such as price, location, number of rooms, and square meters.
    """

    def __init__(self, name: str):
        """
        Initializes the OhneMaklerScraper.
        
        Args:
            name: The name identifier for this scraper instance.
        """
        super().__init__(name)
        self.url = "https://www.ohne-makler.net/immobilien/wohnung-mieten/berlin/berlin/"

    def get_current_listings(
        self, known_listings: Optional[Dict[str, Listing]] = None
    ) -> Dict[str, Listing]:
        """
        Fetches the website and returns a dictionary of listings.
        
        Args:
            known_listings: Optional dictionary of previously known listings.
            
        Returns:
            Dictionary mapping listing identifiers to Listing objects.
            
        Raises:
            requests.exceptions.RequestException: If the HTTP request fails.
            Exception: For any other unexpected errors during parsing.
        """
        try:
            with requests.get(self.url, headers=self.headers, timeout=20) as response:
                response.raise_for_status()
                return self._parse_html(response.text)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching website {self.url}: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during parsing: {e}")
            raise

    def _parse_html(self, html_content: str) -> Dict[str, Listing]:
        """
        Parses the HTML content to extract listing details.
        
        Args:
            html_content: The raw HTML content from the website.
            
        Returns:
            Dictionary mapping listing identifiers to Listing objects.
        """
        soup = BeautifulSoup(html_content, 'lxml')
        listings_data = {}

        # Find all listing links with pattern /immobilie/{number}/
        listing_items = soup.find_all('a', href=re.compile(r'^/immobilie/\d+/$'))
        
        if not listing_items:
            logger.warning("No listing items found on the page.")
            return {}

        logger.info(f"Found {len(listing_items)} listings on the page.")

        for item_soup in listing_items:
            listing = self._parse_listing_details(item_soup)
            if listing and listing.identifier:
                listings_data[listing.identifier] = listing
            else:
                logger.warning("Skipping a listing: no identifier found.")

        return listings_data

    def _parse_listing_details(self, listing_soup: BeautifulSoup) -> Optional[Listing]:
        """
        Parses details from an individual listing's BeautifulSoup object.
        
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

        # Extract URL
        href = listing_soup.get('href')
        if href:
            details['link'] = f"https://www.ohne-makler.net{href}"
            details['identifier'] = listing_id

        # Extract price
        price_span = listing_soup.find(
            'span', 
            class_=re.compile(r'.*text-primary-500.*text-xl.*')
        )
        if price_span:
            details['price_total'] = self._clean_text(price_span.get_text(strip=True))

        # Extract title
        title_h4 = listing_soup.find('h4')
        if title_h4:
            title = self._clean_text(title_h4.get_text(strip=True))
            logger.debug(f"Found listing: {title}")

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
                details['rooms'] = self._clean_text(rooms_span.get_text(strip=True))

        # Extract square meters - look for div with title="Wohnfläche"
        sqm_div = listing_soup.find('div', title='Wohnfläche')
        if sqm_div:
            sqm_span = sqm_div.find('span', class_=re.compile(r'.*text-slate-700.*font-medium.*'))
            if sqm_span:
                details['sqm'] = self._clean_text(sqm_span.get_text(strip=True))

        details['source'] = self.name
        return Listing(**details)

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

