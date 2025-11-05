import logging
import re
from typing import Dict, Any, Optional

import requests
from bs4 import BeautifulSoup

from scraper.listing import Listing
from scraper.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class InBerlinWohnenScraper(BaseScraper):
    """Handles fetching and parsing of apartment listings from inberlinwohnen.de."""
    LISTINGS_CONTAINER_SELECTOR = "div[wire\:loading\.remove]"
    LISTING_ITEM_SELECTOR = "div[id^='apartment-']"

    def __init__(self, name: str):
        super().__init__(name)
        self.url = "https://www.inberlinwohnen.de/wohnungsfinder"

    def get_current_listings(self) -> Dict[str, Listing]:
        """Fetches the website and returns a dictionary of listings."""
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
        """Parses the HTML content to extract listing details."""
        soup = BeautifulSoup(html_content, 'lxml')
        listings_data = {}

        listings_container = soup.select_one(self.LISTINGS_CONTAINER_SELECTOR)
        if not listings_container:
            logger.error(f"Could not find listing container '{self.LISTINGS_CONTAINER_SELECTOR}'")
            return {}

        listing_items = listings_container.select(self.LISTING_ITEM_SELECTOR)
        if not listing_items:
            if "Keine Wohnungen gefunden" in listings_container.get_text():
                logger.info("No listings currently available on the page.")
            else:
                logger.warning(f"Container found, but no items matching '{self.LISTING_ITEM_SELECTOR}'.")
            return {}

        for item_soup in listing_items:
            listing = self._parse_listing_details(item_soup)
            if listing.identifier:
                listings_data[listing.identifier] = listing
            else:
                logger.warning("Skipping a listing because no identifier could be determined.")

        return listings_data

    def _parse_listing_details(self, listing_soup: BeautifulSoup) -> Listing:
        """Parses details from an individual listing's BeautifulSoup object."""
        details = {}
        link_tag = listing_soup.find('a', string=re.compile(r'Alle Details'))
        if link_tag and link_tag.get('href'):
            details['link'] = link_tag['href']
            details['identifier'] = details['link']

        dts = listing_soup.find_all('dt')
        for dt in dts:
            dt_text = dt.get_text(strip=True)
            dd = dt.find_next_sibling('dd')
            if dd:
                dd_text = self._clean_text(dd.get_text(separator=' ', strip=True))
                if "Adresse:" in dt_text:
                    address_button = dd.find('button')
                    address_text = self._clean_text(
                        address_button.get_text(strip=True)) if address_button else dd_text
                    details['address'] = address_text

                    # Extract zip code and determine borough
                    zip_code_match = re.search(r'\b(\d{5})\b', address_text)
                    if zip_code_match:
                        zip_code = zip_code_match.group(1)
                        details['borough'] = self._get_borough_from_zip(zip_code)
                elif "Wohnfläche:" in dt_text:
                    details['sqm'] = dd_text
                elif "Kaltmiete:" in dt_text:
                    details['price_cold'] = dd_text
                elif "Gesamtmiete:" in dt_text:
                    details['price_total'] = dd_text
                elif "Zimmeranzahl:" in dt_text:
                    details['rooms'] = dd_text
                elif "WBS:" in dt_text:
                    details['wbs'] = dd_text if dd_text != 'N/A' else 'Unknown'

        details['source'] = self.name
        return Listing(**details)

    @staticmethod
    def _clean_text(text: Optional[str]) -> str:
        """Remove extra whitespace and common units."""
        if not text:
            return "N/A"
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace('€', '').replace('m²', '').strip()
        if text.endswith('.') or text.endswith(','):
            text = text[:-1].strip()
        return text if text else "N/A"
