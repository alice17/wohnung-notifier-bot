"""
Unit tests for the KleinanzeigenScraper class.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from src.scrapers.kleinanzeigen import KleinanzeigenScraper
from src.services.borough_resolver import BoroughResolver


class TestKleinanzeigenScraper(unittest.TestCase):
    """Test cases for the KleinanzeigenScraper initialization and basic methods."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.scraper = KleinanzeigenScraper("kleinanzeigen")

    def test_initialization(self):
        """Test that the scraper initializes with correct properties."""
        self.assertEqual(self.scraper.name, "kleinanzeigen")
        self.assertIn("kleinanzeigen.de", self.scraper.url)
        self.assertIn("sortierung:neuste", self.scraper.url)

    def test_initialization_custom_name(self):
        """Test initialization with a custom name."""
        scraper = KleinanzeigenScraper("custom_kleinanzeigen")
        self.assertEqual(scraper.name, "custom_kleinanzeigen")

    def test_headers_include_required_fields(self):
        """Test that headers include necessary fields for Kleinanzeigen."""
        self.assertIn("Accept", self.scraper.headers)
        self.assertIn("Accept-Language", self.scraper.headers)
        self.assertIn("Referer", self.scraper.headers)
        self.assertIn("User-Agent", self.scraper.headers)

    def test_clean_text_basic(self):
        """Test basic text cleaning functionality."""
        self.assertEqual(
            self.scraper._clean_text("  Hello   World  "), "Hello World"
        )

    def test_clean_text_with_euro_symbol(self):
        """Test text cleaning removes euro symbol."""
        self.assertEqual(self.scraper._clean_text("1.200 €"), "1.200")

    def test_clean_text_with_sqm_unit(self):
        """Test text cleaning removes square meter unit."""
        self.assertEqual(self.scraper._clean_text("75 m²"), "75")

    def test_clean_text_with_vb(self):
        """Test text cleaning removes VB (Verhandlungsbasis)."""
        self.assertEqual(self.scraper._clean_text("1.500 € VB"), "1.500")

    def test_clean_text_none(self):
        """Test text cleaning with None returns N/A."""
        self.assertEqual(self.scraper._clean_text(None), "N/A")

    def test_clean_text_empty(self):
        """Test text cleaning with empty string returns N/A."""
        self.assertEqual(self.scraper._clean_text(""), "N/A")


class TestKleinanzeigenScraperIdentifierExtraction(unittest.TestCase):
    """Test cases for identifier and URL extraction functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = KleinanzeigenScraper("kleinanzeigen")

    def test_extract_identifier_fast_with_data_href(self):
        """Test identifier extraction from data-href attribute."""
        html = """
        <div class="ad-listitem">
            <article class="aditem" data-adid="12345678" 
                     data-href="/s-anzeige/schoene-wohnung-berlin/12345678">
                <div class="aditem-main"></div>
            </article>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        identifier = self.scraper._extract_identifier_fast(listing_soup)

        self.assertEqual(
            identifier,
            "https://www.kleinanzeigen.de/s-anzeige/schoene-wohnung-berlin/12345678"
        )

    def test_extract_identifier_fast_no_aditem(self):
        """Test identifier extraction returns None when no aditem found."""
        html = '<div class="ad-listitem"><div>Some content</div></div>'
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        identifier = self.scraper._extract_identifier_fast(listing_soup)

        self.assertIsNone(identifier)

    def test_extract_identifier_fast_no_data_href(self):
        """Test identifier extraction returns None when no data-href."""
        html = """
        <div class="ad-listitem">
            <article class="aditem" data-adid="12345678">
                <div class="aditem-main"></div>
            </article>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        identifier = self.scraper._extract_identifier_fast(listing_soup)

        self.assertIsNone(identifier)

    def test_extract_ad_id(self):
        """Test advertisement ID extraction."""
        html = """
        <div class="ad-listitem">
            <article class="aditem" data-adid="98765432">
                <div class="aditem-main"></div>
            </article>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        ad_id = self.scraper._extract_ad_id(listing_soup)

        self.assertEqual(ad_id, "98765432")

    def test_extract_ad_id_no_aditem(self):
        """Test advertisement ID extraction returns None when no aditem."""
        html = '<div class="ad-listitem"><div>Content</div></div>'
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        ad_id = self.scraper._extract_ad_id(listing_soup)

        self.assertIsNone(ad_id)

    def test_extract_listing_url_from_data_href(self):
        """Test URL extraction from data-href attribute."""
        html = """
        <div class="ad-listitem">
            <article class="aditem" data-href="/s-anzeige/wohnung/12345">
            </article>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        url = self.scraper._extract_listing_url(listing_soup)

        self.assertEqual(
            url, "https://www.kleinanzeigen.de/s-anzeige/wohnung/12345"
        )

    def test_extract_listing_url_fallback_to_link(self):
        """Test URL extraction falls back to anchor link."""
        html = """
        <div class="ad-listitem">
            <article class="aditem">
                <a href="/s-anzeige/fallback-wohnung/67890">Link</a>
            </article>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        url = self.scraper._extract_listing_url(listing_soup)

        self.assertEqual(
            url, "https://www.kleinanzeigen.de/s-anzeige/fallback-wohnung/67890"
        )


