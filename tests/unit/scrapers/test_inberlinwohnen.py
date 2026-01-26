"""
Unit tests for the InBerlinWohnenScraper class.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from src.scrapers.inberlinwohnen import InBerlinWohnenScraper
from src.services.borough_resolver import BoroughResolver


class TestInBerlinWohnenScraper(unittest.TestCase):
    """Test cases for the InBerlinWohnenScraper."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scraper = InBerlinWohnenScraper("inberlinwohnen")

    def test_initialization(self):
        """Test that the scraper initializes with correct properties."""
        self.assertEqual(self.scraper.name, "inberlinwohnen")
        self.assertEqual(
            self.scraper.url, "https://www.inberlinwohnen.de/wohnungsfinder"
        )

    def test_initialization_custom_name(self):
        """Test initialization with a custom name."""
        scraper = InBerlinWohnenScraper("custom_name")
        self.assertEqual(scraper.name, "custom_name")

    def test_clean_text_basic(self):
        """Test basic text cleaning functionality."""
        self.assertEqual(
            self.scraper._clean_text("  Hello   World  "), "Hello World"
        )

    def test_clean_text_with_euro_symbol(self):
        """Test text cleaning removes euro symbol."""
        self.assertEqual(self.scraper._clean_text("1000 €"), "1000")

    def test_clean_text_with_sqm_unit(self):
        """Test text cleaning removes square meter unit."""
        self.assertEqual(self.scraper._clean_text("75 m²"), "75")

    def test_clean_text_trailing_punctuation(self):
        """Test text cleaning removes trailing punctuation."""
        self.assertEqual(self.scraper._clean_text("Test value."), "Test value")
        self.assertEqual(self.scraper._clean_text("Test value,"), "Test value")

    def test_clean_text_none(self):
        """Test text cleaning with None returns N/A."""
        self.assertEqual(self.scraper._clean_text(None), "N/A")

    def test_clean_text_empty(self):
        """Test text cleaning with empty string returns N/A."""
        self.assertEqual(self.scraper._clean_text(""), "N/A")


class TestInBerlinWohnenScraperIdentifierExtraction(unittest.TestCase):
    """Test cases for identifier extraction functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = InBerlinWohnenScraper("inberlinwohnen")

    def test_extract_identifier_fast_with_valid_link(self):
        """Test identifier extraction from listing with valid link."""
        html = """
        <div id="apartment-123">
            <a>Alle Details</a>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", id="apartment-123")

        # Add href attribute to the link
        link = listing_soup.find("a", string="Alle Details")
        link["href"] = "https://example.com/apartment/123"

        identifier = self.scraper._extract_identifier_fast(listing_soup)
        self.assertEqual(identifier, "https://example.com/apartment/123")

    def test_extract_identifier_fast_no_link(self):
        """Test identifier extraction returns None when no link found."""
        html = '<div id="apartment-123"><span>Some content</span></div>'
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div")

        identifier = self.scraper._extract_identifier_fast(listing_soup)
        self.assertIsNone(identifier)

    def test_extract_identifier_fast_link_without_href(self):
        """Test identifier extraction returns None when link has no href."""
        html = '<div id="apartment-123"><a>Alle Details</a></div>'
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div")

        identifier = self.scraper._extract_identifier_fast(listing_soup)
        self.assertIsNone(identifier)

    def test_extract_known_ids(self):
        """Test extracting known IDs from known listings dict."""
        known_listings = {
            "https://example.com/apartment/1": Mock(),
            "https://example.com/apartment/2": Mock(),
            "https://example.com/apartment/3": Mock(),
        }

        known_ids = self.scraper._extract_known_ids(known_listings)

        self.assertEqual(len(known_ids), 3)
        self.assertIn("https://example.com/apartment/1", known_ids)
        self.assertIn("https://example.com/apartment/2", known_ids)
        self.assertIn("https://example.com/apartment/3", known_ids)


