"""
Unit tests for the ImmoweltScraper class.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from bs4 import BeautifulSoup

from src.scrapers.immowelt import ImmoweltScraper
from src.services.borough_resolver import BoroughResolver


class TestImmoweltScraperInitialization(unittest.TestCase):
    """Test cases for ImmoweltScraper initialization."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scraper = ImmoweltScraper("immowelt")

    def test_initialization(self):
        """Test that the scraper initializes with correct properties."""
        self.assertEqual(self.scraper.name, "immowelt")
        self.assertIn("immowelt.de/classified-search", self.scraper.url)
        self.assertIn("distributionTypes=Rent", self.scraper.url)
        self.assertIn("estateTypes=Apartment", self.scraper.url)
        self.assertIn("order=DateDesc", self.scraper.url)

    def test_initialization_custom_name(self):
        """Test initialization with custom name."""
        scraper = ImmoweltScraper("custom_immowelt")
        self.assertEqual(scraper.name, "custom_immowelt")

    def test_initialization_headers(self):
        """Test that custom headers are set."""
        self.assertIn("Accept", self.scraper.headers)
        self.assertIn("Accept-Language", self.scraper.headers)
        self.assertIn("Referer", self.scraper.headers)
        self.assertIn("DNT", self.scraper.headers)


class TestImmoweltScraperTextCleaning(unittest.TestCase):
    """Test cases for text cleaning methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ImmoweltScraper("immowelt")

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

    def test_clean_text_with_zimmer(self):
        """Test text cleaning removes Zimmer text."""
        self.assertEqual(self.scraper._clean_text("3 Zimmer"), "3")
        self.assertEqual(self.scraper._clean_text("2,5 Zi."), "2,5")

    def test_clean_text_trailing_punctuation(self):
        """Test text cleaning removes trailing punctuation."""
        self.assertEqual(self.scraper._clean_text("Hello World."), "Hello World")
        self.assertEqual(self.scraper._clean_text("Hello World,"), "Hello World")


class TestImmoweltScraperGermanNumberNormalization(unittest.TestCase):
    """Test cases for German number normalization."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ImmoweltScraper("immowelt")

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


class TestImmoweltScraperRoomNormalization(unittest.TestCase):
    """Test cases for room format normalization."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ImmoweltScraper("immowelt")

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


class TestImmoweltScraperIdentifierExtraction(unittest.TestCase):
    """Test cases for fast identifier extraction."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ImmoweltScraper("immowelt")

    def test_extract_identifier_fast_valid(self):
        """Test fast identifier extraction with valid href."""
        html = '''
        <div data-testid="classified-card-mfe-123">
            <a data-testid="card-mfe-covering-link-testid" 
               href="/expose/abc123">Listing</a>
        </div>
        '''
        soup = BeautifulSoup(html, "html.parser").find("div")

        identifier = self.scraper._extract_identifier_fast(soup)
        self.assertEqual(identifier, "https://www.immowelt.de/expose/abc123")

    def test_extract_identifier_fast_absolute_url(self):
        """Test fast identifier extraction with absolute URL."""
        html = '''
        <div data-testid="classified-card-mfe-123">
            <a data-testid="card-mfe-covering-link-testid" 
               href="https://www.immowelt.de/expose/abc123">Listing</a>
        </div>
        '''
        soup = BeautifulSoup(html, "html.parser").find("div")

        identifier = self.scraper._extract_identifier_fast(soup)
        self.assertEqual(identifier, "https://www.immowelt.de/expose/abc123")

    def test_extract_identifier_fast_no_link(self):
        """Test fast identifier extraction without link element."""
        html = '<div data-testid="classified-card-mfe-123">No link</div>'
        soup = BeautifulSoup(html, "html.parser").find("div")

        identifier = self.scraper._extract_identifier_fast(soup)
        self.assertIsNone(identifier)

    def test_extract_identifier_fast_no_href(self):
        """Test fast identifier extraction without href."""
        html = '''
        <div data-testid="classified-card-mfe-123">
            <a data-testid="card-mfe-covering-link-testid">No href</a>
        </div>
        '''
        soup = BeautifulSoup(html, "html.parser").find("div")

        identifier = self.scraper._extract_identifier_fast(soup)
        self.assertIsNone(identifier)


