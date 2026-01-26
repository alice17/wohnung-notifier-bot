"""
Unit tests for the OhneMaklerScraper class.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from src.scrapers.ohnemakler import OhneMaklerScraper
from src.services.borough_resolver import BoroughResolver


class TestOhneMaklerScraperInitialization(unittest.TestCase):
    """Test cases for OhneMaklerScraper initialization."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scraper = OhneMaklerScraper("ohnemakler")

    def test_initialization(self):
        """Test that the scraper initializes with correct properties."""
        self.assertEqual(self.scraper.name, "ohnemakler")
        self.assertEqual(
            self.scraper.url,
            "https://www.ohne-makler.net/immobilien/wohnung-mieten/berlin/berlin/"
        )
        self.assertEqual(
            self.scraper.BASE_URL,
            "https://www.ohne-makler.net"
        )

    def test_initialization_custom_name(self):
        """Test initialization with custom name."""
        scraper = OhneMaklerScraper("custom_ohnemakler")
        self.assertEqual(scraper.name, "custom_ohnemakler")


class TestOhneMaklerScraperTextCleaning(unittest.TestCase):
    """Test cases for text cleaning methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = OhneMaklerScraper("ohnemakler")

    def test_clean_text_normal(self):
        """Test text cleaning with normal text."""
        self.assertEqual(self.scraper._clean_text("  Hello   World  "), "Hello World")

    def test_clean_text_none(self):
        """Test text cleaning with None."""
        self.assertEqual(self.scraper._clean_text(None), "N/A")

    def test_clean_text_empty(self):
        """Test text cleaning with empty string."""
        self.assertEqual(self.scraper._clean_text(""), "N/A")

    def test_clean_text_with_currency(self):
        """Test text cleaning removes currency symbol."""
        self.assertEqual(self.scraper._clean_text("1.200 €"), "1.200")

    def test_clean_text_with_sqm_symbol(self):
        """Test text cleaning removes square meter symbol."""
        self.assertEqual(self.scraper._clean_text("65 m²"), "65")

    def test_clean_text_trailing_punctuation(self):
        """Test text cleaning removes trailing punctuation."""
        self.assertEqual(self.scraper._clean_text("Hello World."), "Hello World")
        self.assertEqual(self.scraper._clean_text("Hello World,"), "Hello World")


class TestOhneMaklerScraperPriceExtraction(unittest.TestCase):
    """Test cases for price extraction methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = OhneMaklerScraper("ohnemakler")

    def test_extract_price_value_simple(self):
        """Test price extraction with simple value."""
        self.assertEqual(self.scraper._extract_price_value("800 €"), "800")

    def test_extract_price_value_thousands(self):
        """Test price extraction with thousands separator."""
        self.assertEqual(self.scraper._extract_price_value("1.200 €"), "1.200")

    def test_extract_price_value_with_decimal(self):
        """Test price extraction with decimal."""
        self.assertEqual(self.scraper._extract_price_value("1.200,50 €"), "1.200,50")

    def test_extract_price_value_with_note(self):
        """Test price extraction with note (zzgl. NK)."""
        self.assertEqual(
            self.scraper._extract_price_value("1.800 € (zzgl. NK)"),
            "1.800"
        )

    def test_extract_price_value_no_match(self):
        """Test price extraction with no price."""
        self.assertIsNone(self.scraper._extract_price_value("No price here"))

    def test_extract_price_value_empty(self):
        """Test price extraction with empty string."""
        self.assertIsNone(self.scraper._extract_price_value(""))