class TestInBerlinWohnenScraperFieldExtraction(unittest.TestCase):
    """Test cases for field extraction functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = InBerlinWohnenScraper("inberlinwohnen")

    def test_extract_field_address(self):
        """Test address field extraction."""
        html = '<dd><button>Teststraße 123, 10115 Berlin</button></dd>'
        soup = BeautifulSoup(html, "lxml")
        dd_element = soup.find("dd")
        details = {}

        self.scraper._extract_field(
            "Adresse:", dd_element, "Teststraße 123, 10115 Berlin", details
        )

        self.assertEqual(details["address"], "Teststraße 123, 10115 Berlin")

    def test_extract_field_address_without_button(self):
        """Test address extraction when there's no button element."""
        html = "<dd>Teststraße 456, 12345 Berlin</dd>"
        soup = BeautifulSoup(html, "lxml")
        dd_element = soup.find("dd")
        details = {}

        self.scraper._extract_field(
            "Adresse:", dd_element, "Teststraße 456, 12345 Berlin", details
        )

        self.assertEqual(details["address"], "Teststraße 456, 12345 Berlin")

    def test_extract_field_sqm(self):
        """Test square meters field extraction."""
        html = "<dd>75,5 m²</dd>"
        soup = BeautifulSoup(html, "lxml")
        dd_element = soup.find("dd")
        details = {}

        self.scraper._extract_field("Wohnfläche:", dd_element, "75,5", details)

        self.assertEqual(details["sqm"], "75.5")

    def test_extract_field_price_cold(self):
        """Test cold rent field extraction."""
        html = "<dd>800,00 €</dd>"
        soup = BeautifulSoup(html, "lxml")
        dd_element = soup.find("dd")
        details = {}

        self.scraper._extract_field("Kaltmiete:", dd_element, "800,00", details)

        self.assertEqual(details["price_cold"], "800.00")

    def test_extract_field_price_total(self):
        """Test total rent field extraction."""
        html = "<dd>1.050,00 €</dd>"
        soup = BeautifulSoup(html, "lxml")
        dd_element = soup.find("dd")
        details = {}

        self.scraper._extract_field("Gesamtmiete:", dd_element, "1.050,00", details)

        self.assertEqual(details["price_total"], "1050.00")

    def test_extract_field_rooms(self):
        """Test rooms field extraction."""
        html = "<dd>3,5</dd>"
        soup = BeautifulSoup(html, "lxml")
        dd_element = soup.find("dd")
        details = {}

        self.scraper._extract_field("Zimmeranzahl:", dd_element, "3,5", details)

        self.assertEqual(details["rooms"], "3.5")

    def test_extract_field_wbs_required(self):
        """Test WBS field extraction when required."""
        html = "<dd>Ja, erforderlich</dd>"
        soup = BeautifulSoup(html, "lxml")
        dd_element = soup.find("dd")
        details = {}

        self.scraper._extract_field("WBS:", dd_element, "Ja, erforderlich", details)

        self.assertTrue(details["wbs"])

    def test_extract_field_wbs_not_required(self):
        """Test WBS field extraction when not required."""
        html = "<dd>nicht erforderlich</dd>"
        soup = BeautifulSoup(html, "lxml")
        dd_element = soup.find("dd")
        details = {}

        self.scraper._extract_field("WBS:", dd_element, "nicht erforderlich", details)

        self.assertFalse(details["wbs"])


