"""
This module defines the DeutscheWohnenScraper class.

Deutsche Wohnen Scraper
======================

This scraper fetches apartment listings from deutsche-wohnen.com using their
internal API (wohnraumkarte.de), which provides fast and reliable access to
listing data.

Features:
---------
- Fetches all available Berlin apartment listings
- Extracts: address, borough, rooms, size, cold rent, and listing URL
- Uses efficient API-based approach (no HTML parsing required)
- Supports pagination for large result sets

Limitations:
-----------
- Warm rent (price_total) is NOT available from the API
  - The detail API requires user session cookies
  - Fetching detail pages for all listings would be slow and unreliable
  - Therefore, price_total remains 'N/A' for all listings
- If warm rent is critical for filtering, consider using other scrapers

Technical Details:
-----------------
The scraper uses the wohnraumkarte.de API which Deutsche Wohnen uses to
dynamically load their listings. This API returns comprehensive listing
data in JSON format, making it ideal for scraping.
"""
import logging
from typing import Dict, Optional

import requests

from src.listing import Listing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class DeutscheWohnenScraper(BaseScraper):
    """
    Handles fetching and parsing of apartment listings from deutsche-wohnen.com.
    
    This scraper uses the Wohnraumkarte API that Deutsche Wohnen uses
    to dynamically load their apartment listings.
    """

    def __init__(self, name: str):
        """
        Initializes the Deutsche Wohnen scraper.
        
        Args:
            name: Display name for this scraper instance
        """
        super().__init__(name)
        self.api_url = "https://www.wohnraumkarte.de/api/getImmoList"
        self.base_url = "https://www.deutsche-wohnen.com"
        self.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
                "Referer": "https://www.deutsche-wohnen.com/",
                "DNT": "1",
            }
        )

    def get_current_listings(
        self, known_listings: Optional[Dict[str, Listing]] = None
    ) -> Dict[str, Listing]:
        """
        Fetches apartment listings from the API.
        
        Note: Warm rent (price_total) is not available from the API
        and would require fetching individual detail pages with session
        cookies, which would significantly slow down the scraper.
        Therefore, price_total remains 'N/A' for all listings.
        
        Args:
            known_listings: Dictionary of previously known listings (unused)
            
        Returns:
            Dictionary mapping listing identifiers to Listing objects
        """
        listings_data: Dict[str, Listing] = {}
        session = requests.Session()
        session.headers.update(self.headers)

        try:
            total_listings = self._fetch_total_count(session)
            logger.info(f"Found {total_listings} total listings available.")

            offset = 0
            limit = 100  # Fetch in batches of 100

            while offset < total_listings:
                batch_listings = self._fetch_listings_batch(session, limit, offset)
                
                for listing_data in batch_listings:
                    listing = self._parse_listing(listing_data)
                    if listing and listing.identifier:
                        listings_data[listing.identifier] = listing

                offset += limit
                logger.info(
                    f"Fetched {len(listings_data)}/{total_listings} listings..."
                )

        except requests.exceptions.RequestException as e:
            logger.error(
                f"An error occurred during the request for {self.api_url}: {e}"
            )
            raise

        return listings_data

    def _fetch_total_count(self, session: requests.Session) -> int:
        """
        Fetches the total count of available listings.
        
        Args:
            session: Active requests session
            
        Returns:
            Total number of listings available
        """
        params = self._build_api_params(limit=1, offset=0)
        
        try:
            response = session.get(self.api_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'paging' in data and 'totalCount' in data['paging']:
                return int(data['paging']['totalCount'])
            
            # Fallback to results count if paging info not available
            return len(data.get('results', []))
            
        except (requests.exceptions.RequestException, KeyError, ValueError) as e:
            logger.warning(f"Could not determine total count: {e}")
            return 0

    def _fetch_listings_batch(
        self, session: requests.Session, limit: int, offset: int
    ) -> list:
        """
        Fetches a batch of listings from the API.
        
        Args:
            session: Active requests session
            limit: Maximum number of listings to fetch
            offset: Starting offset for pagination
            
        Returns:
            List of listing dictionaries from the API
        """
        params = self._build_api_params(limit=limit, offset=offset)
        
        response = session.get(self.api_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return data.get('results', [])

    def _build_api_params(self, limit: int, offset: int) -> dict:
        """
        Builds API query parameters for fetching listings.
        
        Args:
            limit: Maximum number of results to return
            offset: Starting offset for pagination
            
        Returns:
            Dictionary of query parameters
        """
        return {
            'rentType': 'miete',
            'city': 'Berlin',
            'immoType': 'wohnung',
            'limit': str(limit),
            'offset': str(offset),
            'orderBy': 'date_desc',
            'dataSet': 'deuwo'
        }

    def _parse_listing(self, listing_data: dict) -> Optional[Listing]:
        """
        Parses a single listing from the API response.
        
        Args:
            listing_data: Dictionary containing listing data from API
            
        Returns:
            Listing object or None if parsing fails
        """
        try:
            wrk_id = listing_data.get('wrk_id', '')
            if not wrk_id:
                logger.warning("Skipping listing without wrk_id")
                return None

            address = self._build_address(listing_data)
            borough = self._extract_borough(listing_data)
            price_cold = self._extract_price(listing_data)
            sqm = self._extract_sqm(listing_data)
            rooms = self._extract_rooms(listing_data)
            link = self._build_listing_url(listing_data)

            return Listing(
                source=self.name,
                address=address,
                borough=borough,
                sqm=sqm,
                price_cold=price_cold,
                rooms=rooms,
                link=link,
                identifier=link,
            )

        except Exception as e:
            logger.error(f"Error parsing listing: {e}")
            return None

    def _build_address(self, listing_data: dict) -> str:
        """
        Builds the full address from listing data.
        
        Args:
            listing_data: Dictionary containing listing data
            
        Returns:
            Formatted address string
        """
        street = listing_data.get('strasse', '').strip()
        plz = listing_data.get('plz', '').strip()
        ort = listing_data.get('ort', '').strip()

        if street and plz and ort:
            return f"{street}, {plz} {ort}"
        elif plz and ort:
            return f"{plz} {ort}"
        elif street:
            return street
        
        return "N/A"

    def _extract_borough(self, listing_data: dict) -> str:
        """
        Extracts borough from listing data.
        
        Args:
            listing_data: Dictionary containing listing data
            
        Returns:
            Borough name or 'N/A' if not found
        """
        # Try to extract from 'ort' field (e.g., "Berlin OT Wedding")
        ort = listing_data.get('ort', '')
        if 'OT' in ort:
            parts = ort.split('OT')
            if len(parts) > 1:
                return parts[1].strip()

        # Fallback to ZIP code lookup
        plz = listing_data.get('plz', '')
        if plz:
            return self._get_borough_from_zip(plz)

        return "N/A"

    def _extract_price(self, listing_data: dict) -> str:
        """
        Extracts and formats the cold rent price.
        
        Args:
            listing_data: Dictionary containing listing data
            
        Returns:
            Formatted price string or 'N/A'
        """
        price = listing_data.get('preis')
        if price:
            return str(price).strip()
        return 'N/A'

    def _extract_sqm(self, listing_data: dict) -> str:
        """
        Extracts and formats the square meters.
        
        Args:
            listing_data: Dictionary containing listing data
            
        Returns:
            Formatted square meters string or 'N/A'
        """
        groesse = listing_data.get('groesse')
        if groesse:
            return str(groesse).strip()
        return 'N/A'

    def _extract_rooms(self, listing_data: dict) -> str:
        """
        Extracts and formats the number of rooms.
        
        Args:
            listing_data: Dictionary containing listing data
            
        Returns:
            Formatted room count string or '1'
        """
        rooms = listing_data.get('anzahl_zimmer')
        if rooms:
            return str(rooms).strip()
        return '1'

    def _build_listing_url(self, listing_data: dict) -> str:
        """
        Builds the detail page URL for a listing.
        
        Args:
            listing_data: Dictionary containing listing data
            
        Returns:
            Full URL to the listing detail page
        """
        slug = listing_data.get('slug', '')
        wrk_id = listing_data.get('wrk_id', '')

        if slug and wrk_id:
            return f"{self.base_url}/mieten/mietangebote/{slug}-{wrk_id}"

        return 'N/A'