class TestKleinanzeigenScraperPriceExtraction(unittest.TestCase):
    """Test cases for price extraction functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = KleinanzeigenScraper("kleinanzeigen")

    def test_extract_price_simple(self):
        """Test simple price extraction."""
        html = """
        <div class="ad-listitem">
            <p class="aditem-main--middle--price-shipping--price">1.200 €</p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        price = self.scraper._extract_price(listing_soup)

        self.assertEqual(price, "1200")

    def test_extract_price_with_cents(self):
        """Test price extraction with German decimal format."""
        html = """
        <div class="ad-listitem">
            <p class="aditem-main--middle--price-shipping--price">899,50 €</p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        price = self.scraper._extract_price(listing_soup)

        self.assertEqual(price, "899.50")

    def test_extract_price_with_old_price(self):
        """Test price extraction removes old strikethrough price."""
        html = """
        <div class="ad-listitem">
            <p class="aditem-main--middle--price-shipping--price">
                <span class="aditem-main--middle--price-shipping--old-price">
                    1.500 €
                </span>
                1.200 €
            </p>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        price = self.scraper._extract_price(listing_soup)

        self.assertEqual(price, "1200")

    def test_extract_price_not_found(self):
        """Test price extraction returns N/A when not found."""
        html = '<div class="ad-listitem"><div>No price here</div></div>'
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        price = self.scraper._extract_price(listing_soup)

        self.assertEqual(price, "N/A")


class TestKleinanzeigenScraperSizeAndRoomsExtraction(unittest.TestCase):
    """Test cases for size and rooms extraction functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = KleinanzeigenScraper("kleinanzeigen")

    def test_extract_size_and_rooms_both_present(self):
        """Test extraction when both size and rooms are present."""
        html = """
        <div class="ad-listitem">
            <div class="aditem-main--middle--tags">
                85 m² | 3 Zi.
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        size, rooms = self.scraper._extract_size_and_rooms(listing_soup)

        self.assertEqual(size, "85")
        self.assertEqual(rooms, "3")

    def test_extract_size_with_decimal(self):
        """Test size extraction with German decimal format."""
        html = """
        <div class="ad-listitem">
            <div class="aditem-main--middle--tags">
                138,01 m² | 4 Zi.
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        size, rooms = self.scraper._extract_size_and_rooms(listing_soup)

        self.assertEqual(size, "138.01")
        self.assertEqual(rooms, "4")

    def test_extract_size_only(self):
        """Test extraction when only size is present, rooms defaults to 1."""
        html = """
        <div class="ad-listitem">
            <div class="aditem-main--middle--tags">
                45 m²
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        size, rooms = self.scraper._extract_size_and_rooms(listing_soup)

        self.assertEqual(size, "45")
        self.assertEqual(rooms, "1")

    def test_extract_no_tags_element(self):
        """Test extraction when tags element is missing."""
        html = '<div class="ad-listitem"><div>No tags</div></div>'
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        size, rooms = self.scraper._extract_size_and_rooms(listing_soup)

        self.assertEqual(size, "N/A")
        self.assertEqual(rooms, "1")