class TestInBerlinWohnenScraperBoroughExtraction(unittest.TestCase):
    """Test cases for borough extraction functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = InBerlinWohnenScraper("inberlinwohnen")

    def _create_resolver(self, mapping: dict) -> BoroughResolver:
        """Creates a BoroughResolver with specified mapping."""
        temp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(mapping, temp)
        temp.close()
        resolver = BoroughResolver(temp.name)
        Path(temp.name).unlink(missing_ok=True)
        return resolver

    def test_extract_borough_from_address_with_zip(self):
        """Test borough extraction from address with ZIP code."""
        resolver = self._create_resolver({"10115": ["Mitte"]})
        self.scraper.set_borough_resolver(resolver)
        details = {}

        self.scraper._extract_borough_from_address(
            "Teststraße 123, 10115 Berlin", details
        )

        self.assertEqual(details["borough"], "Mitte")

    def test_extract_borough_from_address_no_zip(self):
        """Test borough extraction when address has no ZIP code."""
        resolver = self._create_resolver({"10115": ["Mitte"]})
        self.scraper.set_borough_resolver(resolver)
        details = {}

        self.scraper._extract_borough_from_address("Teststraße 123, Berlin", details)

        self.assertNotIn("borough", details)

    def test_extract_borough_from_address_unknown_zip(self):
        """Test borough extraction with unknown ZIP code."""
        resolver = self._create_resolver({"10115": ["Mitte"]})
        self.scraper.set_borough_resolver(resolver)
        details = {}

        self.scraper._extract_borough_from_address(
            "Teststraße 123, 99999 Berlin", details
        )

        self.assertEqual(details["borough"], "N/A")


class TestInBerlinWohnenScraperHTMLParsing(unittest.TestCase):
    """Test cases for HTML parsing functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = InBerlinWohnenScraper("inberlinwohnen")

    def test_parse_html_optimized_no_container(self):
        """Test parsing HTML when container is not found."""
        html_content = "<html><body><div>No listings here</div></body></html>"

        listings, seen_known_ids = self.scraper._parse_html_optimized(
            html_content, set()
        )

        self.assertEqual(len(listings), 0)
        self.assertEqual(len(seen_known_ids), 0)

    def test_parse_html_optimized_no_listings_message(self):
        """Test parsing HTML with 'Keine Wohnungen gefunden' message."""
        html_content = """
        <html><body>
        <div wire:loading.remove>
            <div>Keine Wohnungen gefunden</div>
        </div>
        </body></html>
        """

        listings, seen_known_ids = self.scraper._parse_html_optimized(
            html_content, set()
        )

        self.assertEqual(len(listings), 0)
        self.assertEqual(len(seen_known_ids), 0)

    def test_parse_html_optimized_early_termination(self):
        """Test early termination when known listing is encountered."""
        html_content = """
        <html><body>
        <div wire:loading.remove>
            <div id="apartment-1">
                <a href="https://example.com/apartment/1">Alle Details</a>
                <dt>Adresse:</dt><dd>Street 1, 10115 Berlin</dd>
            </div>
            <div id="apartment-2">
                <a href="https://example.com/apartment/2">Alle Details</a>
                <dt>Adresse:</dt><dd>Street 2, 10115 Berlin</dd>
            </div>
        </div>
        </body></html>
        """
        known_ids = {"https://example.com/apartment/1"}

        listings, seen_known_ids = self.scraper._parse_html_optimized(
            html_content, known_ids
        )

        # First listing is known, should terminate early
        # seen_known_ids should contain the known listing
        self.assertIn("https://example.com/apartment/1", seen_known_ids)
        # No new listings should be found due to early termination
        self.assertEqual(len(listings), 0)

    def test_parse_html_optimized_new_listings_before_known(self):
        """Test parsing with new listings before a known listing."""
        html_content = """
        <html><body>
        <div wire:loading.remove>
            <div id="apartment-new">
                <a href="https://example.com/apartment/new">Alle Details</a>
                <dt>Adresse:</dt><dd>New Street 1, 10115 Berlin</dd>
            </div>
            <div id="apartment-known">
                <a href="https://example.com/apartment/known">Alle Details</a>
                <dt>Adresse:</dt><dd>Known Street, 10115 Berlin</dd>
            </div>
        </div>
        </body></html>
        """
        known_ids = {"https://example.com/apartment/known"}

        listings, seen_known_ids = self.scraper._parse_html_optimized(
            html_content, known_ids
        )

        # Should find one new listing before hitting known listing
        self.assertEqual(len(listings), 1)
        self.assertIn("https://example.com/apartment/new", listings)
        self.assertIn("https://example.com/apartment/known", seen_known_ids)


