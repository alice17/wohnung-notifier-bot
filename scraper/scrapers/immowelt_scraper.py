import logging
import re
import time
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup

from scraper.listing import Listing
from scraper.scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class ImmoweltScraper(BaseScraper):
    """Handles fetching and parsing of apartment listings from immowelt.de."""

    def __init__(self, name: str):
        super().__init__(name)
        self.url = "https://www.immowelt.de/classified-search?distributionTypes=Rent&estateTypes=Apartment&locations=AD08DE8634&projectTypes=Stock&order=DateDesc"
        self.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Language': 'en-US,en;q=0.9,de;q=0.8',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
        })

    def get_current_listings(self, known_listings: Dict[str, Listing]) -> Dict[str, Listing]:
        """Fetches the website and returns a dictionary of listings."""
        listings_data: Dict[str, Listing] = {}
        session = requests.Session()
        session.headers.update(self.headers)

        try:
            # First hit the base URL to "establish" our session and get cookies
            session.get("https://www.immowelt.de/", timeout=10)

            # Now, make the actual request to the search page
            response = session.get(self.url, timeout=10)
            response.raise_for_status()  # Raise an exception for bad status codes

            logger.info("Successfully fetched the webpage.")
            soup = BeautifulSoup(response.text, 'html.parser')
            listings = soup.find_all('div', attrs={'data-testid': lambda v: v and v.startswith('classified-card-mfe-')})
            logger.info(f"Found {len(listings)} listings on the page.")

            for listing_soup in listings:
                listing = self._parse_listing(listing_soup)
                if listing and listing.identifier:
                    if listing.identifier in known_listings:
                        logger.debug(f"Skipping detail fetch for known listing: {listing.identifier}")
                        existing_listing = known_listings[listing.identifier]
                        listing.price_total = existing_listing.price_total
                    else:
                        self._scrape_listing_details(listing, session)
                        time.sleep(1) # Be nice to the server
                    
                    listings_data[listing.identifier] = listing
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred during the request for {self.url}: {e}")
            raise
        
        return listings_data

    def _parse_listing(self, listing_soup: BeautifulSoup) -> Optional[Listing]:
        """Parses a single listing from its BeautifulSoup object."""
        link_element = listing_soup.find('a', attrs={'data-testid': 'card-mfe-covering-link-testid'})
        if not (link_element and link_element.get('href')):
            logger.warning("Skipping a listing because no URL could be determined.")
            return None
        
        relative_url = link_element.get('href')
        url = "https://www.immowelt.de" + relative_url if relative_url and relative_url.startswith('/') else relative_url
        if not url:
            return None

        price_element = listing_soup.find('div', attrs={'data-testid': 'cardmfe-price-testid'})
        price = price_element.text.strip().split(' ')[0] if price_element else 'N/A'

        address_element = listing_soup.find('div', attrs={'data-testid': 'cardmfe-description-box-address'})
        address = address_element.text.strip() if address_element else 'N/A'
        
        borough = "N/A"
        zip_code_match = re.search(r'\b(\d{5})\b', address)
        if zip_code_match:
            zip_code = zip_code_match.group(1)
            borough = self._get_borough_from_zip(zip_code)

        rooms, size = '1', 'N/A'  # Default rooms to '1'
        key_facts_container = listing_soup.find('div', attrs={'data-testid': 'cardmfe-keyfacts-testid'})
        if key_facts_container:
            key_facts_elements = key_facts_container.find_all('div', class_='css-9u48bm')
            key_facts = [fact.text.strip() for fact in key_facts_elements if fact.text.strip() != '·']
            
            zimmer_fact = next((fact for fact in key_facts if 'Zimmer' in fact), None)
            if zimmer_fact:
                rooms = zimmer_fact.split(' ')[0]

            size_fact = next((fact for fact in key_facts if 'm²' in fact), None)
            if size_fact:
                size = size_fact

        return Listing(
            source=self.name,
            address=address,
            borough=borough,
            sqm=self._clean_text(size),
            price_cold=self._clean_text(price),
            rooms=self._clean_text(rooms),
            link=url,
            identifier=url,
        )

    def _scrape_listing_details(self, listing: Listing, session: requests.Session):
        """Scrapes additional details from the listing's detail page."""
        if not listing.link or listing.link == 'N/A':
            return
        
        try:
            logger.info(f"Fetching details from: {listing.link}")
            detail_response = session.get(listing.link, timeout=10)
            detail_response.raise_for_status()

            detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
            
            warm_rent_label = detail_soup.find('div', class_='css-8c1m7t', string='Warmmiete')
            if warm_rent_label:
                value_element = warm_rent_label.find_next_sibling('div', class_='css-1grdggd')
                if value_element:
                    span_element = value_element.find('span')
                    if span_element:
                        listing.price_total = self._clean_text(span_element.text.strip().replace('\xa0', ' '))
                        logger.debug(f"  > Success: Found Warmmiete: {listing.price_total}")

        except requests.exceptions.RequestException as e:
            logger.error(f"  > Error fetching detail page {listing.link}: {e}")

    @staticmethod
    def _clean_text(text: Optional[str]) -> str:
        """Remove extra whitespace and common units."""
        if not text:
            return "N/A"
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace('€', '').replace('m²', '').replace('Zi.', '').replace('Zimmer', '').strip()
        if text.endswith('.') or text.endswith(','):
            text = text[:-1].strip()
        return text if text else "N/A"