class TestImmoweltScraperUrlExtraction(unittest.TestCase):
    """Test cases for URL extraction."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ImmoweltScraper("immowelt")

    def test_extract_listing_url_valid(self):
        """Test URL extraction with valid href."""
        html = '''
        <div data-testid="classified-card-mfe-123">
            <a data-testid="card-mfe-covering-link-testid" 
               href="/expose/xyz789">Listing</a>
        </div>
        '''
        soup = BeautifulSoup(html, "html.parser").find("div")

        url = self.scraper._extract_listing_url(soup)
        self.assertEqual(url, "https://www.immowelt.de/expose/xyz789")

    def test_extract_listing_url_none(self):
        """Test URL extraction without link returns None."""
        html = '<div data-testid="classified-card-mfe-123">No link</div>'
        soup = BeautifulSoup(html, "html.parser").find("div")

        url = self.scraper._extract_listing_url(soup)
        self.assertIsNone(url)


class TestImmoweltScraperPriceExtraction(unittest.TestCase):
    """Test cases for price extraction."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ImmoweltScraper("immowelt")

    def test_extract_price_valid(self):
        """Test price extraction with valid price."""
        html = '''
        <div data-testid="classified-card-mfe-123">
            <div data-testid="cardmfe-price-testid">1.200 € mtl.</div>
        </div>
        '''
        soup = BeautifulSoup(html, "html.parser").find("div")

        price = self.scraper._extract_price(soup)
        self.assertEqual(price, "1200")

    def test_extract_price_thousands(self):
        """Test price extraction with thousands separator."""
        html = '''
        <div data-testid="classified-card-mfe-123">
            <div data-testid="cardmfe-price-testid">2.345 € mtl.</div>
        </div>
        '''
        soup = BeautifulSoup(html, "html.parser").find("div")

        price = self.scraper._extract_price(soup)
        self.assertEqual(price, "2345")

    def test_extract_price_no_element(self):
        """Test price extraction without price element."""
        html = '<div data-testid="classified-card-mfe-123">No price</div>'
        soup = BeautifulSoup(html, "html.parser").find("div")

        price = self.scraper._extract_price(soup)
        self.assertEqual(price, "N/A")


