"""
Vonovia Scraper.

This module defines the VonoviaScraper class for fetching apartment
listings from vonovia.de via the wohnraumkarte.de API.

Features:
---------
- Uses the wohnraumkarte.de API (no dataSet filter needed)
- Inherits optimized live update logic from WohnraumkarteScraper

Limitations:
-----------
- Warm rent (price_total) is NOT available from the API
- Therefore, price_total remains 'N/A' for all listings
"""
from src.scrapers.wohnraumkarte import WohnraumkarteScraper


class VonoviaScraper(WohnraumkarteScraper):
    """
    Scraper for apartment listings from vonovia.de.

    Uses the wohnraumkarte.de API to fetch Berlin apartment listings.
    """

    def __init__(self, name: str):
        """
        Initializes the Vonovia scraper.

        Args:
            name: Display name for this scraper instance.
        """
        super().__init__(
            name=name,
            base_url="https://www.vonovia.de",
            referer="https://www.vonovia.de/",
        )

    def _get_listing_url_path(self, slug: str, wrk_id: str) -> str:
        """
        Returns the URL path for a Vonovia listing.

        Args:
            slug: The URL-friendly listing slug.
            wrk_id: The wohnraumkarte listing ID.

        Returns:
            The path portion of the listing URL.
        """
        return f"/zuhause-finden/{slug}-{wrk_id}"