class TestOhneMaklerScraperPricingFromDetail(unittest.TestCase):
    """Test cases for pricing extraction from detail page."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = OhneMaklerScraper("ohnemakler")

    def test_extract_pricing_from_detail_complete(self):
        """Test pricing extraction with complete data."""
        html = """
        <table>
            <tr>
                <td>Kaltmiete</td>
                <td>1.200 €</td>
            </tr>
            <tr>
                <td>Summe Nebenkosten/Heizkosten</td>
                <td>200 €</td>
            </tr>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        price_cold, price_total = self.scraper._extract_pricing_from_detail(soup)

        self.assertEqual(price_cold, "1200")
        self.assertEqual(price_total, "1400")

    def test_extract_pricing_from_detail_only_kaltmiete(self):
        """Test pricing extraction with only Kaltmiete."""
        html = """
        <table>
            <tr>
                <td>Kaltmiete</td>
                <td>900 €</td>
            </tr>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        price_cold, price_total = self.scraper._extract_pricing_from_detail(soup)

        self.assertEqual(price_cold, "900")
        self.assertIsNone(price_total)

    def test_extract_pricing_from_detail_no_data(self):
        """Test pricing extraction with no pricing data."""
        html = "<table><tr><td>Other data</td><td>Value</td></tr></table>"
        soup = BeautifulSoup(html, "lxml")
        price_cold, price_total = self.scraper._extract_pricing_from_detail(soup)

        self.assertIsNone(price_cold)
        self.assertIsNone(price_total)

    def test_extract_pricing_from_detail_summe_nebenkosten(self):
        """Test pricing extraction with 'summe nebenkosten' variant."""
        html = """
        <table>
            <tr>
                <td>Kaltmiete</td>
                <td>1.000 €</td>
            </tr>
            <tr>
                <td>Summe Nebenkosten</td>
                <td>150 €</td>
            </tr>
        </table>
        """
        soup = BeautifulSoup(html, "lxml")
        price_cold, price_total = self.scraper._extract_pricing_from_detail(soup)

        self.assertEqual(price_cold, "1000")
        self.assertEqual(price_total, "1150")


class TestOhneMaklerScraperIdentifierExtraction(unittest.TestCase):
    """Test cases for identifier extraction."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = OhneMaklerScraper("ohnemakler")

    def test_extract_identifier_fast_valid(self):
        """Test fast identifier extraction with valid href."""
        html = '<a href="/immobilie/12345/">Listing</a>'
        soup = BeautifulSoup(html, "lxml").find("a")

        identifier = self.scraper._extract_identifier_fast(soup)
        self.assertEqual(
            identifier,
            "https://www.ohne-makler.net/immobilie/12345/"
        )

    def test_extract_identifier_fast_no_href(self):
        """Test fast identifier extraction without href."""
        html = "<a>No href</a>"
        soup = BeautifulSoup(html, "lxml").find("a")

        identifier = self.scraper._extract_identifier_fast(soup)
        self.assertIsNone(identifier)


class TestOhneMaklerScraperBoroughResolution(unittest.TestCase):
    """Test cases for borough resolution."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = OhneMaklerScraper("ohnemakler")

    def test_get_borough_from_zip_with_resolver(self):
        """Test borough resolution with resolver."""
        temp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({"10245": ["Friedrichshain"]}, temp)
        temp.close()

        try:
            resolver = BoroughResolver(temp.name)
            self.scraper.set_borough_resolver(resolver)

            borough = self.scraper._get_borough_from_zip("10245")
            self.assertEqual(borough, "Friedrichshain")
        finally:
            Path(temp.name).unlink(missing_ok=True)

    def test_get_borough_from_zip_no_resolver(self):
        """Test borough resolution without resolver returns N/A."""
        borough = self.scraper._get_borough_from_zip("10245")
        self.assertEqual(borough, "N/A")

    def test_get_borough_from_zip_unknown_zip(self):
        """Test borough resolution with unknown zip code."""
        temp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({"10245": ["Friedrichshain"]}, temp)
        temp.close()

        try:
            resolver = BoroughResolver(temp.name)
            self.scraper.set_borough_resolver(resolver)

            borough = self.scraper._get_borough_from_zip("99999")
            self.assertEqual(borough, "N/A")
        finally:
            Path(temp.name).unlink(missing_ok=True)


class TestOhneMaklerScraperGermanNumberNormalization(unittest.TestCase):
    """Test cases for German number normalization."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = OhneMaklerScraper("ohnemakler")

    def test_normalize_german_number_thousands(self):
        """Test normalization of thousands separator."""
        self.assertEqual(self.scraper._normalize_german_number("1.200"), "1200")

    def test_normalize_german_number_thousands_and_decimal(self):
        """Test normalization of thousands and decimal."""
        self.assertEqual(self.scraper._normalize_german_number("1.200,50"), "1200.50")

    def test_normalize_german_number_decimal_only(self):
        """Test normalization of decimal only."""
        self.assertEqual(self.scraper._normalize_german_number("65,5"), "65.5")

    def test_normalize_german_number_empty(self):
        """Test normalization of empty string."""
        self.assertEqual(self.scraper._normalize_german_number(""), "")

    def test_normalize_german_number_na(self):
        """Test normalization of N/A."""
        self.assertEqual(self.scraper._normalize_german_number("N/A"), "N/A")