class TestImmoweltScraperAddressExtraction(unittest.TestCase):
    """Test cases for address and borough extraction."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ImmoweltScraper("immowelt")

    def test_extract_address_and_borough_valid(self):
        """Test address extraction with valid data."""
        html = '''
        <div data-testid="classified-card-mfe-123">
            <div data-testid="cardmfe-description-box-address">
                Musterstraße 42, 10245 Berlin
            </div>
        </div>
        '''
        soup = BeautifulSoup(html, "html.parser").find("div")

        # Set up borough resolver
        temp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({"10245": ["Friedrichshain"]}, temp)
        temp.close()

        try:
            resolver = BoroughResolver(temp.name)
            self.scraper.set_borough_resolver(resolver)

            address, borough = self.scraper._extract_address_and_borough(soup)

            self.assertEqual(address, "Musterstraße 42, 10245 Berlin")
            self.assertEqual(borough, "Friedrichshain")
        finally:
            Path(temp.name).unlink(missing_ok=True)

    def test_extract_address_no_element(self):
        """Test address extraction without address element."""
        html = '<div data-testid="classified-card-mfe-123">No address</div>'
        soup = BeautifulSoup(html, "html.parser").find("div")

        address, borough = self.scraper._extract_address_and_borough(soup)

        self.assertEqual(address, "N/A")
        self.assertEqual(borough, "N/A")

    def test_extract_borough_from_address_valid_zip(self):
        """Test borough extraction with valid zip code."""
        temp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({"10961": ["Kreuzberg"]}, temp)
        temp.close()

        try:
            resolver = BoroughResolver(temp.name)
            self.scraper.set_borough_resolver(resolver)

            borough = self.scraper._extract_borough_from_address(
                "Bergmannstraße 10, 10961 Berlin"
            )
            self.assertEqual(borough, "Kreuzberg")
        finally:
            Path(temp.name).unlink(missing_ok=True)

    def test_extract_borough_from_address_no_zip(self):
        """Test borough extraction without zip code."""
        borough = self.scraper._extract_borough_from_address("Berlin, Germany")
        self.assertEqual(borough, "N/A")

    def test_extract_borough_from_address_unknown_zip(self):
        """Test borough extraction with unknown zip code."""
        temp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({"10245": ["Friedrichshain"]}, temp)
        temp.close()

        try:
            resolver = BoroughResolver(temp.name)
            self.scraper.set_borough_resolver(resolver)

            borough = self.scraper._extract_borough_from_address(
                "Unknown Street, 99999 Berlin"
            )
            self.assertEqual(borough, "N/A")
        finally:
            Path(temp.name).unlink(missing_ok=True)


class TestImmoweltScraperKeyFactsExtraction(unittest.TestCase):
    """Test cases for key facts extraction."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ImmoweltScraper("immowelt")

    def test_extract_key_facts_complete(self):
        """Test key facts extraction with complete data."""
        html = '''
        <div data-testid="classified-card-mfe-123">
            <div data-testid="cardmfe-keyfacts-testid">
                <div class="css-9u48bm">3 Zimmer</div>
                <div class="css-9u48bm">·</div>
                <div class="css-9u48bm">75,5 m²</div>
            </div>
        </div>
        '''
        soup = BeautifulSoup(html, "html.parser").find("div")

        rooms, sqm = self.scraper._extract_key_facts(soup)

        self.assertEqual(rooms, "3")
        self.assertEqual(sqm, "75.5")

    def test_extract_key_facts_half_rooms(self):
        """Test key facts extraction with half rooms."""
        html = '''
        <div data-testid="classified-card-mfe-123">
            <div data-testid="cardmfe-keyfacts-testid">
                <div class="css-9u48bm">2,5 Zimmer</div>
                <div class="css-9u48bm">·</div>
                <div class="css-9u48bm">60 m²</div>
            </div>
        </div>
        '''
        soup = BeautifulSoup(html, "html.parser").find("div")

        rooms, sqm = self.scraper._extract_key_facts(soup)

        self.assertEqual(rooms, "2.5")
        self.assertEqual(sqm, "60")

    def test_extract_key_facts_no_container(self):
        """Test key facts extraction without container."""
        html = '<div data-testid="classified-card-mfe-123">No key facts</div>'
        soup = BeautifulSoup(html, "html.parser").find("div")

        rooms, sqm = self.scraper._extract_key_facts(soup)

        self.assertEqual(rooms, "1")  # Default value
        self.assertEqual(sqm, "N/A")  # Default value

    def test_extract_rooms_from_facts(self):
        """Test room extraction from facts list."""
        facts = ["3 Zimmer", "75 m²"]
        rooms = self.scraper._extract_rooms_from_facts(facts)
        self.assertEqual(rooms, "3")

    def test_extract_rooms_from_facts_no_zimmer(self):
        """Test room extraction without Zimmer fact."""
        facts = ["75 m²", "Balkon"]
        rooms = self.scraper._extract_rooms_from_facts(facts)
        self.assertEqual(rooms, "1")  # Default

    def test_extract_sqm_from_facts(self):
        """Test sqm extraction from facts list."""
        facts = ["3 Zimmer", "75,5 m²"]
        sqm = self.scraper._extract_sqm_from_facts(facts)
        self.assertEqual(sqm, "75.5")

    def test_extract_sqm_from_facts_no_sqm(self):
        """Test sqm extraction without m² fact."""
        facts = ["3 Zimmer", "Balkon"]
        sqm = self.scraper._extract_sqm_from_facts(facts)
        self.assertEqual(sqm, "N/A")


class TestImmoweltScraperBoroughResolution(unittest.TestCase):
    """Test cases for borough resolution."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ImmoweltScraper("immowelt")

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


class TestImmoweltScraperListingParsing(unittest.TestCase):
    """Test cases for listing parsing."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ImmoweltScraper("immowelt")

    def test_parse_listing_complete(self):
        """Test parsing listing with all fields."""
        html = '''
        <div data-testid="classified-card-mfe-123">
            <a data-testid="card-mfe-covering-link-testid" 
               href="/expose/abc123">Link</a>
            <div data-testid="cardmfe-price-testid">1.200 € mtl.</div>
            <div data-testid="cardmfe-description-box-address">
                Musterstraße 42, 10245 Berlin
            </div>
            <div data-testid="cardmfe-keyfacts-testid">
                <div class="css-9u48bm">2,5 Zimmer</div>
                <div class="css-9u48bm">·</div>
                <div class="css-9u48bm">65,5 m²</div>
            </div>
        </div>
        '''
        soup = BeautifulSoup(html, "html.parser").find("div")

        temp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({"10245": ["Friedrichshain"]}, temp)
        temp.close()

        try:
            resolver = BoroughResolver(temp.name)
            self.scraper.set_borough_resolver(resolver)

            listing = self.scraper._parse_listing(soup)

            self.assertIsNotNone(listing)
            self.assertEqual(
                listing.identifier, "https://www.immowelt.de/expose/abc123"
            )
            self.assertEqual(listing.source, "immowelt")
            self.assertEqual(listing.price_cold, "1200")
            self.assertEqual(listing.rooms, "2.5")
            self.assertEqual(listing.sqm, "65.5")
            self.assertEqual(listing.borough, "Friedrichshain")
            self.assertIn("Musterstraße 42", listing.address)
            self.assertFalse(listing.wbs)
        finally:
            Path(temp.name).unlink(missing_ok=True)

    def test_parse_listing_no_url(self):
        """Test parsing listing without URL returns None."""
        html = '''
        <div data-testid="classified-card-mfe-123">
            <div data-testid="cardmfe-price-testid">1.200 €</div>
        </div>
        '''
        soup = BeautifulSoup(html, "html.parser").find("div")

        listing = self.scraper._parse_listing(soup)
        self.assertIsNone(listing)

    def test_parse_listing_minimal(self):
        """Test parsing listing with minimal data."""
        html = '''
        <div data-testid="classified-card-mfe-123">
            <a data-testid="card-mfe-covering-link-testid" 
               href="/expose/min123">Link</a>
        </div>
        '''
        soup = BeautifulSoup(html, "html.parser").find("div")

        listing = self.scraper._parse_listing(soup)

        self.assertIsNotNone(listing)
        self.assertEqual(
            listing.identifier, "https://www.immowelt.de/expose/min123"
        )
        self.assertEqual(listing.price_cold, "N/A")
        self.assertEqual(listing.rooms, "1")
        self.assertEqual(listing.sqm, "N/A")