class TestInBerlinWohnenScraperListingParsing(unittest.TestCase):
    """Test cases for individual listing parsing."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = InBerlinWohnenScraper("inberlinwohnen")

    def test_parse_listing_details_complete(self):
        """Test parsing a complete listing with all fields."""
        html = """
        <div id="apartment-123">
            <a href="https://example.com/apartment/123">Alle Details</a>
            <dt>Adresse:</dt>
            <dd><button>Teststraße 42, 10115 Berlin</button></dd>
            <dt>Wohnfläche:</dt>
            <dd>85,5 m²</dd>
            <dt>Kaltmiete:</dt>
            <dd>750,00 €</dd>
            <dt>Gesamtmiete:</dt>
            <dd>950,50 €</dd>
            <dt>Zimmeranzahl:</dt>
            <dd>3,5</dd>
            <dt>WBS:</dt>
            <dd>nicht erforderlich</dd>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", id="apartment-123")

        listing = self.scraper._parse_listing_details(listing_soup)

        self.assertEqual(listing.identifier, "https://example.com/apartment/123")
        self.assertEqual(listing.address, "Teststraße 42, 10115 Berlin")
        self.assertEqual(listing.sqm, "85.5")
        self.assertEqual(listing.price_cold, "750.00")
        self.assertEqual(listing.price_total, "950.50")
        self.assertEqual(listing.rooms, "3.5")
        self.assertFalse(listing.wbs)
        self.assertEqual(listing.source, "inberlinwohnen")

    def test_parse_listing_details_wbs_required(self):
        """Test parsing listing with WBS required."""
        html = """
        <div id="apartment-456">
            <a href="https://example.com/apartment/456">Alle Details</a>
            <dt>WBS:</dt>
            <dd>WBS erforderlich</dd>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", id="apartment-456")

        listing = self.scraper._parse_listing_details(listing_soup)

        self.assertTrue(listing.wbs)

    def test_parse_listing_details_partial(self):
        """Test parsing listing with only some fields present."""
        html = """
        <div id="apartment-789">
            <a href="https://example.com/apartment/789">Alle Details</a>
            <dt>Adresse:</dt>
            <dd>Partial Street 10, 10115 Berlin</dd>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", id="apartment-789")

        listing = self.scraper._parse_listing_details(listing_soup)

        self.assertEqual(listing.identifier, "https://example.com/apartment/789")
        self.assertEqual(listing.address, "Partial Street 10, 10115 Berlin")
        self.assertEqual(listing.sqm, "N/A")
        self.assertEqual(listing.price_cold, "N/A")
        self.assertEqual(listing.price_total, "N/A")
        self.assertEqual(listing.rooms, "N/A")