class TestOhneMaklerScraperRoomNormalization(unittest.TestCase):
    """Test cases for room format normalization."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = OhneMaklerScraper("ohnemakler")

    def test_normalize_rooms_format_comma(self):
        """Test room normalization with comma decimal."""
        self.assertEqual(self.scraper._normalize_rooms_format("2,5"), "2.5")

    def test_normalize_rooms_format_dot(self):
        """Test room normalization with dot decimal."""
        self.assertEqual(self.scraper._normalize_rooms_format("2.5"), "2.5")

    def test_normalize_rooms_format_whole_number(self):
        """Test room normalization with whole number."""
        self.assertEqual(self.scraper._normalize_rooms_format("3"), "3")

    def test_normalize_rooms_format_na(self):
        """Test room normalization with N/A."""
        self.assertEqual(self.scraper._normalize_rooms_format("N/A"), "N/A")


class TestOhneMaklerScraperHTTPRequests(unittest.TestCase):
    """Test cases for HTTP request handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = OhneMaklerScraper("ohnemakler")

    @patch("src.scrapers.ohnemakler.requests.get")
    def test_get_current_listings_empty_page(self, mock_get):
        """Test get_current_listings with no listings found."""
        mock_response = Mock()
        mock_response.text = "<html><body>No listings</body></html>"
        mock_response.raise_for_status = Mock()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_get.return_value = mock_response

        listings, seen_known_ids = self.scraper.get_current_listings()

        self.assertEqual(len(listings), 0)
        self.assertEqual(len(seen_known_ids), 0)

    @patch("src.scrapers.ohnemakler.requests.get")
    def test_get_current_listings_request_error(self, mock_get):
        """Test get_current_listings with request error."""
        import requests

        mock_get.side_effect = requests.exceptions.RequestException("Connection error")

        with self.assertRaises(requests.exceptions.RequestException):
            self.scraper.get_current_listings()

    @patch("src.scrapers.ohnemakler.requests.get")
    def test_fetch_detail_page_pricing_success(self, mock_get):
        """Test fetching detail page pricing successfully."""
        detail_html = """
        <table>
            <tr><td>Kaltmiete</td><td>1.000 €</td></tr>
            <tr><td>Summe Nebenkosten/Heizkosten</td><td>200 €</td></tr>
        </table>
        """
        mock_response = Mock()
        mock_response.text = detail_html
        mock_response.raise_for_status = Mock()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_get.return_value = mock_response

        price_cold, price_total = self.scraper._fetch_detail_page_pricing(
            "https://www.ohne-makler.net/immobilie/12345/"
        )

        self.assertEqual(price_cold, "1000")
        self.assertEqual(price_total, "1200")

    @patch("src.scrapers.ohnemakler.requests.get")
    def test_fetch_detail_page_pricing_failure(self, mock_get):
        """Test fetching detail page pricing with request failure."""
        import requests

        mock_get.side_effect = requests.exceptions.RequestException("Timeout")

        price_cold, price_total = self.scraper._fetch_detail_page_pricing(
            "https://www.ohne-makler.net/immobilie/12345/"
        )

        self.assertIsNone(price_cold)
        self.assertIsNone(price_total)