class TestImmoweltScraperDetailScraping(unittest.TestCase):
    """Test cases for detail page scraping."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ImmoweltScraper("immowelt")

    def test_scrape_listing_details_warmmiete(self):
        """Test scraping warm rent from detail page."""
        from src.core.listing import Listing

        listing = Listing(
            source="immowelt",
            identifier="https://www.immowelt.de/expose/abc123",
            price_cold="1000"
        )

        detail_html = '''
        <div class="css-8c1m7t">Warmmiete</div>
        <div class="css-1grdggd">
            <span>1.200\xa0€</span>
        </div>
        '''

        mock_session = Mock()
        mock_response = Mock()
        mock_response.text = detail_html
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        self.scraper._scrape_listing_details(listing, mock_session)

        self.assertEqual(listing.price_total, "1200")

    def test_scrape_listing_details_no_warmmiete(self):
        """Test scraping detail page without warm rent."""
        from src.core.listing import Listing

        listing = Listing(
            source="immowelt",
            identifier="https://www.immowelt.de/expose/abc123",
            price_cold="1000"
        )

        detail_html = '<div>No warm rent info</div>'

        mock_session = Mock()
        mock_response = Mock()
        mock_response.text = detail_html
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        self.scraper._scrape_listing_details(listing, mock_session)

        self.assertEqual(listing.price_total, "N/A")

    def test_scrape_listing_details_invalid_identifier(self):
        """Test scraping with invalid identifier does nothing."""
        from src.core.listing import Listing

        listing = Listing(
            source="immowelt",
            identifier="not-a-url",
            price_cold="1000"
        )

        mock_session = Mock()
        self.scraper._scrape_listing_details(listing, mock_session)

        # Session should not be called
        mock_session.get.assert_not_called()

    def test_scrape_listing_details_request_error(self):
        """Test scraping with request error handles gracefully."""
        import requests
        from src.core.listing import Listing

        listing = Listing(
            source="immowelt",
            identifier="https://www.immowelt.de/expose/abc123",
            price_cold="1000"
        )

        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.RequestException("Timeout")

        # Should not raise exception
        self.scraper._scrape_listing_details(listing, mock_session)

        # price_total should remain unchanged
        self.assertEqual(listing.price_total, "N/A")


class TestImmoweltScraperHTTPRequests(unittest.TestCase):
    """Test cases for HTTP request handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ImmoweltScraper("immowelt")

    @patch("src.scrapers.immowelt.requests.Session")
    def test_get_current_listings_empty_page(self, mock_session_class):
        """Test get_current_listings with no listings found."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_response = Mock()
        mock_response.text = "<html><body>No listings</body></html>"
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response

        listings, seen_known_ids = self.scraper.get_current_listings()

        self.assertEqual(len(listings), 0)
        self.assertEqual(len(seen_known_ids), 0)

    @patch("src.scrapers.immowelt.requests.Session")
    def test_get_current_listings_request_error(self, mock_session_class):
        """Test get_current_listings with request error."""
        import requests

        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.get.side_effect = requests.exceptions.RequestException(
            "Connection error"
        )

        with self.assertRaises(requests.exceptions.RequestException):
            self.scraper.get_current_listings()


class TestImmoweltScraperEarlyTermination(unittest.TestCase):
    """Test cases for early termination optimization."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ImmoweltScraper("immowelt")

    @patch("src.scrapers.immowelt.requests.Session")
    @patch("src.scrapers.immowelt.time.sleep")
    def test_early_termination_on_known_listing(
        self, mock_sleep, mock_session_class
    ):
        """Test that processing stops when known listing is encountered."""
        html_content = '''
        <html><body>
        <div data-testid="classified-card-mfe-11111">
            <a data-testid="card-mfe-covering-link-testid" 
               href="/expose/11111">New Listing</a>
            <div data-testid="cardmfe-price-testid">900 €</div>
            <div data-testid="cardmfe-description-box-address">
                10245 Berlin
            </div>
            <div data-testid="cardmfe-keyfacts-testid">
                <div class="css-9u48bm">2 Zimmer</div>
                <div class="css-9u48bm">65 m²</div>
            </div>
        </div>
        <div data-testid="classified-card-mfe-22222">
            <a data-testid="card-mfe-covering-link-testid" 
               href="/expose/22222">Known Listing</a>
        </div>
        <div data-testid="classified-card-mfe-33333">
            <a data-testid="card-mfe-covering-link-testid" 
               href="/expose/33333">Should not process</a>
        </div>
        </body></html>
        '''
        detail_html = '<div>Detail page</div>'

        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        def get_side_effect(url, **kwargs):
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            if "expose/11111" in url:
                mock_response.text = detail_html
            else:
                mock_response.text = html_content
            return mock_response

        mock_session.get.side_effect = get_side_effect

        known_listings = {
            "https://www.immowelt.de/expose/22222": Mock()
        }

        listings, seen_known_ids = self.scraper.get_current_listings(known_listings)

        # Should only have the first new listing
        self.assertEqual(len(listings), 1)
        self.assertIn("https://www.immowelt.de/expose/11111", listings)
        # Should not have the third listing (after early termination)
        self.assertNotIn("https://www.immowelt.de/expose/33333", listings)
        # Known listing should be in seen_known_ids
        self.assertIn("https://www.immowelt.de/expose/22222", seen_known_ids)

    @patch("src.scrapers.immowelt.requests.Session")
    @patch("src.scrapers.immowelt.time.sleep")
    def test_no_early_termination_without_known_listings(
        self, mock_sleep, mock_session_class
    ):
        """Test that all listings are processed when no known listings."""
        html_content = '''
        <html><body>
        <div data-testid="classified-card-mfe-11111">
            <a data-testid="card-mfe-covering-link-testid" 
               href="/expose/11111">Listing 1</a>
            <div data-testid="cardmfe-price-testid">900 €</div>
            <div data-testid="cardmfe-description-box-address">
                10245 Berlin
            </div>
            <div data-testid="cardmfe-keyfacts-testid">
                <div class="css-9u48bm">2 Zimmer</div>
                <div class="css-9u48bm">65 m²</div>
            </div>
        </div>
        <div data-testid="classified-card-mfe-22222">
            <a data-testid="card-mfe-covering-link-testid" 
               href="/expose/22222">Listing 2</a>
            <div data-testid="cardmfe-price-testid">1000 €</div>
            <div data-testid="cardmfe-description-box-address">
                10247 Berlin
            </div>
            <div data-testid="cardmfe-keyfacts-testid">
                <div class="css-9u48bm">3 Zimmer</div>
                <div class="css-9u48bm">80 m²</div>
            </div>
        </div>
        </body></html>
        '''
        detail_html = '<div>Detail page</div>'

        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        def get_side_effect(url, **kwargs):
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            if "expose" in url:
                mock_response.text = detail_html
            else:
                mock_response.text = html_content
            return mock_response

        mock_session.get.side_effect = get_side_effect

        listings, seen_known_ids = self.scraper.get_current_listings()

        self.assertEqual(len(listings), 2)
        self.assertEqual(len(seen_known_ids), 0)


