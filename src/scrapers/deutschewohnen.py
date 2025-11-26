"""
Deutsche Wohnen Scraper.

This module defines the DeutscheWohnenScraper class for fetching apartment
listings from deutsche-wohnen.com via the wohnraumkarte.de API.

Features:
---------
- Uses the wohnraumkarte.de API with 'dataSet=deuwo' filter
- Inherits optimized live update logic from WohnraumkarteScraper

Limitations:
-----------
- Warm rent (price_total) is NOT available from the API
- Therefore, price_total remains 'N/A' for all listings
"""
from src.scrapers.wohnraumkarte import WohnraumkarteScraper


class DeutscheWohnenScraper(WohnraumkarteScraper):
    """
    Scraper for apartment listings from deutsche-wohnen.com.

    Uses the wohnraumkarte.de API with Deutsche Wohnen-specific filtering.
    """

    def __init__(self, name: str):
        """
        Initializes the Deutsche Wohnen scraper.

        Args:
            name: Display name for this scraper instance.
        """
        super().__init__(
            name=name,
            base_url="https://www.deutsche-wohnen.com",
            referer="https://www.deutsche-wohnen.com/",
        )

    def _get_listing_url_path(self, slug: str, wrk_id: str) -> str:
        """
        Returns the URL path for a Deutsche Wohnen listing.

        Args:
            slug: The URL-friendly listing slug.
            wrk_id: The wohnraumkarte listing ID.

        Returns:
            The path portion of the listing URL.
        """
        return f"/mieten/mietangebote/{slug}-{wrk_id}"

    def _get_extra_api_params(self) -> dict:
        """
        Returns Deutsche Wohnen-specific API parameters.

        Returns:
            Dictionary with 'dataSet' parameter for filtering.
        """
        return {'dataSet': 'deuwo'}
