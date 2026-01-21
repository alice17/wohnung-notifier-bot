"""
Unit tests for the BerlinovoScraper class.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.scrapers.berlinovo import BerlinovoScraper
from src.services.borough_resolver import BoroughResolver


class TestBerlinovoScraper(unittest.TestCase):
    """Test cases for the BerlinovoScraper."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scraper = BerlinovoScraper("berlinovo")

    def test_initialization(self):
        """Test that the scraper initializes with correct properties."""
        self.assertEqual(self.scraper.name, "berlinovo")
        self.assertEqual(self.scraper.url, "https://www.berlinovo.de/de/wohnungen/suche")
        self.assertEqual(self.scraper.BASE_URL, "https://www.berlinovo.de")

    def test_clean_text(self):
        """Test text cleaning functionality."""
        self.assertEqual(self.scraper._clean_text("  Hello   World  "), "Hello World")
        self.assertEqual(self.scraper._clean_text(None), "N/A")
        self.assertEqual(self.scraper._clean_text(""), "N/A")

    def test_clean_numeric_with_currency(self):
        """Test numeric cleaning with currency symbol."""
        self.assertEqual(self.scraper._clean_numeric("1.001,86 €"), "1001.86")
        self.assertEqual(self.scraper._clean_numeric("901,86 €"), "901.86")

    def test_clean_numeric_with_unit(self):
        """Test numeric cleaning with unit."""
        self.assertEqual(self.scraper._clean_numeric("65,5 m²"), "65.5")

    def test_clean_numeric_missing(self):
        """Test numeric cleaning with missing value."""
        self.assertEqual(self.scraper._clean_numeric(None), "N/A")
        self.assertEqual(self.scraper._clean_numeric(""), "N/A")

    def test_extract_borough_from_address(self):
        """Test borough extraction from address with ZIP code."""
        temp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({"12353": ["Buckow"]}, temp)
        temp.close()

        try:
            resolver = BoroughResolver(temp.name)
            self.scraper.set_borough_resolver(resolver)

            borough = self.scraper._extract_borough_from_address(
                "Dröpkeweg 13, 12353 Berlin"
            )
            self.assertEqual(borough, "Buckow")
        finally:
            Path(temp.name).unlink(missing_ok=True)

    def test_extract_borough_from_address_no_zip(self):
        """Test borough extraction returns N/A when no ZIP code."""
        borough = self.scraper._extract_borough_from_address("Unknown Address")
        self.assertEqual(borough, "N/A")

    def test_check_wbs_required(self):
        """Test WBS detection when required."""
        mock_card = Mock()
        mock_card.get_text.return_value = "WBS-Wohnung für 2 Personen nötig"
        self.assertTrue(self.scraper._check_wbs(mock_card))

    def test_check_wbs_not_required(self):
        """Test WBS detection when not required."""
        mock_card = Mock()
        mock_card.get_text.return_value = "Schöne 2-Zimmer-Wohnung"
        self.assertFalse(self.scraper._check_wbs(mock_card))

    def test_check_wbs_erforderlich(self):
        """Test WBS detection with 'erforderlich' keyword."""
        mock_card = Mock()
        mock_card.get_text.return_value = "WBS erforderlich"
        self.assertTrue(self.scraper._check_wbs(mock_card))

    def test_extract_field_value(self):
        """Test field value extraction from card text."""
        mock_card = Mock()
        mock_card.get_text.return_value = (
            "Title\nWarmmiete\n1.001,86 €\nZimmer\n2,0\n"
        )

        warmmiete = self.scraper._extract_field_value(mock_card, ["Warmmiete"])
        self.assertEqual(warmmiete, "1.001,86 €")

        zimmer = self.scraper._extract_field_value(mock_card, ["Zimmer"])
        self.assertEqual(zimmer, "2,0")

    def test_extract_field_value_not_found(self):
        """Test field value extraction when field not found."""
        mock_card = Mock()
        mock_card.get_text.return_value = "Some other text"

        result = self.scraper._extract_field_value(mock_card, ["Warmmiete"])
        self.assertIsNone(result)

    @patch("src.scrapers.berlinovo.requests.get")
    def test_get_current_listings_empty(self, mock_get):
        """Test get_current_listings with no listings found."""
        mock_response = Mock()
        mock_response.text = "<html><body>No listings</body></html>"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        listings, seen_known_ids = self.scraper.get_current_listings()
        self.assertEqual(len(listings), 0)
        self.assertEqual(len(seen_known_ids), 0)

    @patch("src.scrapers.berlinovo.requests.get")
    def test_get_current_listings_filters_known(self, mock_get):
        """Test that known listings are filtered out."""
        html_content = """
        <html><body>
        <article class="node--type-wohnung">
            <a href="/de/wohnung/test-listing-1">Details</a>
            <div>Warmmiete: 1000 €</div>
        </article>
        <article class="node--type-wohnung">
            <a href="/de/wohnung/test-listing-2">Details</a>
            <div>Warmmiete: 1200 €</div>
        </article>
        </body></html>
        """
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        known_listings = {
            "https://www.berlinovo.de/de/wohnung/test-listing-1": Mock()
        }

        listings, seen_known_ids = self.scraper.get_current_listings(known_listings)

        # Should only return the second listing (first one is filtered as known)
        self.assertNotIn(
            "https://www.berlinovo.de/de/wohnung/test-listing-1", listings
        )
        # The known listing should be in seen_known_ids
        self.assertIn(
            "https://www.berlinovo.de/de/wohnung/test-listing-1", seen_known_ids
        )

    @patch("src.scrapers.berlinovo.requests.get")
    def test_fetch_page_with_pagination(self, mock_get):
        """Test that pagination parameter is added for pages > 0."""
        mock_response = Mock()
        mock_response.text = "<html><body></body></html>"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        self.scraper._fetch_page(page=2)

        # Check that page parameter was included
        call_args = mock_get.call_args
        self.assertIn("params", call_args.kwargs)
        self.assertEqual(call_args.kwargs["params"]["page"], "2")

    @patch("src.scrapers.berlinovo.requests.get")
    def test_fetch_page_first_page(self, mock_get):
        """Test that page parameter is not added for first page."""
        mock_response = Mock()
        mock_response.text = "<html><body></body></html>"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        self.scraper._fetch_page(page=0)

        # Check that page parameter was not included
        call_args = mock_get.call_args
        self.assertIn("params", call_args.kwargs)
        self.assertNotIn("page", call_args.kwargs["params"])

    def test_parse_html_no_listings(self):
        """Test parsing HTML with no listings."""
        html_content = "<html><body><div>No apartments available</div></body></html>"
        listings = self.scraper._parse_html(html_content)
        self.assertEqual(len(listings), 0)

    def test_normalize_rooms_format(self):
        """Test room format normalization inherited from base."""
        self.assertEqual(self.scraper._normalize_rooms_format("2,5"), "2.5")
        self.assertEqual(self.scraper._normalize_rooms_format("3"), "3")
        self.assertEqual(self.scraper._normalize_rooms_format("N/A"), "N/A")