class TestImmoweltScraperIntegration(unittest.TestCase):
    """Integration tests with realistic HTML structure."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ImmoweltScraper("immowelt")

    @patch("src.scrapers.immowelt.requests.Session")
    @patch("src.scrapers.immowelt.time.sleep")
    def test_full_scraping_flow(self, mock_sleep, mock_session_class):
        """Test complete scraping flow with realistic HTML."""
        listing_html = '''
        <html><body>
        <div data-testid="classified-card-mfe-98765">
            <a data-testid="card-mfe-covering-link-testid" 
               href="/expose/98765">Link</a>
            <div data-testid="cardmfe-price-testid">950 € mtl.</div>
            <div data-testid="cardmfe-description-box-address">
                Teststraße 42, 10961 Berlin
            </div>
            <div data-testid="cardmfe-keyfacts-testid">
                <div class="css-9u48bm">3 Zimmer</div>
                <div class="css-9u48bm">·</div>
                <div class="css-9u48bm">75 m²</div>
            </div>
        </div>
        </body></html>
        '''
        detail_html = '''
        <div class="css-8c1m7t">Warmmiete</div>
        <div class="css-1grdggd">
            <span>1.150\xa0€</span>
        </div>
        '''

        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        def get_side_effect(url, **kwargs):
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            if "expose/98765" in url:
                mock_response.text = detail_html
            else:
                mock_response.text = listing_html
            return mock_response

        mock_session.get.side_effect = get_side_effect

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
                "https://www.immowelt.de/expose/98765"
            )
            self.assertEqual(listing.source, "immowelt")
            self.assertEqual(listing.price_cold, "950")
            self.assertEqual(listing.price_total, "1150")
            self.assertEqual(listing.rooms, "3")
            self.assertEqual(listing.sqm, "75")
            self.assertEqual(listing.borough, "Kreuzberg")
            self.assertIn("Teststraße 42", listing.address)
            self.assertFalse(listing.wbs)
        finally:
            Path(temp.name).unlink(missing_ok=True)

    @patch("src.scrapers.immowelt.requests.Session")
    @patch("src.scrapers.immowelt.time.sleep")
    def test_scraping_with_known_listings(self, mock_sleep, mock_session_class):
        """Test scraping correctly handles known listings."""
        html_content = '''
        <html><body>
        <div data-testid="classified-card-mfe-11111">
            <a data-testid="card-mfe-covering-link-testid" 
               href="/expose/11111">New Listing</a>
            <div data-testid="cardmfe-price-testid">800 €</div>
            <div data-testid="cardmfe-description-box-address">
                10115 Berlin
            </div>
            <div data-testid="cardmfe-keyfacts-testid">
                <div class="css-9u48bm">2 Zimmer</div>
                <div class="css-9u48bm">50 m²</div>
            </div>
        </div>
        <div data-testid="classified-card-mfe-22222">
            <a data-testid="card-mfe-covering-link-testid" 
               href="/expose/22222">Known Listing</a>
        </div>
        </body></html>
        '''

        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        def get_side_effect(url, **kwargs):
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_response.text = html_content
            return mock_response

        mock_session.get.side_effect = get_side_effect

        known_listings = {
            "https://www.immowelt.de/expose/22222": Mock()
        }

        listings, seen_known_ids = self.scraper.get_current_listings(known_listings)

        # Should only have the new listing
        self.assertEqual(len(listings), 1)
        self.assertIn("https://www.immowelt.de/expose/11111", listings)
        # Known listing should be in seen_known_ids
        self.assertIn("https://www.immowelt.de/expose/22222", seen_known_ids)


class TestImmoweltScraperKeyFactsParsing(unittest.TestCase):
    """Test cases for key facts container parsing."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ImmoweltScraper("immowelt")

    def test_parse_key_facts_container(self):
        """Test parsing key facts container."""
        html = '''
        <div data-testid="cardmfe-keyfacts-testid">
            <div class="css-9u48bm">3 Zimmer</div>
            <div class="css-9u48bm">·</div>
            <div class="css-9u48bm">75 m²</div>
            <div class="css-9u48bm">·</div>
            <div class="css-9u48bm">EG</div>
        </div>
        '''
        container = BeautifulSoup(html, "html.parser").find("div")

        facts = self.scraper._parse_key_facts_container(container)

        # Should exclude separator dots
        self.assertIn("3 Zimmer", facts)
        self.assertIn("75 m²", facts)
        self.assertIn("EG", facts)
        self.assertNotIn("·", facts)

    def test_parse_key_facts_container_empty(self):
        """Test parsing empty key facts container."""
        html = '<div data-testid="cardmfe-keyfacts-testid"></div>'
        container = BeautifulSoup(html, "html.parser").find("div")

        facts = self.scraper._parse_key_facts_container(container)

        self.assertEqual(facts, [])


if __name__ == "__main__":
    unittest.main()
