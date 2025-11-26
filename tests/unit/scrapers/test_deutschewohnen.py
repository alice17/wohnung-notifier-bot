"""
Unit tests for the DeutscheWohnenScraper class.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.scrapers.deutschewohnen import DeutscheWohnenScraper
from src.services.borough_resolver import BoroughResolver


class TestDeutscheWohnenScraper(unittest.TestCase):
    """Test cases for the DeutscheWohnenScraper."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scraper = DeutscheWohnenScraper('deutschewohnen')

    def test_initialization(self):
        """Test that the scraper initializes with correct properties."""
        self.assertEqual(self.scraper.name, 'deutschewohnen')
        self.assertEqual(
            self.scraper.api_url,
            'https://www.wohnraumkarte.de/api/getImmoList'
        )
        self.assertEqual(
            self.scraper.base_url,
            'https://www.deutsche-wohnen.com'
        )

    def test_build_api_params(self):
        """Test API parameter building."""
        params = self.scraper._build_api_params(limit=50, offset=0)
        
        self.assertEqual(params['rentType'], 'miete')
        self.assertEqual(params['city'], 'Berlin')
        self.assertEqual(params['immoType'], 'wohnung')
        self.assertEqual(params['limit'], '50')
        self.assertEqual(params['offset'], '0')
        self.assertEqual(params['orderBy'], 'date_desc')
        self.assertEqual(params['dataSet'], 'deuwo')

    def test_build_address(self):
        """Test address building from listing data."""
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
        # Create a temporary mapping file for BoroughResolver
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

    def test_extract_rooms(self):
        """Test room count extraction."""
        listing_data = {'anzahl_zimmer': '3'}
        rooms = self.scraper._extract_rooms(listing_data)
        self.assertEqual(rooms, '3')

    def test_extract_rooms_default(self):
        """Test room count extraction with default value."""
        listing_data = {}
        rooms = self.scraper._extract_rooms(listing_data)
        self.assertEqual(rooms, '1')

    def test_build_listing_url(self):
        """Test listing URL building."""
        listing_data = {
            'slug': '2-zimmer-wohnung-in-berlin-mitte',
            'wrk_id': '12345'
        }
        url = self.scraper._build_listing_url(listing_data)
        expected = (
            'https://www.deutsche-wohnen.com/mieten/mietangebote/'
            '2-zimmer-wohnung-in-berlin-mitte-12345'
        )
        self.assertEqual(url, expected)

    def test_build_listing_url_missing_data(self):
        """Test listing URL building with missing data."""
        listing_data = {}
        url = self.scraper._build_listing_url(listing_data)
        self.assertEqual(url, 'N/A')

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
        self.assertEqual(listing.source, 'deutschewohnen')
        self.assertEqual(listing.address, 'Teststr. 1, 10115 Berlin OT Mitte')
        self.assertEqual(listing.borough, 'Mitte')
        self.assertEqual(listing.price_cold, '900')
        self.assertEqual(listing.sqm, '60')
        self.assertEqual(listing.rooms, '2')
        self.assertEqual(
            listing.link,
            'https://www.deutsche-wohnen.com/mieten/mietangebote/'
            'test-listing-12345'
        )
        # Warm rent should be N/A as it's not fetched from detail pages
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


if __name__ == '__main__':
    unittest.main()


