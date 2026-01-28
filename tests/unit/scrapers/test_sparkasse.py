"""
Unit tests for the SparkasseScraper class.
"""
# pylint: disable=protected-access
# Accessing protected methods is expected when unit testing internal logic.

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from src.scrapers.sparkasse import SparkasseScraper
from src.services.borough_resolver import BoroughResolver


class TestSparkasseScraper(unittest.TestCase):
    """Test cases for the SparkasseScraper."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scraper = SparkasseScraper("sparkasse")

    def test_initialization(self):
        """Test that the scraper initializes with correct properties."""
        self.assertEqual(self.scraper.name, "sparkasse")
        self.assertIn("immobilien.sparkasse.de", self.scraper.url)
        self.assertEqual(
            self.scraper.base_url, "https://immobilien.sparkasse.de"
        )

    def test_extract_listing_links(self):
        """Test extraction of listing links from search results page."""
        html = """
        <html>
            <body>
                <a href="/expose/90091272-2044328.html">Listing 1</a>
                <a href="/expose/90091272-1958587.html">Listing 2</a>
                <a href="/other/page.html">Not a listing</a>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        links = self.scraper._extract_listing_links(soup)

        self.assertEqual(len(links), 2)
        self.assertIn("/expose/90091272-2044328.html", links)
        self.assertIn("/expose/90091272-1958587.html", links)

    def test_extract_listing_links_deduplicates(self):
        """Test that duplicate links are removed."""
        html = """
        <html>
            <body>
                <a href="/expose/90091272-2044328.html">Listing 1</a>
                <a href="/expose/90091272-2044328.html">Same listing again</a>
            </body>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")
        links = self.scraper._extract_listing_links(soup)

        self.assertEqual(len(links), 1)

    def test_find_objektdaten_value(self):
        """Test extraction of values from Objektdaten section."""
        html = """
        <div>
            <dt>Straße</dt>
            <dd>Friedrichstraße</dd>
            <dt>PLZ</dt>
            <dd>10117</dd>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")

        street = self.scraper._find_objektdaten_value(soup, "Straße")
        plz = self.scraper._find_objektdaten_value(soup, "PLZ")

        self.assertEqual(street, "Friedrichstraße")
        self.assertEqual(plz, "10117")

    def test_find_objektdaten_value_not_found(self):
        """Test extraction returns empty when label not found."""
        html = "<div><dt>Something</dt><dd>Value</dd></div>"
        soup = BeautifulSoup(html, "html.parser")

        result = self.scraper._find_objektdaten_value(soup, "Nonexistent")
        self.assertEqual(result, "")

    def test_extract_address_full(self):
        """Test full address extraction with all components."""
        html = """
        <div>
            <dt>Straße</dt><dd>Hauptstraße 123</dd>
            <dt>PLZ</dt><dd>10117</dd>
            <dt>Ort</dt><dd>Berlin</dd>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        address = self.scraper._extract_address(soup)

        self.assertEqual(address, "Hauptstraße 123, 10117 Berlin")

    def test_extract_address_missing_street(self):
        """Test address extraction when street is missing."""
        html = """
        <div>
            <dt>PLZ</dt><dd>10117</dd>
            <dt>Ort</dt><dd>Berlin</dd>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        address = self.scraper._extract_address(soup)

        self.assertEqual(address, "10117 Berlin")

    def test_extract_borough_from_plz(self):
        """Test borough extraction from PLZ using resolver."""
        temp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump({"10117": ["Mitte"]}, temp)
        temp.close()

        try:
            resolver = BoroughResolver(temp.name)
            self.scraper.set_borough_resolver(resolver)

            html = """
            <div>
                <dt>PLZ</dt><dd>10117</dd>
            </div>
            """
            soup = BeautifulSoup(html, "html.parser")
            borough = self.scraper._extract_borough_from_soup(soup)

            self.assertEqual(borough, "Mitte")
        finally:
            Path(temp.name).unlink(missing_ok=True)

    def test_extract_borough_fallback_to_text_search(self):
        """Test borough extraction falls back to text content search."""
        temp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        json.dump({"10243": ["Friedrichshain"]}, temp)
        temp.close()

        try:
            resolver = BoroughResolver(temp.name)
            self.scraper.set_borough_resolver(resolver)

            html = "<div>10243 Berlin</div>"
            soup = BeautifulSoup(html, "html.parser")
            borough = self.scraper._extract_borough_from_soup(soup)

            self.assertEqual(borough, "Friedrichshain")
        finally:
            Path(temp.name).unlink(missing_ok=True)

    def test_extract_price_cold(self):
        """Test cold rent extraction."""
        html = """
        <div>
            <dt>Nettokaltmiete</dt>
            <dd>1.800 €</dd>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        price = self.scraper._extract_price_cold(soup)

        self.assertEqual(price, "1800")

    def test_extract_price_total(self):
        """Test warm rent extraction."""
        html = """
        <div>
            <dt>Warmmiete</dt>
            <dd>2.300 €</dd>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        price = self.scraper._extract_price_total(soup)

        self.assertEqual(price, "2300")

    def test_extract_price_with_decimals(self):
        """Test price extraction with decimal values."""
        html = """
        <div>
            <dt>Nettokaltmiete</dt>
            <dd>537,62 €</dd>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        price = self.scraper._extract_price_cold(soup)

        self.assertEqual(price, "537.62")

    def test_extract_price_not_found(self):
        """Test price extraction returns N/A when not found."""
        html = "<div>No price here</div>"
        soup = BeautifulSoup(html, "html.parser")
        price = self.scraper._extract_price_cold(soup)

        self.assertEqual(price, "N/A")

    def test_extract_sqm(self):
        """Test square meters extraction."""
        html = """
        <div>
            <dt>Wohnfläche</dt>
            <dd>92,1 m²</dd>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        sqm = self.scraper._extract_sqm(soup)

        self.assertEqual(sqm, "92.1")

    def test_extract_sqm_not_found(self):
        """Test sqm extraction returns N/A when not found."""
        html = "<div>No size here</div>"
        soup = BeautifulSoup(html, "html.parser")
        sqm = self.scraper._extract_sqm(soup)

        self.assertEqual(sqm, "N/A")

    def test_extract_rooms(self):
        """Test room count extraction."""
        html = """
        <div>
            <dt>Anzahl Zimmer</dt>
            <dd>3</dd>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        rooms = self.scraper._extract_rooms(soup)

        self.assertEqual(rooms, "3")

    def test_extract_rooms_with_decimal(self):
        """Test room count extraction with half rooms."""
        html = """
        <div>
            <dt>Anzahl Zimmer</dt>
            <dd>2,5</dd>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        rooms = self.scraper._extract_rooms(soup)

        self.assertEqual(rooms, "2.5")

    def test_extract_rooms_default(self):
        """Test room count defaults to 1 when not found."""
        html = "<div>No rooms here</div>"
        soup = BeautifulSoup(html, "html.parser")
        rooms = self.scraper._extract_rooms(soup)

        self.assertEqual(rooms, "1")

    def test_clean_text(self):
        """Test text cleaning utility method."""
        self.assertEqual(self.scraper._clean_text("1.800 €"), "1.800")
        self.assertEqual(self.scraper._clean_text("92,1 m²"), "92,1")
        self.assertEqual(self.scraper._clean_text("  extra  spaces  "), "extra spaces")
        self.assertEqual(self.scraper._clean_text(None), "N/A")
        self.assertEqual(self.scraper._clean_text(""), "N/A")

    def test_parse_price(self):
        """Test price parsing and normalization."""
        self.assertEqual(self.scraper._parse_price("1.800 €"), "1800")
        self.assertEqual(self.scraper._parse_price("537,62 €"), "537.62")
        self.assertEqual(self.scraper._parse_price(""), "N/A")

    @patch("requests.Session.get")
    def test_get_current_listings_empty_page(self, mock_get):
        """Test handling of empty search results."""
        mock_response = Mock()
        mock_response.text = "<html><body>No listings</body></html>"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        listings, seen_ids = self.scraper.get_current_listings()

        self.assertEqual(len(listings), 0)
        self.assertEqual(len(seen_ids), 0)

    @patch("requests.Session.get")
    def test_get_current_listings_tracks_known(self, mock_get):
        """Test that known listings are tracked in seen_ids."""
        search_html = """
        <html>
            <body>
                <a href="/expose/known-listing.html">Known</a>
            </body>
        </html>
        """
        mock_response = Mock()
        mock_response.text = search_html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        known_url = "https://immobilien.sparkasse.de/expose/known-listing.html"
        from src.core.listing import Listing

        known_listings = {
            known_url: Listing(source="sparkasse", identifier=known_url)
        }

        listings, seen_ids = self.scraper.get_current_listings(known_listings)

        self.assertEqual(len(listings), 0)
        self.assertIn(known_url, seen_ids)

    @patch("requests.Session.get")
    def test_request_exception_handling(self, mock_get):
        """Test that request exceptions are propagated."""
        import requests

        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

        with self.assertRaises(requests.exceptions.RequestException):
            self.scraper.get_current_listings()


if __name__ == "__main__":
    unittest.main()
