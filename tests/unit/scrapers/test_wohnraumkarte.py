"""
Unit tests for the WohnraumkarteScraper base class.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.scrapers.wohnraumkarte import WohnraumkarteScraper
from src.services.borough_resolver import BoroughResolver


class ConcreteWohnraumkarteScraper(WohnraumkarteScraper):
    """Concrete implementation for testing the abstract base class."""

    def __init__(self, name: str = "test_scraper"):
        """Initialize with test configuration."""
        super().__init__(
            name=name,
            base_url="https://www.test-site.com",
            referer="https://www.test-site.com/",
        )

    def _get_listing_url_path(self, slug: str, wrk_id: str) -> str:
        """Return test URL path."""
        return f"/listings/{slug}-{wrk_id}"


class TestWohnraumkarteScraper(unittest.TestCase):
    """Test cases for the WohnraumkarteScraper base class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scraper = ConcreteWohnraumkarteScraper('test_scraper')

    def test_initialization(self):
        """Test that the scraper initializes with correct properties."""
        self.assertEqual(self.scraper.name, 'test_scraper')
        self.assertEqual(
            self.scraper.api_url,
            'https://www.wohnraumkarte.de/api/getImmoList'
        )
        self.assertEqual(self.scraper.base_url, 'https://www.test-site.com')
        self.assertIn('Referer', self.scraper.headers)
        self.assertEqual(
            self.scraper.headers['Referer'],
            'https://www.test-site.com/'
        )

    def test_get_domain_name(self):
        """Test domain name extraction for logging."""
        self.assertEqual(self.scraper._get_domain_name(), 'test-site.com')

    def test_get_extra_api_params_default_empty(self):
        """Test that extra API params are empty by default."""
        params = self.scraper._get_extra_api_params()
        self.assertEqual(params, {})

    def test_build_api_params(self):
        """Test API parameter building."""
        params = self.scraper._build_api_params(limit=50, offset=0)

        self.assertEqual(params['rentType'], 'miete')
        self.assertEqual(params['city'], 'Berlin')
        self.assertEqual(params['immoType'], 'wohnung')
        self.assertEqual(params['limit'], '50')
        self.assertEqual(params['offset'], '0')
        self.assertEqual(params['orderBy'], 'date_desc')

    def test_build_address_complete(self):
        """Test address building with all fields."""
        listing_data = {
            'strasse': 'Hauptstr. 123',
            'plz': '10115',
            'ort': 'Berlin OT Mitte'
        }
        address = self.scraper._build_address(listing_data)
        self.assertEqual(address, 'Hauptstr. 123, 10115 Berlin OT Mitte')

    def test_build_address_missing_street(self):
        """Test address building when street is missing."""
        listing_data = {
            'strasse': '',
            'plz': '10115',
            'ort': 'Berlin OT Mitte'
        }
        address = self.scraper._build_address(listing_data)
        self.assertEqual(address, '10115 Berlin OT Mitte')

    def test_build_address_only_street(self):
        """Test address building with only street."""
        listing_data = {'strasse': 'Hauptstr. 123'}
        address = self.scraper._build_address(listing_data)
        self.assertEqual(address, 'Hauptstr. 123')

    def test_build_address_all_missing(self):
        """Test address building when all fields are missing."""
        listing_data = {}
        address = self.scraper._build_address(listing_data)
        self.assertEqual(address, 'N/A')

    def test_extract_borough_from_ort(self):
        """Test borough extraction from ort field."""
        listing_data = {
            'ort': 'Berlin OT Friedrichshain',
            'plz': '10243'
        }
        borough = self.scraper._extract_borough(listing_data)
        self.assertEqual(borough, 'Friedrichshain')

    def test_extract_borough_fallback_to_zip(self):
        """Test borough extraction falls back to ZIP lookup."""
        temp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump({'10115': ['Mitte']}, temp)
        temp.close()

        try:
            resolver = BoroughResolver(temp.name)
            self.scraper.set_borough_resolver(resolver)

            listing_data = {
                'ort': 'Berlin',  # No OT
                'plz': '10115'
            }
            borough = self.scraper._extract_borough(listing_data)
            self.assertEqual(borough, 'Mitte')
        finally:
            Path(temp.name).unlink(missing_ok=True)

    def test_extract_borough_no_data(self):
        """Test borough extraction returns N/A when no data available."""
        listing_data = {}
        borough = self.scraper._extract_borough(listing_data)
        self.assertEqual(borough, 'N/A')

    def test_extract_price(self):
        """Test price extraction."""
        listing_data = {'preis': '850.50'}
        price = self.scraper._extract_price(listing_data)
        self.assertEqual(price, '850.50')

    def test_extract_price_missing(self):
        """Test price extraction when missing."""
        listing_data = {}
        price = self.scraper._extract_price(listing_data)
        self.assertEqual(price, 'N/A')

    def test_extract_sqm(self):
        """Test square meter extraction."""
        listing_data = {'groesse': '75.5'}
        sqm = self.scraper._extract_sqm(listing_data)
        self.assertEqual(sqm, '75.5')

    def test_extract_sqm_missing(self):
        """Test square meter extraction when missing."""
        listing_data = {}
        sqm = self.scraper._extract_sqm(listing_data)
        self.assertEqual(sqm, 'N/A')

    def test_extract_rooms(self):
        """Test room count extraction."""
        listing_data = {'anzahl_zimmer': '3'}
        rooms = self.scraper._extract_rooms(listing_data)
        self.assertEqual(rooms, '3')

    def test_extract_rooms_half(self):
        """Test room count extraction with half rooms."""
        listing_data = {'anzahl_zimmer': '2.5'}
        rooms = self.scraper._extract_rooms(listing_data)
        self.assertEqual(rooms, '2.5')

    def test_extract_rooms_default(self):
        """Test room count extraction with default value."""
        listing_data = {}
        rooms = self.scraper._extract_rooms(listing_data)
        self.assertEqual(rooms, '1')

    def test_build_listing_url(self):
        """Test listing URL building."""
        listing_data = {
            'slug': 'test-listing',
            'wrk_id': '12345'
        }
        url = self.scraper._build_listing_url(listing_data)
        expected = 'https://www.test-site.com/listings/test-listing-12345'
        self.assertEqual(url, expected)

    def test_build_listing_url_missing_data(self):
        """Test listing URL building with missing data."""
        listing_data = {}
        url = self.scraper._build_listing_url(listing_data)
        self.assertEqual(url, 'N/A')

    def test_extract_identifier_fast(self):
        """Test fast identifier extraction."""
        listing_data = {
            'slug': 'test-listing',
            'wrk_id': '12345'
        }
        identifier = self.scraper._extract_identifier_fast(listing_data)
        expected = 'https://www.test-site.com/listings/test-listing-12345'
        self.assertEqual(identifier, expected)

    def test_extract_identifier_fast_missing_data(self):
        """Test fast identifier extraction with missing data."""
        listing_data = {'slug': 'test-listing'}
        identifier = self.scraper._extract_identifier_fast(listing_data)
        self.assertIsNone(identifier)

    def test_parse_listing(self):
        """Test parsing a complete listing."""
        listing_data = {
            'wrk_id': '12345',
            'strasse': 'Teststr. 1',
            'plz': '10115',
            'ort': 'Berlin OT Mitte',
            'preis': '900',
            'groesse': '60',
            'anzahl_zimmer': '2',
            'slug': 'test-listing'
        }

        listing = self.scraper._parse_listing(listing_data)

        self.assertIsNotNone(listing)
        self.assertEqual(listing.source, 'test_scraper')
        self.assertEqual(listing.address, 'Teststr. 1, 10115 Berlin OT Mitte')
        self.assertEqual(listing.borough, 'Mitte')
        self.assertEqual(listing.price_cold, '900')
        self.assertEqual(listing.sqm, '60')
        self.assertEqual(listing.rooms, '2')
        self.assertEqual(
            listing.link,
            'https://www.test-site.com/listings/test-listing-12345'
        )
        self.assertEqual(listing.price_total, 'N/A')

    def test_parse_listing_missing_wrk_id(self):
        """Test parsing listing without wrk_id returns None."""
        listing_data = {
            'strasse': 'Teststr. 1',
            'plz': '10115',
            'ort': 'Berlin OT Mitte'
        }

        listing = self.scraper._parse_listing(listing_data)
        self.assertIsNone(listing)

    @patch('requests.Session.get')
    def test_fetch_listings_batch(self, mock_get):
        """Test fetching a batch of listings."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {'wrk_id': '1', 'strasse': 'Test 1'},
                {'wrk_id': '2', 'strasse': 'Test 2'}
            ]
        }
        mock_get.return_value = mock_response

        import requests
        session = requests.Session()
        batch = self.scraper._fetch_listings_batch(session, limit=2, offset=0)

        self.assertEqual(len(batch), 2)
        self.assertEqual(batch[0]['wrk_id'], '1')
        self.assertEqual(batch[1]['wrk_id'], '2')

    @patch('requests.Session.get')
    def test_get_current_listings_with_new_listings(self, mock_get):
        """Test getting current listings when there are new listings."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {
                    'wrk_id': '12345',
                    'strasse': 'Teststr. 1',
                    'plz': '10115',
                    'ort': 'Berlin OT Mitte',
                    'preis': '900',
                    'groesse': '60',
                    'anzahl_zimmer': '2',
                    'slug': 'test-listing-1'
                },
                {
                    'wrk_id': '12346',
                    'strasse': 'Teststr. 2',
                    'plz': '10117',
                    'ort': 'Berlin OT Mitte',
                    'preis': '1000',
                    'groesse': '70',
                    'anzahl_zimmer': '3',
                    'slug': 'test-listing-2'
                }
            ]
        }
        mock_get.return_value = mock_response

        listings = self.scraper.get_current_listings()

        self.assertEqual(len(listings), 2)

    @patch('requests.Session.get')
    def test_get_current_listings_early_termination(self, mock_get):
        """Test early termination when known listing is encountered."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {
                    'wrk_id': '12345',
                    'strasse': 'Teststr. 1',
                    'plz': '10115',
                    'ort': 'Berlin OT Mitte',
                    'preis': '900',
                    'groesse': '60',
                    'anzahl_zimmer': '2',
                    'slug': 'test-listing-1'
                },
                {
                    'wrk_id': '12346',
                    'strasse': 'Teststr. 2',
                    'plz': '10117',
                    'ort': 'Berlin OT Mitte',
                    'preis': '1000',
                    'groesse': '70',
                    'anzahl_zimmer': '3',
                    'slug': 'test-listing-2'
                }
            ]
        }
        mock_get.return_value = mock_response

        # Create a known listing matching the second listing
        known_url = (
            'https://www.test-site.com/listings/test-listing-2-12346'
        )
        known_listings = {known_url: Mock()}

        listings = self.scraper.get_current_listings(known_listings)

        # Should only return the first listing (stops at known listing)
        self.assertEqual(len(listings), 1)

    @patch('requests.Session.get')
    def test_get_current_listings_empty_response(self, mock_get):
        """Test getting current listings with empty API response."""
        mock_response = Mock()
        mock_response.json.return_value = {'results': []}
        mock_get.return_value = mock_response

        listings = self.scraper.get_current_listings()

        self.assertEqual(len(listings), 0)


class TestExtraApiParams(unittest.TestCase):
    """Test that subclasses can add extra API parameters."""

    def test_extra_params_merged(self):
        """Test that extra params are merged into API params."""

        class ScraperWithExtraParams(WohnraumkarteScraper):
            """Scraper that adds extra API parameters."""

            def __init__(self):
                super().__init__(
                    name="extra_params_scraper",
                    base_url="https://example.com",
                    referer="https://example.com/",
                )

            def _get_listing_url_path(self, slug: str, wrk_id: str) -> str:
                return f"/{slug}-{wrk_id}"

            def _get_extra_api_params(self) -> dict:
                return {'dataSet': 'custom', 'customParam': 'value'}

        scraper = ScraperWithExtraParams()
        params = scraper._build_api_params(limit=10, offset=5)

        self.assertEqual(params['dataSet'], 'custom')
        self.assertEqual(params['customParam'], 'value')
        self.assertEqual(params['limit'], '10')
        self.assertEqual(params['offset'], '5')


if __name__ == '__main__':
    unittest.main()