class TestOhneMaklerScraperEarlyTermination(unittest.TestCase):
    """Test cases for early termination optimization."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = OhneMaklerScraper("ohnemakler")

    def test_parse_html_optimized_early_termination(self):
        """Test that parsing stops when known listing is encountered."""
        html_content = """
        <html><body>
        <a href="/immobilie/11111/" data-om-id="11111">
            <span class="text-primary-500 text-xl">900 €</span>
            <div class="flex items-center text-slate-800">
                <span>10245 Berlin (Friedrichshain)</span>
            </div>
            <div title="Zimmer">
                <span class="text-slate-700 font-medium">2</span>
            </div>
            <div title="Wohnfläche">
                <span class="text-slate-700 font-medium">65</span>
            </div>
        </a>
        <a href="/immobilie/22222/" data-om-id="22222">
            <span class="text-primary-500 text-xl">1000 €</span>
        </a>
        <a href="/immobilie/33333/" data-om-id="33333">
            <span class="text-primary-500 text-xl">1100 €</span>
        </a>
        </body></html>
        """
        known_ids = {"https://www.ohne-makler.net/immobilie/22222/"}

        with patch.object(
            self.scraper, "_fetch_detail_page_pricing", return_value=(None, None)
        ):
            listings, seen_known_ids = self.scraper._parse_html_optimized(
                html_content, known_ids
            )

        # Should only have the first listing (before known one)
        self.assertEqual(len(listings), 1)
        self.assertIn(
            "https://www.ohne-makler.net/immobilie/11111/",
            listings
        )
        # Should not have the third listing (after early termination)
        self.assertNotIn(
            "https://www.ohne-makler.net/immobilie/33333/",
            listings
        )
        # Known listing should be in seen_known_ids
        self.assertIn(
            "https://www.ohne-makler.net/immobilie/22222/",
            seen_known_ids
        )

    def test_parse_html_optimized_no_known_listings(self):
        """Test parsing without known listings processes all."""
        html_content = """
        <html><body>
        <a href="/immobilie/11111/" data-om-id="11111">
            <span class="text-primary-500 text-xl">900 €</span>
            <div class="flex items-center text-slate-800">
                <span>10245 Berlin</span>
            </div>
            <div title="Zimmer">
                <span class="text-slate-700 font-medium">2</span>
            </div>
            <div title="Wohnfläche">
                <span class="text-slate-700 font-medium">65</span>
            </div>
        </a>
        <a href="/immobilie/22222/" data-om-id="22222">
            <span class="text-primary-500 text-xl">1000 €</span>
            <div class="flex items-center text-slate-800">
                <span>10247 Berlin</span>
            </div>
            <div title="Zimmer">
                <span class="text-slate-700 font-medium">3</span>
            </div>
            <div title="Wohnfläche">
                <span class="text-slate-700 font-medium">80</span>
            </div>
        </a>
        </body></html>
        """
        with patch.object(
            self.scraper, "_fetch_detail_page_pricing", return_value=(None, None)
        ):
            listings, seen_known_ids = self.scraper._parse_html_optimized(
                html_content, set()
            )

        self.assertEqual(len(listings), 2)
        self.assertEqual(len(seen_known_ids), 0)


class TestOhneMaklerScraperListingParsing(unittest.TestCase):
    """Test cases for listing parsing."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = OhneMaklerScraper("ohnemakler")

    def test_parse_listing_details_complete(self):
        """Test parsing listing details with all fields."""
        html = """
        <a href="/immobilie/12345/" data-om-id="12345">
            <span class="text-primary-500 text-xl">1.200 €</span>
            <div class="flex items-center text-slate-800">
                <span>Musterstraße 10, 10245 Berlin (Friedrichshain)</span>
            </div>
            <div title="Zimmer">
                <span class="text-slate-700 font-medium">2,5</span>
            </div>
            <div title="Wohnfläche">
                <span class="text-slate-700 font-medium">65,5</span>
            </div>
        </a>
        """
        soup = BeautifulSoup(html, "lxml").find("a")

        with patch.object(
            self.scraper, "_fetch_detail_page_pricing", return_value=("1000", "1200")
        ):
            listing = self.scraper._parse_listing_details(soup)

        self.assertIsNotNone(listing)
        self.assertEqual(
            listing.identifier,
            "https://www.ohne-makler.net/immobilie/12345/"
        )
        self.assertEqual(listing.source, "ohnemakler")
        self.assertEqual(listing.price_cold, "1000")
        self.assertEqual(listing.price_total, "1200")
        self.assertEqual(listing.rooms, "2.5")
        self.assertEqual(listing.sqm, "65.5")
        self.assertFalse(listing.wbs)

    def test_parse_listing_details_no_data_om_id(self):
        """Test parsing listing without data-om-id returns None."""
        html = '<a href="/immobilie/12345/">Listing</a>'
        soup = BeautifulSoup(html, "lxml").find("a")

        listing = self.scraper._parse_listing_details(soup)
        self.assertIsNone(listing)

    def test_parse_listing_details_no_href(self):
        """Test parsing listing without href returns None."""
        html = '<a data-om-id="12345">Listing</a>'
        soup = BeautifulSoup(html, "lxml").find("a")

        listing = self.scraper._parse_listing_details(soup)
        self.assertIsNone(listing)

    def test_parse_listing_details_address_formatting(self):
        """Test address formatting removes borough in parentheses."""
        html = """
        <a href="/immobilie/12345/" data-om-id="12345">
            <div class="flex items-center text-slate-800">
                <span>10245 Berlin (Friedrichshain)</span>
            </div>
        </a>
        """
        soup = BeautifulSoup(html, "lxml").find("a")

        with patch.object(
            self.scraper, "_fetch_detail_page_pricing", return_value=(None, None)
        ):
            listing = self.scraper._parse_listing_details(soup)

        self.assertIsNotNone(listing)
        self.assertEqual(listing.address, "10245 Berlin")