class TestInBerlinWohnenScraperHTTPRequests(unittest.TestCase):
    """Test cases for HTTP request handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = InBerlinWohnenScraper("inberlinwohnen")

    @patch("src.scrapers.inberlinwohnen.requests.get")
    def test_get_current_listings_success(self, mock_get):
        """Test successful HTTP request and parsing."""
        html_content = """
        <html><body>
        <div wire:loading.remove>
            <div id="apartment-test">
                <a href="https://example.com/apartment/test">Alle Details</a>
                <dt>Adresse:</dt>
                <dd>Test Street 1, 10115 Berlin</dd>
            </div>
        </div>
        </body></html>
        """
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_get.return_value = mock_response

        listings, _ = self.scraper.get_current_listings()

        self.assertEqual(len(listings), 1)
        self.assertIn("https://example.com/apartment/test", listings)

    @patch("src.scrapers.inberlinwohnen.requests.get")
    def test_get_current_listings_with_known_listings(self, mock_get):
        """Test HTTP request with known listings for filtering."""
        html_content = """
        <html><body>
        <div wire:loading.remove>
            <div id="apartment-new">
                <a href="https://example.com/apartment/new">Alle Details</a>
                <dt>Adresse:</dt>
                <dd>New Street, 10115 Berlin</dd>
            </div>
            <div id="apartment-known">
                <a href="https://example.com/apartment/known">Alle Details</a>
                <dt>Adresse:</dt>
                <dd>Known Street, 10115 Berlin</dd>
            </div>
        </div>
        </body></html>
        """
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_get.return_value = mock_response

        known_listings = {"https://example.com/apartment/known": Mock()}

        listings, seen_known_ids = self.scraper.get_current_listings(known_listings)

        # Should return only new listing, not the known one
        self.assertEqual(len(listings), 1)
        self.assertIn("https://example.com/apartment/new", listings)
        self.assertIn("https://example.com/apartment/known", seen_known_ids)

    @patch("src.scrapers.inberlinwohnen.requests.get")
    def test_get_current_listings_request_error(self, mock_get):
        """Test HTTP request error handling."""
        import requests

        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        with self.assertRaises(requests.exceptions.RequestException):
            self.scraper.get_current_listings()

    @patch("src.scrapers.inberlinwohnen.requests.get")
    def test_get_current_listings_empty_page(self, mock_get):
        """Test handling of empty page response."""
        mock_response = Mock()
        mock_response.text = "<html><body></body></html>"
        mock_response.raise_for_status = Mock()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_get.return_value = mock_response

        listings, seen_known_ids = self.scraper.get_current_listings()

        self.assertEqual(len(listings), 0)
        self.assertEqual(len(seen_known_ids), 0)


class TestInBerlinWohnenScraperIntegration(unittest.TestCase):
    """Integration tests with realistic HTML structure from inberlinwohnen.de."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = InBerlinWohnenScraper("inberlinwohnen")

    def _create_resolver(self, mapping: dict) -> BoroughResolver:
        """Creates a BoroughResolver with specified mapping."""
        temp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(mapping, temp)
        temp.close()
        resolver = BoroughResolver(temp.name)
        Path(temp.name).unlink(missing_ok=True)
        return resolver

    def test_parse_wbm_mitte_listing_with_wbs(self):
        """
        Test parsing a real WBM listing from Mitte requiring WBS.
        
        Based on actual listing: 1-Zimmer-Wohnung in Mitte for students/trainees
        at Rosenthaler Straße 15, 10119 Berlin.
        Source: https://www.inberlinwohnen.de/wohnungsfinder
        """
        resolver = self._create_resolver({"10119": ["Mitte"]})
        self.scraper.set_borough_resolver(resolver)

        html = """
        <html><body>
        <div wire:loading.remove>
            <div id="apartment-1-zimmer-wohnung-mitte-wbs">
                <a href="https://www.wbm.de/wohnungen-berlin/angebote/details/1-zimmer-wohnung-in-mittewbs-fuer-auszubildende-oder-studenten/">
                    Alle Details
                </a>
                <dl>
                    <dt>Adresse:</dt>
                    <dd>
                        <button>Rosenthaler Straße 15, 10119, Mitte</button>
                    </dd>
                    <dt>Zimmeranzahl:</dt>
                    <dd>1,0</dd>
                    <dt>Wohnfläche:</dt>
                    <dd>31,83 m²</dd>
                    <dt>Kaltmiete:</dt>
                    <dd>296,91 €</dd>
                    <dt>Gesamtmiete:</dt>
                    <dd>378,53 €</dd>
                    <dt>WBS:</dt>
                    <dd>erforderlich</dd>
                </dl>
            </div>
        </div>
        </body></html>
        """

        listings, _ = self.scraper._parse_html_optimized(html, set())

        self.assertEqual(len(listings), 1)
        listing = list(listings.values())[0]

        self.assertEqual(
            listing.identifier,
            "https://www.wbm.de/wohnungen-berlin/angebote/details/"
            "1-zimmer-wohnung-in-mittewbs-fuer-auszubildende-oder-studenten/",
        )
        self.assertEqual(listing.address, "Rosenthaler Straße 15, 10119, Mitte")
        self.assertEqual(listing.borough, "Mitte")
        self.assertEqual(listing.sqm, "31.83")
        self.assertEqual(listing.rooms, "1.0")
        self.assertEqual(listing.price_cold, "296.91")
        self.assertEqual(listing.price_total, "378.53")
        self.assertTrue(listing.wbs)
        self.assertEqual(listing.source, "inberlinwohnen")

    def test_parse_mitte_listing_without_wbs(self):
        """
        Test parsing a listing from Mitte without WBS requirement.
        
        Based on actual listing: 2-Zimmer-Wohnung in Mitte ohne Aufzug
        at Joachimstraße 13B, 10119 Berlin.
        Source: https://www.inberlinwohnen.de/wohnungsfinder
        """
        resolver = self._create_resolver({"10119": ["Mitte"]})
        self.scraper.set_borough_resolver(resolver)

        html = """
        <html><body>
        <div wire:loading.remove>
            <div id="apartment-2-zimmer-wohnung-mitte">
                <a href="https://www.wbm.de/wohnungen-berlin/angebote/details/2-zimmer-wohnung-in-mitte-ohne-aufzug/">
                    Alle Details
                </a>
                <dl>
                    <dt>Adresse:</dt>
                    <dd>
                        <button>Joachimstraße 13B, 10119, Mitte</button>
                    </dd>
                    <dt>Zimmeranzahl:</dt>
                    <dd>2,0</dd>
                    <dt>Wohnfläche:</dt>
                    <dd>49,82 m²</dd>
                    <dt>Kaltmiete:</dt>
                    <dd>468,01 €</dd>
                    <dt>Gesamtmiete:</dt>
                    <dd>688,01 €</dd>
                    <dt>WBS:</dt>
                    <dd>nicht erforderlich</dd>
                </dl>
            </div>
        </div>
        </body></html>
        """

        listings, _ = self.scraper._parse_html_optimized(html, set())

        self.assertEqual(len(listings), 1)
        listing = list(listings.values())[0]

        self.assertEqual(listing.address, "Joachimstraße 13B, 10119, Mitte")
        self.assertEqual(listing.borough, "Mitte")
        self.assertEqual(listing.sqm, "49.82")
        self.assertEqual(listing.rooms, "2.0")
        self.assertEqual(listing.price_cold, "468.01")
        self.assertEqual(listing.price_total, "688.01")
        self.assertFalse(listing.wbs)

    def test_parse_half_room_listing(self):
        """
        Test parsing a listing with half rooms (1,5 Zimmer).
        
        Based on actual listing: 1,5 Zimmer nahe Thälmannpark
        at Chodowieckistraße 7, 10405 Pankow.
        Source: https://www.inberlinwohnen.de/wohnungsfinder
        """
        resolver = self._create_resolver({"10405": ["Prenzlauer Berg"]})
        self.scraper.set_borough_resolver(resolver)

        html = """
        <html><body>
        <div wire:loading.remove>
            <div id="apartment-1-5-zimmer-pankow">
                <a href="https://www.gesobau.de/wohnung/1-5-zimmer-nahe-thaelmannpark/">
                    Alle Details
                </a>
                <dl>
                    <dt>Adresse:</dt>
                    <dd>
                        <button>Chodowieckistraße 7, 10405, Pankow</button>
                    </dd>
                    <dt>Zimmeranzahl:</dt>
                    <dd>1,5</dd>
                    <dt>Wohnfläche:</dt>
                    <dd>37,00 m²</dd>
                    <dt>Kaltmiete:</dt>
                    <dd>739,63 €</dd>
                    <dt>Gesamtmiete:</dt>
                    <dd>849,63 €</dd>
                    <dt>WBS:</dt>
                    <dd>nicht erforderlich</dd>
                </dl>
            </div>
        </div>
        </body></html>
        """

        listings, _ = self.scraper._parse_html_optimized(html, set())

        self.assertEqual(len(listings), 1)
        listing = list(listings.values())[0]

        self.assertEqual(listing.rooms, "1.5")
        self.assertEqual(listing.sqm, "37.00")
        self.assertEqual(listing.price_cold, "739.63")
        self.assertEqual(listing.price_total, "849.63")

    def test_parse_lichtenberg_listing_with_wbs(self):
        """
        Test parsing a listing from Lichtenberg with WBS requirement.
        
        Based on actual listing: WBS 100/140 erforderlich
        at Erieseering 32, 10319 Lichtenberg.
        Source: https://www.inberlinwohnen.de/wohnungsfinder
        """
        resolver = self._create_resolver({"10319": ["Lichtenberg"]})
        self.scraper.set_borough_resolver(resolver)

        html = """
        <html><body>
        <div wire:loading.remove>
            <div id="apartment-wbs-lichtenberg">
                <a href="https://www.howoge.de/wohnung/wbs-100-140-erforderlich/">
                    Alle Details
                </a>
                <dl>
                    <dt>Adresse:</dt>
                    <dd>
                        <button>Erieseering 32, 10319, Lichtenberg</button>
                    </dd>
                    <dt>Zimmeranzahl:</dt>
                    <dd>1,0</dd>
                    <dt>Wohnfläche:</dt>
                    <dd>29,98 m²</dd>
                    <dt>Kaltmiete:</dt>
                    <dd>254,60 €</dd>
                    <dt>Gesamtmiete:</dt>
                    <dd>312,19 €</dd>
                    <dt>WBS:</dt>
                    <dd>erforderlich</dd>
                </dl>
            </div>
        </div>
        </body></html>
        """

        listings, _ = self.scraper._parse_html_optimized(html, set())

        self.assertEqual(len(listings), 1)
        listing = list(listings.values())[0]

        self.assertEqual(listing.address, "Erieseering 32, 10319, Lichtenberg")
        self.assertEqual(listing.borough, "Lichtenberg")
        self.assertEqual(listing.sqm, "29.98")
        self.assertEqual(listing.rooms, "1.0")
        self.assertEqual(listing.price_cold, "254.60")
        self.assertEqual(listing.price_total, "312.19")
        self.assertTrue(listing.wbs)

    def test_parse_multiple_real_listings(self):
        """
        Test parsing multiple realistic listings from different boroughs.
        
        Simulates a page with listings from Mitte, Lichtenberg, and Pankow.
        Source: https://www.inberlinwohnen.de/wohnungsfinder
        """
        resolver = self._create_resolver({
            "10119": ["Mitte"],
            "10319": ["Lichtenberg"],
            "13051": ["Neu-Hohenschönhausen"],
        })
        self.scraper.set_borough_resolver(resolver)

        html = """
        <html><body>
        <div wire:loading.remove>
            <div id="apartment-mitte-1">
                <a href="https://www.wbm.de/wohnung/mitte-1/">Alle Details</a>
                <dt>Adresse:</dt>
                <dd><button>Rosenthaler Straße 15, 10119, Mitte</button></dd>
                <dt>Zimmeranzahl:</dt><dd>1,0</dd>
                <dt>Wohnfläche:</dt><dd>31,83 m²</dd>
                <dt>Kaltmiete:</dt><dd>296,91 €</dd>
                <dt>Gesamtmiete:</dt><dd>378,53 €</dd>
                <dt>WBS:</dt><dd>erforderlich</dd>
            </div>
            <div id="apartment-lichtenberg-2">
                <a href="https://www.howoge.de/wohnung/lichtenberg-2/">Alle Details</a>
                <dt>Adresse:</dt>
                <dd><button>Sewanstraße 263, 10319, Lichtenberg</button></dd>
                <dt>Zimmeranzahl:</dt><dd>2,0</dd>
                <dt>Wohnfläche:</dt><dd>49,87 m²</dd>
                <dt>Kaltmiete:</dt><dd>365,34 €</dd>
                <dt>Gesamtmiete:</dt><dd>466,59 €</dd>
                <dt>WBS:</dt><dd>erforderlich</dd>
            </div>
            <div id="apartment-hohenschoenhausen-3">
                <a href="https://www.howoge.de/wohnung/hohenschoenhausen-3/">Alle Details</a>
                <dt>Adresse:</dt>
                <dd><button>Barther Straße 7, 13051, Lichtenberg</button></dd>
                <dt>Zimmeranzahl:</dt><dd>3,0</dd>
                <dt>Wohnfläche:</dt><dd>70,79 m²</dd>
                <dt>Kaltmiete:</dt><dd>454,75 €</dd>
                <dt>Gesamtmiete:</dt><dd>595,91 €</dd>
                <dt>WBS:</dt><dd>nicht erforderlich</dd>
            </div>
        </div>
        </body></html>
        """

        listings, _ = self.scraper._parse_html_optimized(html, set())

        self.assertEqual(len(listings), 3)

        # Verify first listing (Mitte with WBS)
        mitte_listing = listings["https://www.wbm.de/wohnung/mitte-1/"]
        self.assertEqual(mitte_listing.borough, "Mitte")
        self.assertEqual(mitte_listing.rooms, "1.0")
        self.assertTrue(mitte_listing.wbs)

        # Verify second listing (Lichtenberg with WBS)
        lichtenberg_listing = listings["https://www.howoge.de/wohnung/lichtenberg-2/"]
        self.assertEqual(lichtenberg_listing.borough, "Lichtenberg")
        self.assertEqual(lichtenberg_listing.rooms, "2.0")
        self.assertTrue(lichtenberg_listing.wbs)

        # Verify third listing (Neu-Hohenschönhausen without WBS)
        hohen_listing = listings["https://www.howoge.de/wohnung/hohenschoenhausen-3/"]
        self.assertEqual(hohen_listing.borough, "Neu-Hohenschönhausen")
        self.assertEqual(hohen_listing.rooms, "3.0")
        self.assertFalse(hohen_listing.wbs)

    def test_parse_neubau_listing(self):
        """
        Test parsing a new construction (Neubau) listing.
        
        Based on actual listing: Neubau - 1 Zimmerwohnung mit WBS bis 140
        at Wiecker Straße 12, 13051 Lichtenberg (Baujahr 2025).
        Source: https://www.inberlinwohnen.de/wohnungsfinder
        """
        resolver = self._create_resolver({"13051": ["Neu-Hohenschönhausen"]})
        self.scraper.set_borough_resolver(resolver)

        html = """
        <html><body>
        <div wire:loading.remove>
            <div id="apartment-neubau-wiecker">
                <a href="https://www.howoge.de/wohnung/neubau-1-zimmerwohnung-wbs-140/">
                    Alle Details
                </a>
                <dl>
                    <dt>Adresse:</dt>
                    <dd>
                        <button>Wiecker Straße 12, 13051, Lichtenberg</button>
                    </dd>
                    <dt>Zimmeranzahl:</dt>
                    <dd>1,0</dd>
                    <dt>Wohnfläche:</dt>
                    <dd>29,00 m²</dd>
                    <dt>Kaltmiete:</dt>
                    <dd>203,00 €</dd>
                    <dt>Gesamtmiete:</dt>
                    <dd>261,00 €</dd>
                    <dt>WBS:</dt>
                    <dd>erforderlich</dd>
                </dl>
            </div>
        </div>
        </body></html>
        """

        listings, _ = self.scraper._parse_html_optimized(html, set())

        self.assertEqual(len(listings), 1)
        listing = list(listings.values())[0]

        self.assertEqual(listing.address, "Wiecker Straße 12, 13051, Lichtenberg")
        self.assertEqual(listing.borough, "Neu-Hohenschönhausen")
        self.assertEqual(listing.sqm, "29.00")
        self.assertEqual(listing.rooms, "1.0")
        self.assertEqual(listing.price_cold, "203.00")
        self.assertEqual(listing.price_total, "261.00")
        self.assertTrue(listing.wbs)


if __name__ == "__main__":
    unittest.main()