class TestKleinanzeigenScraperAddressExtraction(unittest.TestCase):
    """Test cases for address extraction functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = KleinanzeigenScraper("kleinanzeigen")

    def test_extract_address_simple(self):
        """Test simple address extraction."""
        html = """
        <div class="ad-listitem">
            <div class="aditem-main--top--left">
                10115 Berlin Mitte
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        address = self.scraper._extract_address(listing_soup)

        self.assertEqual(address, "10115 Berlin Mitte")

    def test_extract_address_with_distance(self):
        """Test address extraction removes distance suffix."""
        html = """
        <div class="ad-listitem">
            <div class="aditem-main--top--left">
                12345 Berlin Kreuzberg (6 km)
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        address = self.scraper._extract_address(listing_soup)

        self.assertEqual(address, "12345 Berlin Kreuzberg")

    def test_extract_address_not_found(self):
        """Test address extraction returns N/A when not found."""
        html = '<div class="ad-listitem"><div>No address</div></div>'
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        address = self.scraper._extract_address(listing_soup)

        self.assertEqual(address, "N/A")


class TestKleinanzeigenScraperBoroughExtraction(unittest.TestCase):
    """Test cases for borough extraction functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = KleinanzeigenScraper("kleinanzeigen")

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

        borough = self.scraper._extract_borough_from_address("10115 Berlin Mitte")

        self.assertEqual(borough, "Mitte")

    def test_extract_borough_from_address_no_zip(self):
        """Test borough extraction when address has no ZIP code."""
        resolver = self._create_resolver({"10115": ["Mitte"]})
        self.scraper.set_borough_resolver(resolver)

        borough = self.scraper._extract_borough_from_address("Berlin Mitte")

        self.assertEqual(borough, "N/A")

    def test_extract_borough_from_address_unknown_zip(self):
        """Test borough extraction with unknown ZIP code."""
        resolver = self._create_resolver({"10115": ["Mitte"]})
        self.scraper.set_borough_resolver(resolver)

        borough = self.scraper._extract_borough_from_address("99999 Somewhere")

        self.assertEqual(borough, "N/A")


class TestKleinanzeigenScraperListingParsing(unittest.TestCase):
    """Test cases for complete listing parsing."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = KleinanzeigenScraper("kleinanzeigen")

    def _create_resolver(self, mapping: dict) -> BoroughResolver:
        """Creates a BoroughResolver with specified mapping."""
        temp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(mapping, temp)
        temp.close()
        resolver = BoroughResolver(temp.name)
        Path(temp.name).unlink(missing_ok=True)
        return resolver

    def test_parse_listing_complete(self):
        """Test parsing a complete listing with all fields."""
        resolver = self._create_resolver({"10115": ["Mitte"]})
        self.scraper.set_borough_resolver(resolver)

        html = """
        <div class="ad-listitem">
            <article class="aditem" data-adid="12345678" 
                     data-href="/s-anzeige/schoene-3-zimmer-wohnung/12345678">
                <div class="aditem-main">
                    <div class="aditem-main--top">
                        <div class="aditem-main--top--left">
                            10115 Berlin Mitte
                        </div>
                    </div>
                    <div class="aditem-main--middle">
                        <div class="aditem-main--middle--tags">
                            85 m² | 3 Zi.
                        </div>
                        <p class="aditem-main--middle--price-shipping--price">
                            1.200 €
                        </p>
                    </div>
                </div>
            </article>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        listing = self.scraper._parse_listing(listing_soup)

        self.assertIsNotNone(listing)
        self.assertEqual(
            listing.identifier,
            "https://www.kleinanzeigen.de/s-anzeige/schoene-3-zimmer-wohnung/12345678"
        )
        self.assertEqual(listing.address, "10115 Berlin Mitte")
        self.assertEqual(listing.borough, "Mitte")
        self.assertEqual(listing.sqm, "85")
        self.assertEqual(listing.rooms, "3")
        self.assertEqual(listing.price_cold, "1200")
        self.assertFalse(listing.wbs)
        self.assertEqual(listing.source, "kleinanzeigen")

    def test_parse_listing_no_ad_id(self):
        """Test parsing listing without ad ID returns None."""
        html = """
        <div class="ad-listitem">
            <article class="aditem">
                <div class="aditem-main"></div>
            </article>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        listing = self.scraper._parse_listing(listing_soup)

        self.assertIsNone(listing)

    def test_parse_listing_no_url(self):
        """Test parsing listing without URL returns None."""
        html = """
        <div class="ad-listitem">
            <article class="aditem" data-adid="12345678">
                <div class="aditem-main"></div>
            </article>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        listing = self.scraper._parse_listing(listing_soup)

        self.assertIsNone(listing)