class TestOhneMaklerScraperIntegration(unittest.TestCase):
    """Integration tests with realistic HTML structure."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = OhneMaklerScraper("ohnemakler")

    @patch("src.scrapers.ohnemakler.requests.get")
    def test_full_scraping_flow(self, mock_get):
        """Test complete scraping flow with realistic HTML."""
        listing_html = """
        <html><body>
        <a href="/immobilie/98765/" data-om-id="98765">
            <span class="text-primary-500 text-xl">950 €</span>
            <div class="flex items-center text-slate-800">
                <span>Teststraße 42, 10961 Berlin (Kreuzberg)</span>
            </div>
            <div title="Zimmer">
                <span class="text-slate-700 font-medium">3</span>
            </div>
            <div title="Wohnfläche">
                <span class="text-slate-700 font-medium">75</span>
            </div>
        </a>
        </body></html>
        """
        detail_html = """
        <table>
            <tr><td>Kaltmiete</td><td>950 €</td></tr>
            <tr><td>Summe Nebenkosten/Heizkosten</td><td>200 €</td></tr>
        </table>
        """

        # Configure mock to return different responses for list and detail pages
        def mock_get_side_effect(url, **kwargs):
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)

            if "immobilie/98765" in url:
                mock_response.text = detail_html
            else:
                mock_response.text = listing_html

            return mock_response

        mock_get.side_effect = mock_get_side_effect

        # Set up borough resolver
        temp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({"10961": ["Kreuzberg"]}, temp)
        temp.close()

        try:
            resolver = BoroughResolver(temp.name)
            self.scraper.set_borough_resolver(resolver)

            listings, seen_known_ids = self.scraper.get_current_listings()

            self.assertEqual(len(listings), 1)
            listing = list(listings.values())[0]

            self.assertEqual(
                listing.identifier,
                "https://www.ohne-makler.net/immobilie/98765/"
            )
            self.assertEqual(listing.source, "ohnemakler")
            self.assertEqual(listing.price_cold, "950")
            self.assertEqual(listing.price_total, "1150")
            self.assertEqual(listing.rooms, "3")
            self.assertEqual(listing.sqm, "75")
            self.assertEqual(listing.borough, "Kreuzberg")
            self.assertIn("Teststraße 42", listing.address)
            self.assertFalse(listing.wbs)
        finally:
            Path(temp.name).unlink(missing_ok=True)

    @patch("src.scrapers.ohnemakler.requests.get")
    def test_scraping_with_known_listings(self, mock_get):
        """Test scraping correctly handles known listings."""
        html_content = """
        <html><body>
        <a href="/immobilie/11111/" data-om-id="11111">
            <span class="text-primary-500 text-xl">800 €</span>
            <div class="flex items-center text-slate-800">
                <span>10115 Berlin</span>
            </div>
            <div title="Zimmer">
                <span class="text-slate-700 font-medium">2</span>
            </div>
            <div title="Wohnfläche">
                <span class="text-slate-700 font-medium">50</span>
            </div>
        </a>
        <a href="/immobilie/22222/" data-om-id="22222">
            <span class="text-primary-500 text-xl">900 €</span>
        </a>
        </body></html>
        """

        def mock_get_side_effect(url, **kwargs):
            mock_response = Mock()
            mock_response.text = html_content
            mock_response.raise_for_status = Mock()
            mock_response.__enter__ = Mock(return_value=mock_response)
            mock_response.__exit__ = Mock(return_value=False)

            # For detail page, return minimal pricing
            if "immobilie/11111" in url:
                mock_response.text = "<table></table>"

            return mock_response

        mock_get.side_effect = mock_get_side_effect

        known_listings = {
            "https://www.ohne-makler.net/immobilie/22222/": Mock()
        }

        listings, seen_known_ids = self.scraper.get_current_listings(known_listings)

        # Should only have the new listing
        self.assertEqual(len(listings), 1)
        self.assertIn(
            "https://www.ohne-makler.net/immobilie/11111/",
            listings
        )
        # Known listing should be in seen_known_ids
        self.assertIn(
            "https://www.ohne-makler.net/immobilie/22222/",
            seen_known_ids
        )


if __name__ == "__main__":
    unittest.main()
