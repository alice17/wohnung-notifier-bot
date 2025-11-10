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
            listings = soup.select('#srchrslt-adtable .ad-listitem')
            logger.info(f"Found {len(listings)} listings on the page.")

            for listing_soup in listings:
                listing = self._parse_listing(listing_soup)
                if listing and listing.identifier:
                    listings_data[listing.identifier] = listing

        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred during the request for {self.url}: {e}")
            raise

        return listings_data

    def _parse_listing(self, listing_soup: BeautifulSoup) -> Optional[Listing]:
        """Parses a single listing from its BeautifulSoup object."""
        aditem = listing_soup.select_one('.aditem')
        if not aditem:
            return None

        ad_id = aditem.get('data-adid')
        if not ad_id:
            return None

        link_element = listing_soup.select_one('.aditem-main .text-module-begin a')
        relative_url = link_element.get('href') if link_element else None
        if not relative_url:
            return None
        url = f"https://www.kleinanzeigen.de{relative_url}"

        price_element = listing_soup.select_one('.aditem-main--middle--price-shipping--price')
        if price_element:
            # Remove the old price (strikethrough) if present
            old_price = price_element.select_one('.aditem-main--middle--price-shipping--old-price')
            if old_price:
                old_price.decompose()
            price = self._clean_text(price_element.text)
        else:
            price = 'N/A'

        size_element = listing_soup.select_one('.aditem-main--middle--tags')
        tags_text = size_element.text if size_element else ''
        
        # Extract square meters from tags
        size_match = re.search(r'(\d+)\s*m²', tags_text)
        size = size_match.group(1) if size_match else 'N/A'
        
        # Extract number of rooms from tags
        rooms_match = re.search(r'(\d+)\s*Zi\.', tags_text)
        rooms = rooms_match.group(1) if rooms_match else '1'

        address_element = listing_soup.select_one('.aditem-main--top--left')
        address = self._clean_text(address_element.text) if address_element else 'N/A'
        # Remove distance in parentheses (e.g., "(6 km)")
        address = re.sub(r'\s*\(\d+\s*km\)', '', address)

        borough = "N/A"
        zip_code_match = re.search(r'\b(\d{5})\b', address)
        if zip_code_match:
            zip_code = zip_code_match.group(1)
            borough = self._get_borough_from_zip(zip_code)

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

    @staticmethod
    def _clean_text(text: Optional[str]) -> str:
        """Remove extra whitespace and common units."""
        if not text:
            return "N/A"
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace('€', '').replace('m²', '').replace('VB', '').strip()
        return text if text else "N/A"
