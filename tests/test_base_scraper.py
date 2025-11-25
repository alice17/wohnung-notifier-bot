"""
Unit tests for the BaseScraper class.
"""
import unittest
from src.scrapers.base import BaseScraper
from src.listing import Listing
from typing import Dict, Optional


class ConcreteScraper(BaseScraper):
    """Concrete implementation of BaseScraper for testing."""

    def get_current_listings(
        self, known_listings: Optional[Dict[str, Listing]] = None
    ) -> Dict[str, Listing]:
        """Dummy implementation for testing."""
        return {}


class TestBaseScraper(unittest.TestCase):
    """Test suite for BaseScraper class."""

    def setUp(self):
        """Sets up common test fixtures."""
        self.scraper = ConcreteScraper("test_scraper")

    def test_normalize_german_number_thousands_only(self):
        """Tests normalizing German format with only thousands separator."""
        # German: 2.345 = 2345
        self.assertEqual(self.scraper._normalize_german_number("2.345"), "2345")
        self.assertEqual(self.scraper._normalize_german_number("1.800"), "1800")
        self.assertEqual(self.scraper._normalize_german_number("1.200"), "1200")

    def test_normalize_german_number_thousands_and_decimal(self):
        """Tests normalizing German format with thousands and decimal separators."""
        # German: 1.234,56 = 1234.56
        self.assertEqual(self.scraper._normalize_german_number("1.234,56"), "1234.56")
        self.assertEqual(self.scraper._normalize_german_number("2.345,67"), "2345.67")
        self.assertEqual(self.scraper._normalize_german_number("10.000,00"), "10000.00")

    def test_normalize_german_number_decimal_only(self):
        """Tests normalizing German format with only decimal separator."""
        # German: 123,45 = 123.45
        self.assertEqual(self.scraper._normalize_german_number("123,45"), "123.45")
        self.assertEqual(self.scraper._normalize_german_number("99,99"), "99.99")
        self.assertEqual(self.scraper._normalize_german_number("1000,50"), "1000.50")

    def test_normalize_german_number_no_separators(self):
        """Tests normalizing German format with no separators."""
        # Simple integers should pass through unchanged
        self.assertEqual(self.scraper._normalize_german_number("1234"), "1234")
        self.assertEqual(self.scraper._normalize_german_number("999"), "999")
        self.assertEqual(self.scraper._normalize_german_number("500"), "500")

    def test_normalize_german_number_special_values(self):
        """Tests normalizing special values."""
        self.assertEqual(self.scraper._normalize_german_number("N/A"), "N/A")
        self.assertEqual(self.scraper._normalize_german_number(""), "")
        self.assertIsNone(self.scraper._normalize_german_number(None))

    def test_normalize_german_number_edge_cases(self):
        """Tests edge cases for German number normalization."""
        # Large numbers
        self.assertEqual(
            self.scraper._normalize_german_number("100.000,00"), "100000.00"
        )
        self.assertEqual(
            self.scraper._normalize_german_number("1.000.000,50"), "1000000.50"
        )

        # Small decimals
        self.assertEqual(self.scraper._normalize_german_number("0,99"), "0.99")
        self.assertEqual(self.scraper._normalize_german_number("0,01"), "0.01")

    def test_get_borough_from_zip(self):
        """Tests borough lookup from zip code."""
        zip_map = {
            "10115": ["Mitte"],
            "10961": ["Kreuzberg"],
            "10115-10119": ["Mitte", "Prenzlauer Berg"]
        }
        self.scraper.set_zip_to_borough_map(zip_map)

        # Exact match
        self.assertEqual(self.scraper._get_borough_from_zip("10115"), "Mitte")
        self.assertEqual(self.scraper._get_borough_from_zip("10961"), "Kreuzberg")

        # No match
        self.assertEqual(self.scraper._get_borough_from_zip("99999"), "N/A")

        # No map set
        scraper_no_map = ConcreteScraper("test")
        self.assertEqual(scraper_no_map._get_borough_from_zip("10115"), "N/A")


if __name__ == '__main__':
    unittest.main()

