"""
Unit tests for the VonoviaScraper class.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.scrapers.vonovia import VonoviaScraper
from src.services.borough_resolver import BoroughResolver


class TestVonoviaScraper(unittest.TestCase):
    """Test cases for the VonoviaScraper."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scraper = VonoviaScraper('vonovia')

    def test_initialization(self):
        """Test that the scraper initializes with correct properties."""
        self.assertEqual(self.scraper.name, 'vonovia')
        self.assertEqual(
            self.scraper.api_url,
            'https://www.vonovia.de/api/real-estate/list'
        )
        self.assertEqual(
            self.scraper.base_url,
            'https://www.vonovia.de'
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
        # Vonovia does not use dataSet parameter (unlike Deutsche Wohnen)
        self.assertNotIn('dataSet', params)

    def test_build_address(self):
        """Test address building from listing data."""
        listing_data = {
            'strasse': 'Torfstraße 11',
            'plz': '13353',
            'ort': 'Berlin OT Wedding'
        }
        address = self.scraper._build_address(listing_data)
        self.assertEqual(address, 'Torfstraße 11, 13353 Berlin OT Wedding')

    def test_build_address_missing_street(self):
        """Test address building when street is missing."""
        listing_data = {
            'strasse': '',
            'plz': '13353',
            'ort': 'Berlin OT Wedding'
        }
        address = self.scraper._build_address(listing_data)
        self.assertEqual(address, '13353 Berlin OT Wedding')

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
        listing_data = {'preis': '1673'}
        price = self.scraper._extract_price(listing_data)
        self.assertEqual(price, '1673')

    def test_extract_price_with_decimal(self):
        """Test price extraction with decimal value."""
        listing_data = {'preis': '667.29'}
        price = self.scraper._extract_price(listing_data)
        self.assertEqual(price, '667.29')

    def test_extract_price_missing(self):
        """Test price extraction when missing."""
        listing_data = {}
        price = self.scraper._extract_price(listing_data)
        self.assertEqual(price, 'N/A')

    def test_extract_sqm(self):
        """Test square meter extraction."""
        listing_data = {'groesse': '119.26'}
        sqm = self.scraper._extract_sqm(listing_data)
        self.assertEqual(sqm, '119.26')

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

    def test_extract_rooms_half_rooms(self):
        """Test room count extraction with half rooms."""
        listing_data = {'anzahl_zimmer': '1.5'}
        rooms = self.scraper._extract_rooms(listing_data)
        self.assertEqual(rooms, '1.5')

    def test_extract_rooms_default(self):
        """Test room count extraction with default value."""
        listing_data = {}
        rooms = self.scraper._extract_rooms(listing_data)
        self.assertEqual(rooms, 'N/A')

    def test_build_listing_url(self):
        """Test listing URL building.

        The new API returns slugs that already contain the ID, so we
        just use the slug directly.
        """
        listing_data = {
            'slug': '3-zimmer-erdgeschosswohnung-zur-miete-in-berlin-wedding-82-505949',
            'wrk_id': '505949'
        }
        url = self.scraper._build_listing_url(listing_data)
        expected = (
            'https://www.vonovia.de/zuhause-finden/'
            '3-zimmer-erdgeschosswohnung-zur-miete-in-berlin-wedding-82-505949'
        )
        self.assertEqual(url, expected)

    def test_build_listing_url_missing_data(self):
        """Test listing URL building with missing data."""
        listing_data = {}
        url = self.scraper._build_listing_url(listing_data)
        self.assertEqual(url, 'N/A')

    def test_extract_identifier_fast(self):
        """Test fast identifier extraction."""
        listing_data = {
            'slug': 'test-listing-82-12345',
            'wrk_id': '12345'
        }
        identifier = self.scraper._extract_identifier_fast(listing_data)
        expected = 'https://www.vonovia.de/zuhause-finden/test-listing-82-12345'
        self.assertEqual(identifier, expected)

    def test_extract_identifier_fast_missing_data(self):
        """Test fast identifier extraction with missing data."""
        listing_data = {}
        identifier = self.scraper._extract_identifier_fast(listing_data)
        self.assertIsNone(identifier)

    def test_parse_listing(self):
        """Test parsing a complete listing."""
        listing_data = {
            'wrk_id': '505949',
            'strasse': 'Torfstraße 11',
            'plz': '13353',
            'ort': 'Berlin OT Wedding',
            'preis': '1673',
            'groesse': '119.26',
            'anzahl_zimmer': '3',
            'slug': '3-zimmer-erdgeschosswohnung-zur-miete-in-berlin-wedding-82-505949'
        }

        listing = self.scraper._parse_item(listing_data)

        self.assertIsNotNone(listing)
        self.assertEqual(listing.source, 'vonovia')
        self.assertEqual(
            listing.address,
            'Torfstraße 11, 13353 Berlin OT Wedding'
        )
        self.assertEqual(listing.borough, 'Wedding')
        self.assertEqual(listing.price_cold, '1673')
        self.assertEqual(listing.sqm, '119.26')
        self.assertEqual(listing.rooms, '3')
        self.assertEqual(
            listing.identifier,
            'https://www.vonovia.de/zuhause-finden/'
            '3-zimmer-erdgeschosswohnung-zur-miete-in-berlin-wedding-82-505949'
        )
        # Warm rent should be N/A as it's not available from API
        self.assertEqual(listing.price_total, 'N/A')

    def test_parse_listing_missing_wrk_id(self):
        """Test parsing listing without wrk_id returns None."""
        listing_data = {
            'strasse': 'Torfstraße 11',
            'plz': '13353',
            'ort': 'Berlin OT Wedding'
        }

        listing = self.scraper._parse_item(listing_data)
        self.assertIsNone(listing)

    @patch('requests.Session.get')
    def test_fetch_listings_batch(self, mock_get):
        """Test fetching a batch of listings."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {'wrk_id': '505949', 'strasse': 'Torfstraße 11'},
                {'wrk_id': '520702', 'strasse': 'Reginhardstr. 65'}
            ]
        }
        mock_get.return_value = mock_response

        import requests
        session = requests.Session()
        batch = self.scraper._fetch_listings_batch(session, limit=2, offset=0)

        self.assertEqual(len(batch), 2)
        self.assertEqual(batch[0]['wrk_id'], '505949')
        self.assertEqual(batch[1]['wrk_id'], '520702')

    @patch('requests.Session.get')
    def test_get_current_listings_with_new_listings(self, mock_get):
        """Test getting current listings when there are new listings."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {
                    'wrk_id': '505949',
                    'strasse': 'Torfstraße 11',
                    'plz': '13353',
                    'ort': 'Berlin OT Wedding',
                    'preis': '1673',
                    'groesse': '119.26',
                    'anzahl_zimmer': '3',
                    'slug': 'test-listing-1-82-505949'
                },
                {
                    'wrk_id': '520702',
                    'strasse': 'Reginhardstr. 65',
                    'plz': '13409',
                    'ort': 'Berlin OT Reinickendorf',
                    'preis': '667.29',
                    'groesse': '50.21',
                    'anzahl_zimmer': '1.5',
                    'slug': 'test-listing-2-82-520702'
                }
            ]
        }
        mock_get.return_value = mock_response

        listings, seen_known_ids = self.scraper.get_current_listings()

        self.assertEqual(len(listings), 2)
        self.assertEqual(len(seen_known_ids), 0)

    @patch('requests.Session.get')
    def test_get_current_listings_early_termination(self, mock_get):
        """Test early termination when known listing is encountered."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'results': [
                {
                    'wrk_id': '505949',
                    'strasse': 'Torfstraße 11',
                    'plz': '13353',
                    'ort': 'Berlin OT Wedding',
                    'preis': '1673',
                    'groesse': '119.26',
                    'anzahl_zimmer': '3',
                    'slug': 'test-listing-1-82-505949'
                },
                {
                    'wrk_id': '520702',
                    'strasse': 'Reginhardstr. 65',
                    'plz': '13409',
                    'ort': 'Berlin OT Reinickendorf',
                    'preis': '667.29',
                    'groesse': '50.21',
                    'anzahl_zimmer': '1.5',
                    'slug': 'test-listing-2-82-520702'
                }
            ]
        }
        mock_get.return_value = mock_response

        # Create a known listing matching the second listing
        known_url = (
            'https://www.vonovia.de/zuhause-finden/test-listing-2-82-520702'
        )
        known_listings = {known_url: Mock()}

        listings, seen_known_ids = self.scraper.get_current_listings(known_listings)

        # Should only return the first listing (stops at known listing)
        self.assertEqual(len(listings), 1)
        # The known listing should be in seen_known_ids
        self.assertIn(known_url, seen_known_ids)

    @patch('requests.Session.get')
    def test_get_current_listings_empty_response(self, mock_get):
        """Test getting current listings with empty API response."""
        mock_response = Mock()
        mock_response.json.return_value = {'results': []}
        mock_get.return_value = mock_response

        listings, seen_known_ids = self.scraper.get_current_listings()

        self.assertEqual(len(listings), 0)
        self.assertEqual(len(seen_known_ids), 0)


if __name__ == '__main__':
    unittest.main()
