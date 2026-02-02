"""
Unit tests for the ImmobilienScoutScraper class.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock

from src.scrapers.immobilienscout import ImmobilienScoutScraper


class TestImmobilienScoutScraper(unittest.TestCase):
    """Test cases for the ImmobilienScoutScraper."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scraper = ImmobilienScoutScraper("immobilienscout")

    def test_initialization(self):
        """Test that the scraper initializes with correct properties."""
        self.assertEqual(self.scraper.name, "immobilienscout")
        self.assertEqual(self.scraper.REGION, "/de/berlin/berlin")
        self.assertEqual(
            self.scraper.url,
            "https://www.immobilienscout24.de/Suche/de/berlin/berlin"
        )

    def test_extract_address_full(self):
        """Test address extraction with all components."""
        real_estate = {
            "address": {
                "street": "Musterstraße",
                "houseNumber": "123",
                "postcode": "10115",
                "city": "Berlin",
                "quarter": "Mitte"
            }
        }
        address = self.scraper._extract_address(real_estate)
        self.assertIn("Musterstraße 123", address)
        self.assertIn("10115", address)
        self.assertIn("Berlin", address)

    def test_extract_address_partial(self):
        """Test address extraction with partial data."""
        real_estate = {
            "address": {
                "postcode": "10115",
                "city": "Berlin"
            }
        }
        address = self.scraper._extract_address(real_estate)
        self.assertIn("10115", address)
        self.assertIn("Berlin", address)

    def test_extract_address_empty(self):
        """Test address extraction with no data returns default city."""
        real_estate = {"address": {}}
        address = self.scraper._extract_address(real_estate)
        # Default city is Berlin
        self.assertEqual(address, "Berlin")

    def test_extract_address_quarter_only(self):
        """Test address extraction with only quarter includes city."""
        real_estate = {"address": {"quarter": "Prenzlauer Berg"}}
        address = self.scraper._extract_address(real_estate)
        self.assertEqual(address, "Berlin (Prenzlauer Berg)")

    def test_extract_total_price_valid(self):
        """Test total price extraction with valid value."""
        real_estate = {"totalRent": 1250.50}
        price = self.scraper._extract_total_price(real_estate)
        self.assertEqual(price, "1250.5")

    def test_extract_total_price_missing(self):
        """Test total price extraction with missing data."""
        self.assertEqual(self.scraper._extract_total_price({}), "N/A")

    def test_extract_rooms_whole_number(self):
        """Test room extraction with whole number."""
        real_estate = {"numberOfRooms": 3}
        rooms = self.scraper._extract_rooms(real_estate)
        self.assertEqual(rooms, "3")

    def test_extract_rooms_decimal(self):
        """Test room extraction with decimal."""
        real_estate = {"numberOfRooms": 2.5}
        rooms = self.scraper._extract_rooms(real_estate)
        self.assertEqual(rooms, "2.5")

    def test_extract_rooms_missing(self):
        """Test room extraction with missing data."""
        self.assertEqual(self.scraper._extract_rooms({}), "N/A")

    def test_extract_sqm_valid(self):
        """Test square meter extraction."""
        real_estate = {"livingSpace": 75.5}
        sqm = self.scraper._extract_sqm(real_estate)
        self.assertEqual(sqm, "75.5")

    def test_extract_sqm_missing(self):
        """Test square meter extraction with missing data."""
        self.assertEqual(self.scraper._extract_sqm({}), "N/A")

    def test_extract_borough_from_postcode(self):
        """Test borough extraction using postcode."""
        # Set up mock borough resolver
        mock_resolver = Mock()
        mock_resolver.get_borough_or_default.return_value = "Mitte"
        self.scraper.set_borough_resolver(mock_resolver)

        real_estate = {"address": {"postcode": "10115"}}
        borough = self.scraper._extract_borough(real_estate, "10115 Berlin")
        self.assertEqual(borough, "Mitte")

    def test_parse_listing_valid(self):
        """Test parsing a valid listing item with current API structure."""
        item = {
            "type": "listing",
            "item": {
                "id": "123456789",
                "title": "Schöne Wohnung",
                "address": {
                    "line": "Teststraße 10, 10115 Berlin, Mitte"
                },
                "attributes": [
                    {"label": "", "value": "1.000 €"},
                    {"label": "", "value": "60 m²"},
                    {"label": "", "value": "2 Zi."}
                ]
            }
        }
        listing = self.scraper._parse_listing(item)

        self.assertIsNotNone(listing)
        self.assertEqual(listing.source, "immobilienscout")
        self.assertIn("123456789", listing.identifier)
        self.assertIn("Teststraße 10", listing.address)
        # Attribute price is treated as cold rent, not total
        self.assertEqual(listing.price_cold, "1000.0")
        self.assertEqual(listing.rooms, "2")
        self.assertEqual(listing.sqm, "60.0")

    def test_parse_listing_with_structured_prices(self):
        """Test parsing listing with structured warm/cold rent fields."""
        item = {
            "type": "listing",
            "item": {
                "id": "123456789",
                "title": "Schöne Wohnung",
                "address": {
                    "line": "Teststraße 10, 10115 Berlin, Mitte"
                },
                "totalRent": 1200.0,
                "baseRent": 1000.0,
                "attributes": [
                    {"label": "", "value": "1.000 €"},
                    {"label": "", "value": "60 m²"},
                    {"label": "", "value": "2 Zi."}
                ]
            }
        }
        listing = self.scraper._parse_listing(item)

        self.assertIsNotNone(listing)
        # Structured fields take priority
        self.assertEqual(listing.price_total, "1200.0")
        self.assertEqual(listing.price_cold, "1000.0")
        self.assertEqual(listing.rooms, "2")
        self.assertEqual(listing.sqm, "60.0")

    def test_parse_listing_missing_id(self):
        """Test parsing listing without ID returns None."""
        item = {"resultlist.realEstate": {"address": {}}}
        listing = self.scraper._parse_listing(item)
        self.assertIsNone(listing)

    def test_extract_listing_items_standard_structure(self):
        """Test extracting listing items from standard API response."""
        results = {
            "searchResponseModel": {
                "resultlist.resultlist": {
                    "resultlistEntries": [
                        {"resultlistEntry": [{"@id": "1"}, {"@id": "2"}]}
                    ]
                }
            },
            "totalResults": 2
        }
        items = self.scraper._extract_listing_items(results)
        self.assertEqual(len(items), 2)

    def test_extract_listing_items_direct_access(self):
        """Test extracting listing items with direct resultlistEntry access."""
        results = {"resultlistEntry": [{"@id": "1"}, {"@id": "2"}]}
        items = self.scraper._extract_listing_items(results)
        self.assertEqual(len(items), 2)

    def test_extract_listing_items_empty(self):
        """Test extracting listing items from empty response."""
        results = {}
        items = self.scraper._extract_listing_items(results)
        self.assertEqual(len(items), 0)

    def test_extract_listing_items_filters_ads(self):
        """Test that advertisements are filtered out from results."""
        results = {
            "resultListItems": [
                {"type": "EXPOSE_RESULT", "item": {"id": "123"}},
                {"type": "AD_RESULT", "item": {"id": "ad1"}},
                {"type": "EXPOSE_RESULT", "item": {"id": "456"}},
                {"type": "BANNER", "item": {"id": "banner1"}},
            ]
        }
        items = self.scraper._extract_listing_items(results)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["item"]["id"], "123")
        self.assertEqual(items[1]["item"]["id"], "456")