class TestBerlinovoScraperRoomExtraction(unittest.TestCase):
    """Test cases for room extraction from various formats."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = BerlinovoScraper("berlinovo")

    def test_extract_rooms_from_title_compound_word(self):
        """Test room extraction when 'Zimmer' appears in title compound word."""
        from unittest.mock import Mock

        mock_card = Mock()
        mock_card.select_one.return_value = None
        mock_card.get_text.return_value = (
            "Schöne 2-Zimmer-Wohnung mit Balkon in Staaken zu vermieten!"
        )

        rooms = self.scraper._extract_rooms(mock_card)
        self.assertEqual(rooms, "2")

    def test_extract_rooms_from_label_below(self):
        """Test room extraction when value is on line below label."""
        from unittest.mock import Mock

        mock_card = Mock()
        mock_card.select_one.return_value = None
        mock_card.get_text.return_value = "Zimmer\n2,0\n"

        rooms = self.scraper._extract_rooms(mock_card)
        self.assertEqual(rooms, "2,0")

    def test_extract_rooms_with_decimal(self):
        """Test room extraction with half rooms (e.g., 2.5)."""
        from unittest.mock import Mock

        mock_card = Mock()
        mock_card.select_one.return_value = None
        mock_card.get_text.return_value = "Große 2,5-Zimmer-Wohnung"

        rooms = self.scraper._extract_rooms(mock_card)
        self.assertEqual(rooms, "2,5")

    def test_extract_rooms_with_colon(self):
        """Test room extraction with colon separator."""
        from unittest.mock import Mock

        mock_card = Mock()
        mock_card.select_one.return_value = None
        mock_card.get_text.return_value = "Zimmer: 3"

        rooms = self.scraper._extract_rooms(mock_card)
        self.assertEqual(rooms, "3")


class TestBerlinovoScraperIntegration(unittest.TestCase):
    """Integration tests for BerlinovoScraper with realistic HTML."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = BerlinovoScraper("berlinovo")

    def test_parse_realistic_listing_card(self):
        """Test parsing a realistic listing card structure."""
        from bs4 import BeautifulSoup

        html = """
        <article class="node--type-wohnung">
            <a href="/de/wohnung/seniorenwohnung-buckow-123">
                <img src="/image.jpg" alt="Dröpkeweg"/>
            </a>
            <h3>Neubauprojekt: Seniorenwohnen in Buckow</h3>
            <div class="field--name-field-adresse">
                Dröpkeweg 13<br/>12353 Berlin<br/>Deutschland
            </div>
            <div class="listing-details">
                Verfügbar ab
                01.05.2026
                Warmmiete
                1.001,86 €
                Bruttokaltmiete
                901,86 €
                Zimmer
                2,0
                Etage
                1
            </div>
        </article>
        """
        soup = BeautifulSoup(html, "lxml")
        card = soup.select_one("article.node--type-wohnung")

        listing = self.scraper._parse_listing_card(card)

        self.assertIsNotNone(listing)
        self.assertEqual(listing.source, "berlinovo")
        self.assertIn("Dröpkeweg", listing.address)
        self.assertEqual(listing.price_total, "1001.86")
        self.assertEqual(listing.price_cold, "901.86")
        self.assertEqual(listing.rooms, "2.0")
        self.assertIn("berlinovo.de", listing.identifier)


if __name__ == "__main__":
    unittest.main()
