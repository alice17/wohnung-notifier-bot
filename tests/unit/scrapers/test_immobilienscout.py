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

    @patch.object(ImmobilienScoutScraper, "_fetch_expose_details", return_value=None)
    def test_parse_listing_valid(self, mock_fetch_expose):
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
        listing = self.scraper._parse_item(item)

        self.assertIsNotNone(listing)
        self.assertEqual(listing.source, "immobilienscout")
        self.assertIn("123456789", listing.identifier)
        self.assertIn("Teststraße 10", listing.address)
        # Attribute price is treated as cold rent, not total
        self.assertEqual(listing.price_cold, "1000.0")
        self.assertEqual(listing.rooms, "2")
        self.assertEqual(listing.sqm, "60.0")
        # Expose details fetched since warm rent was missing
        mock_fetch_expose.assert_called_once_with("123456789")

    @patch.object(ImmobilienScoutScraper, "_fetch_expose_details")
    def test_parse_listing_fetches_warm_rent_from_expose(self, mock_fetch_expose):
        """Test that _parse_listing fetches warm rent from expose when missing."""
        mock_fetch_expose.return_value = {
            "sections": [
                {
                    "type": "COST_CHECK",
                    "totalRent": 1350.50,
                }
            ]
        }
        item = {
            "type": "listing",
            "item": {
                "id": "987654321",
                "title": "Wohnung ohne Warmmiete",
                "address": {
                    "line": "Beispielstraße 5, 10115 Berlin, Mitte"
                },
                "attributes": [
                    {"label": "", "value": "1.100 €"},
                    {"label": "", "value": "70 m²"},
                    {"label": "", "value": "3 Zi."}
                ]
            }
        }
        listing = self.scraper._parse_item(item)

        self.assertIsNotNone(listing)
        mock_fetch_expose.assert_called_once_with("987654321")
        # Warm rent comes from expose details
        self.assertEqual(listing.price_total, "1350.5")
        # Cold rent comes from attributes
        self.assertEqual(listing.price_cold, "1100.0")

    def test_parse_listing_missing_id(self):
        """Test parsing listing without ID returns None."""
        item = {"resultlist.realEstate": {"address": {}}}
        listing = self.scraper._parse_item(item)
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
        # Newest-first order: new listing first, then known (early termination stops after known)
        mock_response.json.return_value = {
            "resultlistEntry": [
                {"@id": "new-456", "resultlist.realEstate": {
                    "address": {"postcode": "10115"},
                    "price": {"value": 1000},
                    "numberOfRooms": 2,
                    "livingSpace": 50
                }},
                {"@id": "known-123", "resultlist.realEstate": {}},
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
        # Only the new listing should be in results (known triggers early stop)
        self.assertIn(
            "https://www.immobilienscout24.de/expose/new-456", listings
        )
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
        self.assertEqual(params["sorting"], "-firstactivation")

        # Check payload
        payload = call_args[1]["json"]
        self.assertIn("supportedREsultListType", payload)
        self.assertIn("userData", payload)

    def test_fetch_expose_details_success(self):
        """Test fetching expose details returns parsed JSON."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "expose.expose": {
                "realEstate": {
                    "price": {"calculatedTotalRent": 1200.0}
                }
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response

        self.scraper._session = mock_session
        result = self.scraper._fetch_expose_details("158382494")

        self.assertIsNotNone(result)
        mock_session.get.assert_called_once()
        self.assertIn("expose/158382494", mock_session.get.call_args[0][0])

    def test_fetch_expose_details_failure(self):
        """Test fetching expose details returns None on error."""
        import requests as req
        mock_session = MagicMock()
        mock_session.get.side_effect = req.RequestException("Connection error")

        self.scraper._session = mock_session
        result = self.scraper._fetch_expose_details("158382494")

        self.assertIsNone(result)

    def test_is_blocked_agent_tauschwohnung(self):
        """Test that Tauschwohnung GmbH is detected as blocked agent."""
        expose = {
            "sections": [
                {
                    "type": "AGENTS_INFO",
                    "title": "Anbieter Informationen",
                    "company": "Tauschwohnung GmbH",
                    "name": "Tauschwohnung Wohnungstausch",
                }
            ]
        }
        self.assertTrue(self.scraper._is_blocked_agent(expose))

    def test_is_blocked_agent_wohnungsswap(self):
        """Test that Wohnungsswap.de - Relocasa AB is detected as blocked agent."""
        expose = {
            "sections": [
                {
                    "type": "AGENTS_INFO",
                    "title": "Anbieter Informationen",
                    "company": "Wohnungsswap.de - Relocasa AB -",
                    "name": "Wohnungsswap",
                }
            ]
        }
        self.assertTrue(self.scraper._is_blocked_agent(expose))

    def test_is_blocked_agent_regular_company(self):
        """Test that a regular company is not blocked."""
        expose = {
            "sections": [
                {
                    "type": "AGENTS_INFO",
                    "title": "Anbieter Informationen",
                    "company": "Hausverwaltung Müller GmbH",
                    "name": "Max Müller",
                }
            ]
        }
        self.assertFalse(self.scraper._is_blocked_agent(expose))

    def test_is_blocked_agent_no_sections(self):
        """Test that missing sections does not crash."""
        expose = {"header": {"id": "123"}}
        self.assertFalse(self.scraper._is_blocked_agent(expose))

    def test_is_blocked_agent_no_company_field(self):
        """Test that missing company field does not crash."""
        expose = {
            "sections": [
                {"type": "AGENTS_INFO", "title": "Anbieter Informationen"}
            ]
        }
        self.assertFalse(self.scraper._is_blocked_agent(expose))

    @patch.object(ImmobilienScoutScraper, "_fetch_expose_details")
    def test_parse_item_skips_blocked_agent(self, mock_fetch_expose):
        """Test that _parse_item returns None for blocked agents."""
        mock_fetch_expose.return_value = {
            "sections": [
                {
                    "type": "AGENTS_INFO",
                    "company": "Tauschwohnung GmbH",
                    "name": "Tauschwohnung Wohnungstausch",
                },
                {"type": "COST_CHECK", "totalRent": 900.0},
            ]
        }
        item = {
            "type": "listing",
            "item": {
                "id": "111222333",
                "address": {"line": "Swapstraße 1, 10115 Berlin"},
                "attributes": [
                    {"label": "", "value": "800 €"},
                    {"label": "", "value": "50 m²"},
                    {"label": "", "value": "2 Zi."},
                ],
            },
        }
        listing = self.scraper._parse_item(item)
        self.assertIsNone(listing)

    def test_extract_warm_rent_from_cost_check_section(self):
        """Test warm rent extraction from COST_CHECK section."""
        expose = {
            "sections": [
                {"type": "MEDIA", "media": []},
                {"type": "COST_CHECK", "totalRent": 1388.4, "expenses": []},
            ]
        }
        result = self.scraper._extract_warm_rent_from_expose(expose)
        self.assertEqual(result, "1388.4")

    def test_extract_warm_rent_from_kosten_attribute_list(self):
        """Test warm rent extraction from Kosten ATTRIBUTE_LIST fallback."""
        expose = {
            "sections": [
                {
                    "type": "ATTRIBUTE_LIST",
                    "title": "Kosten",
                    "attributes": [
                        {"type": "TEXT", "label": "Kaltmiete (zzgl. Nebenkosten):", "text": "1.275 €"},
                        {"type": "TEXT", "label": "Nebenkosten:", "text": "71,40 €"},
                        {"type": "TEXT", "label": "Gesamtmiete:", "text": "1.388,40 €"},
                    ],
                }
            ]
        }
        result = self.scraper._extract_warm_rent_from_expose(expose)
        self.assertEqual(result, "1388.4")

    def test_extract_warm_rent_from_expose_prefers_cost_check(self):
        """Test that COST_CHECK is preferred over Kosten ATTRIBUTE_LIST."""
        expose = {
            "sections": [
                {"type": "COST_CHECK", "totalRent": 1400.0},
                {
                    "type": "ATTRIBUTE_LIST",
                    "title": "Kosten",
                    "attributes": [
                        {"type": "TEXT", "label": "Gesamtmiete:", "text": "1.388,40 €"},
                    ],
                },
            ]
        }
        result = self.scraper._extract_warm_rent_from_expose(expose)
        self.assertEqual(result, "1400.0")

    def test_extract_warm_rent_from_expose_missing(self):
        """Test warm rent extraction returns N/A when not found."""
        expose = {"sections": [{"type": "MEDIA", "media": []}]}
        result = self.scraper._extract_warm_rent_from_expose(expose)
        self.assertEqual(result, "N/A")

    def test_extract_warm_rent_from_expose_no_sections(self):
        """Test warm rent extraction returns N/A when sections missing."""
        expose = {"header": {"id": "123"}}
        result = self.scraper._extract_warm_rent_from_expose(expose)
        self.assertEqual(result, "N/A")

    def test_parse_german_price(self):
        """Test German price string parsing."""
        self.assertEqual(ImmobilienScoutScraper._parse_german_price("1.388,40 €"), "1388.4")
        self.assertEqual(ImmobilienScoutScraper._parse_german_price("1.275 €"), "1275.0")
        self.assertEqual(ImmobilienScoutScraper._parse_german_price("71,40 €"), "71.4")
        self.assertEqual(ImmobilienScoutScraper._parse_german_price("keine Angabe"), "N/A")

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