class TestImmobilienScoutScraperIntegration(unittest.TestCase):
    """Integration tests for the ImmobilienScout scraper API calls."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = ImmobilienScoutScraper("immobilienscout")

    @patch("src.scrapers.immobilienscout.requests.Session")
    def test_get_current_listings_empty(self, mock_session_class):
        """Test get_current_listings with no results."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"totalResults": 0}
        mock_response.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session

        # Force re-initialization of session
        self.scraper._session = mock_session

        listings, seen_known_ids = self.scraper.get_current_listings()
        self.assertEqual(len(listings), 0)
        self.assertEqual(len(seen_known_ids), 0)

    @patch("src.scrapers.immobilienscout.requests.Session")
    def test_get_current_listings_filters_known(self, mock_session_class):
        """Test that known listings are filtered and tracked."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "resultlistEntry": [
                {"@id": "known-123", "resultlist.realEstate": {}},
                {"@id": "new-456", "resultlist.realEstate": {
                    "address": {"postcode": "10115"},
                    "price": {"value": 1000},
                    "numberOfRooms": 2,
                    "livingSpace": 50
                }},
            ],
            "totalResults": 2
        }
        mock_response.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        self.scraper._session = mock_session

        known_listings = {
            "https://www.immobilienscout24.de/expose/known-123": Mock()
        }

        listings, seen_known_ids = self.scraper.get_current_listings(known_listings)

        # The known listing should be tracked
        self.assertIn(
            "https://www.immobilienscout24.de/expose/known-123", seen_known_ids
        )
        # Only the new listing should be in results
        self.assertNotIn(
            "https://www.immobilienscout24.de/expose/known-123", listings
        )

    def test_session_lazy_initialization(self):
        """Test that session is lazily initialized."""
        scraper = ImmobilienScoutScraper("test")
        self.assertIsNone(scraper._session)

        # Access session property
        session = scraper.session
        self.assertIsNotNone(scraper._session)
        self.assertEqual(session.headers["User-Agent"], "ImmoScout_27.12_26.2_._")
        self.assertEqual(session.headers["Connection"], "keep-alive")

    def test_fetch_page_parameters(self):
        """Test that _fetch_page sends correct API parameters."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"resultListItems": []}
        mock_response.raise_for_status = MagicMock()
        mock_session.post.return_value = mock_response

        self.scraper._session = mock_session
        self.scraper._fetch_page(page_number=2)

        # Verify the API call
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args

        # Check URL
        self.assertIn("api.mobile.immobilienscout24.de", call_args[0][0])
        self.assertIn("search/list", call_args[0][0])

        # Check params
        params = call_args[1]["params"]
        self.assertEqual(params["pricetype"], "calculatedtotalrent")
        self.assertEqual(params["realestatetype"], "apartmentrent")
        self.assertEqual(params["searchType"], "region")
        self.assertEqual(params["geocodes"], "/de/berlin/berlin")
        self.assertEqual(params["pagenumber"], 2)

        # Check payload
        payload = call_args[1]["json"]
        self.assertIn("supportedREsultListType", payload)
        self.assertIn("userData", payload)

    def test_is_listing_active_returns_true_on_200(self):
        """Test is_listing_active returns True when listing exists."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.get.return_value = mock_response

        self.scraper._session = mock_session
        result = self.scraper.is_listing_active("123456")

        self.assertTrue(result)
        mock_session.get.assert_called_once()
        self.assertIn("expose/123456", mock_session.get.call_args[0][0])

    def test_is_listing_active_returns_false_on_404(self):
        """Test is_listing_active returns False when listing not found."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_session.get.return_value = mock_response

        self.scraper._session = mock_session
        result = self.scraper.is_listing_active("123456")

        self.assertFalse(result)

    def test_is_listing_active_returns_none_on_error(self):
        """Test is_listing_active returns None on request error."""
        import requests as req
        mock_session = MagicMock()
        mock_session.get.side_effect = req.RequestException("Connection error")

        self.scraper._session = mock_session
        result = self.scraper.is_listing_active("123456")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