class TestKleinanzeigenScraperHTTPRequests(unittest.TestCase):
    """Test cases for HTTP request handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = KleinanzeigenScraper("kleinanzeigen")

    @patch("src.scrapers.kleinanzeigen.requests.Session")
    def test_get_current_listings_success(self, mock_session_class):
        """Test successful HTTP request and parsing."""
        html_content = """
        <html><body>
        <ul id="srchrslt-adtable">
            <li class="ad-listitem">
                <article class="aditem" data-adid="11111111" 
                         data-href="/s-anzeige/test-wohnung/11111111">
                    <div class="aditem-main">
                        <div class="aditem-main--top">
                            <div class="aditem-main--top--left">10115 Berlin</div>
                        </div>
                        <div class="aditem-main--middle">
                            <div class="aditem-main--middle--tags">50 m² | 2 Zi.</div>
                            <p class="aditem-main--middle--price-shipping--price">800 €</p>
                        </div>
                    </div>
                </article>
            </li>
        </ul>
        </body></html>
        """
        mock_session = Mock()
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        listings, seen_known_ids = self.scraper.get_current_listings()

        self.assertEqual(len(listings), 1)
        self.assertIn(
            "https://www.kleinanzeigen.de/s-anzeige/test-wohnung/11111111",
            listings
        )

    @patch("src.scrapers.kleinanzeigen.requests.Session")
    def test_get_current_listings_with_known_listings(self, mock_session_class):
        """Test HTTP request with known listings triggers early termination."""
        html_content = """
        <html><body>
        <ul id="srchrslt-adtable">
            <li class="ad-listitem">
                <article class="aditem" data-adid="22222222" 
                         data-href="/s-anzeige/new-listing/22222222">
                    <div class="aditem-main">
                        <div class="aditem-main--top">
                            <div class="aditem-main--top--left">10115 Berlin</div>
                        </div>
                        <div class="aditem-main--middle">
                            <div class="aditem-main--middle--tags">60 m² | 2 Zi.</div>
                            <p class="aditem-main--middle--price-shipping--price">900 €</p>
                        </div>
                    </div>
                </article>
            </li>
            <li class="ad-listitem">
                <article class="aditem" data-adid="11111111" 
                         data-href="/s-anzeige/known-listing/11111111">
                    <div class="aditem-main">
                        <div class="aditem-main--top">
                            <div class="aditem-main--top--left">10115 Berlin</div>
                        </div>
                    </div>
                </article>
            </li>
        </ul>
        </body></html>
        """
        mock_session = Mock()
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        known_listings = {
            "https://www.kleinanzeigen.de/s-anzeige/known-listing/11111111": Mock()
        }

        listings, seen_known_ids = self.scraper.get_current_listings(known_listings)

        # Should find one new listing before hitting known listing
        self.assertEqual(len(listings), 1)
        self.assertIn(
            "https://www.kleinanzeigen.de/s-anzeige/new-listing/22222222",
            listings
        )
        self.assertIn(
            "https://www.kleinanzeigen.de/s-anzeige/known-listing/11111111",
            seen_known_ids
        )

    @patch("src.scrapers.kleinanzeigen.requests.Session")
    def test_get_current_listings_request_error(self, mock_session_class):
        """Test HTTP request error handling."""
        import requests

        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.RequestException(
            "Network error"
        )
        mock_session_class.return_value = mock_session

        with self.assertRaises(requests.exceptions.RequestException):
            self.scraper.get_current_listings()

    @patch("src.scrapers.kleinanzeigen.requests.Session")
    def test_get_current_listings_filters_empty_items(self, mock_session_class):
        """Test that empty ad-listitem elements are filtered out."""
        html_content = """
        <html><body>
        <ul id="srchrslt-adtable">
            <li class="ad-listitem">
                <!-- Empty spacer element -->
            </li>
            <li class="ad-listitem">
                <article class="aditem" data-adid="33333333" 
                         data-href="/s-anzeige/real-listing/33333333">
                    <div class="aditem-main">
                        <div class="aditem-main--top">
                            <div class="aditem-main--top--left">10115 Berlin</div>
                        </div>
                        <div class="aditem-main--middle">
                            <div class="aditem-main--middle--tags">70 m² | 3 Zi.</div>
                            <p class="aditem-main--middle--price-shipping--price">1000 €</p>
                        </div>
                    </div>
                </article>
            </li>
            <li class="ad-listitem">
                <!-- Another spacer -->
                <div class="placeholder"></div>
            </li>
        </ul>
        </body></html>
        """
        mock_session = Mock()
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        listings, _ = self.scraper.get_current_listings()

        # Should only find the one valid listing
        self.assertEqual(len(listings), 1)


class TestKleinanzeigenScraperIntegration(unittest.TestCase):
    """Integration tests with realistic HTML structure from kleinanzeigen.de."""

    def setUp(self):
        """Set up test fixtures."""
        self.scraper = KleinanzeigenScraper("kleinanzeigen")

    def _create_resolver(self, mapping: dict) -> BoroughResolver:
        """Creates a BoroughResolver with specified mapping."""
        temp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(mapping, temp)
        temp.close()
        resolver = BoroughResolver(temp.name)
        Path(temp.name).unlink(missing_ok=True)
        return resolver

    def test_parse_realistic_berlin_mitte_listing(self):
        """
        Test parsing a realistic listing from Berlin Mitte.
        
        Simulates a typical Kleinanzeigen listing structure for a
        3-room apartment in Mitte.
        """
        resolver = self._create_resolver({"10115": ["Mitte"]})
        self.scraper.set_borough_resolver(resolver)

        html = """
        <div class="ad-listitem">
            <article class="aditem" data-adid="2847593621" 
                     data-href="/s-anzeige/helle-3-zimmer-wohnung-mit-balkon-in-mitte/2847593621">
                <div class="aditem-main">
                    <div class="aditem-main--top">
                        <div class="aditem-main--top--left">
                            10115 Berlin Mitte
                        </div>
                        <div class="aditem-main--top--right">
                            Heute, 14:32
                        </div>
                    </div>
                    <div class="aditem-main--middle">
                        <h2 class="text-module-begin">
                            Helle 3-Zimmer-Wohnung mit Balkon in Mitte
                        </h2>
                        <div class="aditem-main--middle--tags">
                            85 m² | 3 Zi.
                        </div>
                        <p class="aditem-main--middle--price-shipping--price">
                            1.450 €
                        </p>
                    </div>
                </div>
            </article>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        listing = self.scraper._parse_listing(listing_soup)

        self.assertIsNotNone(listing)
        self.assertEqual(
            listing.identifier,
            "https://www.kleinanzeigen.de/s-anzeige/"
            "helle-3-zimmer-wohnung-mit-balkon-in-mitte/2847593621"
        )
        self.assertEqual(listing.address, "10115 Berlin Mitte")
        self.assertEqual(listing.borough, "Mitte")
        self.assertEqual(listing.sqm, "85")
        self.assertEqual(listing.rooms, "3")
        self.assertEqual(listing.price_cold, "1450")
        self.assertEqual(listing.source, "kleinanzeigen")

    def test_parse_realistic_kreuzberg_listing(self):
        """
        Test parsing a realistic listing from Kreuzberg.
        
        Simulates a typical listing with decimal square meters.
        """
        resolver = self._create_resolver({"10961": ["Kreuzberg"]})
        self.scraper.set_borough_resolver(resolver)

        html = """
        <div class="ad-listitem">
            <article class="aditem" data-adid="2851234567" 
                     data-href="/s-anzeige/altbau-wohnung-kreuzberg-nahe-bergmannstrasse/2851234567">
                <div class="aditem-main">
                    <div class="aditem-main--top">
                        <div class="aditem-main--top--left">
                            10961 Berlin Kreuzberg (3 km)
                        </div>
                        <div class="aditem-main--top--right">
                            Gestern, 18:45
                        </div>
                    </div>
                    <div class="aditem-main--middle">
                        <h2 class="text-module-begin">
                            Altbau-Wohnung Kreuzberg nahe Bergmannstraße
                        </h2>
                        <div class="aditem-main--middle--tags">
                            72,50 m² | 2 Zi.
                        </div>
                        <p class="aditem-main--middle--price-shipping--price">
                            1.180 €
                        </p>
                    </div>
                </div>
            </article>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        listing = self.scraper._parse_listing(listing_soup)

        self.assertIsNotNone(listing)
        self.assertEqual(listing.address, "10961 Berlin Kreuzberg")
        self.assertEqual(listing.borough, "Kreuzberg")
        self.assertEqual(listing.sqm, "72.50")
        self.assertEqual(listing.rooms, "2")
        self.assertEqual(listing.price_cold, "1180")

    def test_parse_realistic_prenzlauer_berg_listing(self):
        """
        Test parsing a realistic listing from Prenzlauer Berg.
        
        Simulates a larger family apartment.
        """
        resolver = self._create_resolver({"10405": ["Prenzlauer Berg"]})
        self.scraper.set_borough_resolver(resolver)

        html = """
        <div class="ad-listitem">
            <article class="aditem" data-adid="2859876543" 
                     data-href="/s-anzeige/grosse-familienwohnung-prenzlauer-berg/2859876543">
                <div class="aditem-main">
                    <div class="aditem-main--top">
                        <div class="aditem-main--top--left">
                            10405 Berlin Prenzlauer Berg
                        </div>
                        <div class="aditem-main--top--right">
                            22.01.2026
                        </div>
                    </div>
                    <div class="aditem-main--middle">
                        <h2 class="text-module-begin">
                            Große Familienwohnung Prenzlauer Berg
                        </h2>
                        <div class="aditem-main--middle--tags">
                            138,01 m² | 5 Zi.
                        </div>
                        <p class="aditem-main--middle--price-shipping--price">
                            2.350 €
                        </p>
                    </div>
                </div>
            </article>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        listing = self.scraper._parse_listing(listing_soup)

        self.assertIsNotNone(listing)
        self.assertEqual(listing.address, "10405 Berlin Prenzlauer Berg")
        self.assertEqual(listing.borough, "Prenzlauer Berg")
        self.assertEqual(listing.sqm, "138.01")
        self.assertEqual(listing.rooms, "5")
        self.assertEqual(listing.price_cold, "2350")

    def test_parse_listing_with_negotiable_price(self):
        """
        Test parsing a listing with VB (Verhandlungsbasis) price.
        
        VB indicates the price is negotiable and should be stripped.
        """
        resolver = self._create_resolver({"12043": ["Neukölln"]})
        self.scraper.set_borough_resolver(resolver)

        html = """
        <div class="ad-listitem">
            <article class="aditem" data-adid="2861111111" 
                     data-href="/s-anzeige/wohnung-neukoelln-vb/2861111111">
                <div class="aditem-main">
                    <div class="aditem-main--top">
                        <div class="aditem-main--top--left">
                            12043 Berlin Neukölln (5 km)
                        </div>
                    </div>
                    <div class="aditem-main--middle">
                        <div class="aditem-main--middle--tags">
                            55 m² | 2 Zi.
                        </div>
                        <p class="aditem-main--middle--price-shipping--price">
                            950 € VB
                        </p>
                    </div>
                </div>
            </article>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        listing = self.scraper._parse_listing(listing_soup)

        self.assertIsNotNone(listing)
        self.assertEqual(listing.address, "12043 Berlin Neukölln")
        self.assertEqual(listing.borough, "Neukölln")
        self.assertEqual(listing.price_cold, "950")

    def test_parse_listing_studio_apartment(self):
        """
        Test parsing a studio apartment (1 room).
        
        Some listings don't specify room count for studios.
        """
        resolver = self._create_resolver({"10117": ["Mitte"]})
        self.scraper.set_borough_resolver(resolver)

        html = """
        <div class="ad-listitem">
            <article class="aditem" data-adid="2862222222" 
                     data-href="/s-anzeige/studio-apartment-berlin-mitte/2862222222">
                <div class="aditem-main">
                    <div class="aditem-main--top">
                        <div class="aditem-main--top--left">
                            10117 Berlin Mitte
                        </div>
                    </div>
                    <div class="aditem-main--middle">
                        <div class="aditem-main--middle--tags">
                            28 m²
                        </div>
                        <p class="aditem-main--middle--price-shipping--price">
                            650 €
                        </p>
                    </div>
                </div>
            </article>
        </div>
        """
        soup = BeautifulSoup(html, "lxml")
        listing_soup = soup.find("div", class_="ad-listitem")

        listing = self.scraper._parse_listing(listing_soup)

        self.assertIsNotNone(listing)
        self.assertEqual(listing.sqm, "28")
        self.assertEqual(listing.rooms, "1")  # Defaults to 1 when not specified
        self.assertEqual(listing.price_cold, "650")

    @patch("src.scrapers.kleinanzeigen.requests.Session")
    def test_parse_multiple_listings_page(self, mock_session_class):
        """
        Test parsing a page with multiple listings.
        
        Simulates the full page structure with multiple ad-listitems.
        """
        resolver = self._create_resolver({
            "10115": ["Mitte"],
            "10961": ["Kreuzberg"],
            "10405": ["Prenzlauer Berg"],
        })
        self.scraper.set_borough_resolver(resolver)

        html_content = """
        <html><body>
        <ul id="srchrslt-adtable">
            <li class="ad-listitem">
                <article class="aditem" data-adid="1111" 
                         data-href="/s-anzeige/wohnung-mitte/1111">
                    <div class="aditem-main">
                        <div class="aditem-main--top">
                            <div class="aditem-main--top--left">10115 Berlin</div>
                        </div>
                        <div class="aditem-main--middle">
                            <div class="aditem-main--middle--tags">60 m² | 2 Zi.</div>
                            <p class="aditem-main--middle--price-shipping--price">1.000 €</p>
                        </div>
                    </div>
                </article>
            </li>
            <li class="ad-listitem">
                <!-- Ad spacer - should be filtered -->
            </li>
            <li class="ad-listitem">
                <article class="aditem" data-adid="2222" 
                         data-href="/s-anzeige/wohnung-kreuzberg/2222">
                    <div class="aditem-main">
                        <div class="aditem-main--top">
                            <div class="aditem-main--top--left">10961 Berlin</div>
                        </div>
                        <div class="aditem-main--middle">
                            <div class="aditem-main--middle--tags">75 m² | 3 Zi.</div>
                            <p class="aditem-main--middle--price-shipping--price">1.200 €</p>
                        </div>
                    </div>
                </article>
            </li>
            <li class="ad-listitem">
                <article class="aditem" data-adid="3333" 
                         data-href="/s-anzeige/wohnung-prenzlauer-berg/3333">
                    <div class="aditem-main">
                        <div class="aditem-main--top">
                            <div class="aditem-main--top--left">10405 Berlin</div>
                        </div>
                        <div class="aditem-main--middle">
                            <div class="aditem-main--middle--tags">90 m² | 4 Zi.</div>
                            <p class="aditem-main--middle--price-shipping--price">1.600 €</p>
                        </div>
                    </div>
                </article>
            </li>
        </ul>
        </body></html>
        """
        mock_session = Mock()
        mock_response = Mock()
        mock_response.text = html_content
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        listings, _ = self.scraper.get_current_listings()

        self.assertEqual(len(listings), 3)

        # Verify Mitte listing
        mitte = listings["https://www.kleinanzeigen.de/s-anzeige/wohnung-mitte/1111"]
        self.assertEqual(mitte.borough, "Mitte")
        self.assertEqual(mitte.rooms, "2")
        self.assertEqual(mitte.price_cold, "1000")

        # Verify Kreuzberg listing
        kreuzberg = listings[
            "https://www.kleinanzeigen.de/s-anzeige/wohnung-kreuzberg/2222"
        ]
        self.assertEqual(kreuzberg.borough, "Kreuzberg")
        self.assertEqual(kreuzberg.rooms, "3")
        self.assertEqual(kreuzberg.price_cold, "1200")

        # Verify Prenzlauer Berg listing
        pberg = listings[
            "https://www.kleinanzeigen.de/s-anzeige/wohnung-prenzlauer-berg/3333"
        ]
        self.assertEqual(pberg.borough, "Prenzlauer Berg")
        self.assertEqual(pberg.rooms, "4")
        self.assertEqual(pberg.price_cold, "1600")


if __name__ == "__main__":
    unittest.main()
