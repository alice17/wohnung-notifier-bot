"""
Unit tests for the ListingFilter class.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from src.core.config import Config
from src.services.filter import ListingFilter
from src.core.listing import Listing
from src.services.borough_resolver import BoroughResolver


class TestListingFilter(unittest.TestCase):
    """Test suite for ListingFilter class."""

    def setUp(self):
        """Sets up common test fixtures."""
        self.maxDiff = None
        
        # Create a temporary mapping file for BoroughResolver
        self.test_mapping = {
            "10115": ["Mitte"],
            "10179": ["Mitte"],
            "10243": ["Friedrichshain"]
        }
        self.temp_file = tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        )
        json.dump(self.test_mapping, self.temp_file)
        self.temp_file.close()

    def tearDown(self):
        """Clean up temporary file."""
        Path(self.temp_file.name).unlink(missing_ok=True)

    def _create_resolver(self, mapping: dict = None) -> BoroughResolver:
        """Creates a BoroughResolver with specified mapping."""
        if mapping is None:
            return BoroughResolver(self.temp_file.name)
        
        temp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(mapping, temp)
        temp.close()
        resolver = BoroughResolver(temp.name)
        Path(temp.name).unlink(missing_ok=True)
        return resolver

    def test_to_numeric_standard_format(self):
        """
        Test _to_numeric with standard format numbers (period as decimal).
        
        All scrapers now normalize their numbers to standard format before
        passing to the filter, so the filter only needs to handle this format.
        """
        self.assertEqual(ListingFilter._to_numeric('555.02'), 555.02)
        self.assertEqual(ListingFilter._to_numeric('1234.56'), 1234.56)
        self.assertEqual(ListingFilter._to_numeric('850.0'), 850.0)
        self.assertEqual(ListingFilter._to_numeric('2345'), 2345.0)
        self.assertEqual(ListingFilter._to_numeric('1800'), 1800.0)

    def test_to_numeric_simple_numbers(self):
        """Test _to_numeric with simple numbers without separators."""
        self.assertEqual(ListingFilter._to_numeric('850'), 850.0)
        self.assertEqual(ListingFilter._to_numeric('1234'), 1234.0)

    def test_to_numeric_invalid_values(self):
        """Test _to_numeric with invalid or special values."""
        self.assertIsNone(ListingFilter._to_numeric('N/A'))
        self.assertIsNone(ListingFilter._to_numeric(''))
        self.assertIsNone(ListingFilter._to_numeric('abc'))
        self.assertIsNone(ListingFilter._to_numeric(None))

    def test_to_numeric_regression_price_parsing(self):
        """
        Regression test for price parsing.
        
        Ensures that standard format prices are correctly parsed.
        All scrapers normalize to this format before filtering.
        """
        result = ListingFilter._to_numeric('555.02')
        self.assertEqual(result, 555.02)
        
        self.assertEqual(ListingFilter._to_numeric('2345'), 2345.0)
        self.assertEqual(ListingFilter._to_numeric('1800'), 1800.0)
        
        self.assertLess(555.02, 1200, "555.02 should be less than max 1200")
        self.assertGreater(2345, 1200, "2345 should be greater than max 1200")

    def _create_config(self, filters_config: dict) -> Config:
        """Creates a Config object with specified filters."""
        config_data = {
            "telegram": {"bot_token": "token", "chat_id": "123"},
            "scrapers": {},
            "filters": filters_config
        }
        return Config(config_data)

    def _create_listing(self, **kwargs) -> Listing:
        """Creates a Listing object with default or specified values."""
        defaults = {
            "source": "test_source",
            "address": "Teststrasse 1, 10115 Berlin",
            "borough": "N/A",
            "sqm": "50.0",
            "price_cold": "800.00",
            "price_total": "1000.00",
            "rooms": "2.0",
            "wbs": "N/A",
            "link": "https://example.com/listing",
            "identifier": "test-123"
        }
        defaults.update(kwargs)
        return Listing(**defaults)

    # Tests for initialization

    def test_initialization_with_filters_enabled(self):
        """Tests ListingFilter initialization with filters enabled."""
        config = self._create_config({"enabled": True})
        resolver = self._create_resolver()
        listing_filter = ListingFilter(config, resolver)

        self.assertEqual(listing_filter.filters, {"enabled": True})
        self.assertIsNotNone(listing_filter.borough_resolver)

    def test_initialization_with_no_resolver(self):
        """Tests ListingFilter initialization without resolver."""
        config = self._create_config({"enabled": False})
        listing_filter = ListingFilter(config, None)

        self.assertIsNone(listing_filter.borough_resolver)

    # Tests for is_filtered method

    def test_is_filtered_when_filters_disabled(self):
        """Tests that no listings are filtered when filters are disabled."""
        config = self._create_config({"enabled": False})
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing()

        self.assertFalse(listing_filter.is_filtered(listing))

    def test_is_filtered_when_filters_not_present(self):
        """Tests that no listings are filtered when filters are not present."""
        config = self._create_config({})
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing()

        self.assertFalse(listing_filter.is_filtered(listing))

    def test_is_filtered_all_checks_pass(self):
        """Tests that listing passes when all filter checks pass."""
        config = self._create_config({
            "enabled": True,
            "properties": {
                "price_total": {"min": 500, "max": 1500},
                "sqm": {"min": 30, "max": 100},
                "rooms": {"min": 1, "max": 3}
            }
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(
            price_total="1000.00",
            price_cold="800.00",
            sqm="50.0",
            rooms="2.0"
        )

        self.assertFalse(listing_filter.is_filtered(listing))

    def test_is_filtered_fails_price_check(self):
        """Tests that listing is filtered when price check fails."""
        config = self._create_config({
            "enabled": True,
            "properties": {
                "price_total": {"max": 500}
            }
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(price_total="1000.00")

        self.assertTrue(listing_filter.is_filtered(listing))

    def test_is_filtered_fails_sqm_check(self):
        """Tests that listing is filtered when sqm check fails."""
        config = self._create_config({
            "enabled": True,
            "properties": {
                "sqm": {"min": 60}
            }
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(sqm="50.0")

        self.assertTrue(listing_filter.is_filtered(listing))

    def test_is_filtered_fails_rooms_check(self):
        """Tests that listing is filtered when rooms check fails."""
        config = self._create_config({
            "enabled": True,
            "properties": {
                "rooms": {"max": 1}
            }
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(rooms="2.0")

        self.assertTrue(listing_filter.is_filtered(listing))

    def test_is_filtered_fails_wbs_check(self):
        """Tests that listing is filtered when WBS check fails."""
        config = self._create_config({
            "enabled": True,
            "properties": {
                "wbs": {"allowed_values": ["required"]}
            }
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(wbs="N/A")

        self.assertTrue(listing_filter.is_filtered(listing))

    def test_is_filtered_fails_borough_check(self):
        """Tests that listing is filtered when borough check fails."""
        config = self._create_config({
            "enabled": True,
            "properties": {
                "boroughs": {"allowed_values": ["Charlottenburg"]}
            }
        })
        resolver = self._create_resolver({"10115": ["Mitte"]})
        listing_filter = ListingFilter(config, resolver)
        listing = self._create_listing(address="Teststrasse 1, 10115 Berlin")

        self.assertTrue(listing_filter.is_filtered(listing))

    # Tests for _passes_numeric_filter

    def test_passes_numeric_filter_no_rules(self):
        """Tests numeric filter passes when no rules are specified."""
        config = self._create_config({"enabled": True})
        listing_filter = ListingFilter(config, None)

        self.assertTrue(listing_filter._passes_numeric_filter(100.0, {}))

    def test_passes_numeric_filter_value_none(self):
        """Tests numeric filter passes when value is None."""
        config = self._create_config({"enabled": True})
        listing_filter = ListingFilter(config, None)

        self.assertTrue(listing_filter._passes_numeric_filter(None, {"min": 50}))

    def test_passes_numeric_filter_min_boundary(self):
        """Tests numeric filter with minimum boundary."""
        config = self._create_config({"enabled": True})
        listing_filter = ListingFilter(config, None)

        self.assertTrue(listing_filter._passes_numeric_filter(50.0, {"min": 50}))
        self.assertFalse(listing_filter._passes_numeric_filter(49.9, {"min": 50}))

    def test_passes_numeric_filter_max_boundary(self):
        """Tests numeric filter with maximum boundary."""
        config = self._create_config({"enabled": True})
        listing_filter = ListingFilter(config, None)

        self.assertTrue(listing_filter._passes_numeric_filter(100.0, {"max": 100}))
        self.assertFalse(listing_filter._passes_numeric_filter(100.1, {"max": 100}))

    def test_passes_numeric_filter_min_and_max(self):
        """Tests numeric filter with both minimum and maximum."""
        config = self._create_config({"enabled": True})
        listing_filter = ListingFilter(config, None)

        self.assertTrue(listing_filter._passes_numeric_filter(75.0, {"min": 50, "max": 100}))
        self.assertFalse(listing_filter._passes_numeric_filter(40.0, {"min": 50, "max": 100}))
        self.assertFalse(listing_filter._passes_numeric_filter(110.0, {"min": 50, "max": 100}))

    # Tests for _is_filtered_by_price

    def test_is_filtered_by_price_warm_rent_within_range(self):
        """Tests price filtering with warm rent within range."""
        config = self._create_config({
            "enabled": True,
            "properties": {"price_total": {"min": 500, "max": 1500}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(price_total="1000.00")

        self.assertFalse(listing_filter._is_filtered_by_price(listing))

    def test_is_filtered_by_price_warm_rent_above_max(self):
        """Tests price filtering with warm rent above maximum."""
        config = self._create_config({
            "enabled": True,
            "properties": {"price_total": {"max": 1200}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(price_total="1500.00")

        self.assertTrue(listing_filter._is_filtered_by_price(listing))

    def test_is_filtered_by_price_warm_rent_below_min(self):
        """Tests price filtering with warm rent below minimum."""
        config = self._create_config({
            "enabled": True,
            "properties": {"price_total": {"min": 800}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(price_total="500.00")

        self.assertTrue(listing_filter._is_filtered_by_price(listing))

    def test_is_filtered_by_price_falls_back_to_cold_rent(self):
        """Tests price filtering falls back to cold rent when warm is N/A."""
        config = self._create_config({
            "enabled": True,
            "properties": {"price_total": {"max": 800}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(price_total="N/A", price_cold="700.00")

        self.assertFalse(listing_filter._is_filtered_by_price(listing))

    def test_is_filtered_by_price_cold_rent_exceeds_max(self):
        """Tests price filtering with cold rent exceeding maximum."""
        config = self._create_config({
            "enabled": True,
            "properties": {"price_total": {"max": 600}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(price_total="N/A", price_cold="700.00")

        self.assertTrue(listing_filter._is_filtered_by_price(listing))

    def test_is_filtered_by_price_both_prices_na(self):
        """Tests price filtering when both prices are N/A."""
        config = self._create_config({
            "enabled": True,
            "properties": {"price_total": {"max": 1000}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(price_total="N/A", price_cold="N/A")

        self.assertFalse(listing_filter._is_filtered_by_price(listing))

    def test_is_filtered_by_price_regression_high_prices(self):
        """Regression test for price filtering with high values."""
        config = self._create_config({
            "enabled": True,
            "properties": {"price_total": {"max": 1200}}
        })
        listing_filter = ListingFilter(config, None)
        
        listing1 = self._create_listing(price_total="2825", price_cold="2345")
        self.assertTrue(listing_filter._is_filtered_by_price(listing1))
        
        listing2 = self._create_listing(price_total="1800", price_cold="N/A")
        self.assertTrue(listing_filter._is_filtered_by_price(listing2))
        
        listing3 = self._create_listing(price_total="1150", price_cold="N/A")
        self.assertFalse(listing_filter._is_filtered_by_price(listing3))

    # Tests for _is_filtered_by_sqm

    def test_is_filtered_by_sqm_within_range(self):
        """Tests sqm filtering with value within range."""
        config = self._create_config({
            "enabled": True,
            "properties": {"sqm": {"min": 40, "max": 80}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(sqm="50.0")

        self.assertFalse(listing_filter._is_filtered_by_sqm(listing))

    def test_is_filtered_by_sqm_below_min(self):
        """Tests sqm filtering with value below minimum."""
        config = self._create_config({
            "enabled": True,
            "properties": {"sqm": {"min": 60}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(sqm="50.0")

        self.assertTrue(listing_filter._is_filtered_by_sqm(listing))

    def test_is_filtered_by_sqm_above_max(self):
        """Tests sqm filtering with value above maximum."""
        config = self._create_config({
            "enabled": True,
            "properties": {"sqm": {"max": 40}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(sqm="50.0")

        self.assertTrue(listing_filter._is_filtered_by_sqm(listing))

    def test_is_filtered_by_sqm_na_value(self):
        """Tests sqm filtering with N/A value."""
        config = self._create_config({
            "enabled": True,
            "properties": {"sqm": {"min": 40}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(sqm="N/A")

        self.assertFalse(listing_filter._is_filtered_by_sqm(listing))

    # Tests for _is_filtered_by_rooms

    def test_is_filtered_by_rooms_within_range(self):
        """Tests rooms filtering with value within range."""
        config = self._create_config({
            "enabled": True,
            "properties": {"rooms": {"min": 1, "max": 3}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(rooms="2.0")

        self.assertFalse(listing_filter._is_filtered_by_rooms(listing))

    def test_is_filtered_by_rooms_below_min(self):
        """Tests rooms filtering with value below minimum."""
        config = self._create_config({
            "enabled": True,
            "properties": {"rooms": {"min": 3}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(rooms="2.0")

        self.assertTrue(listing_filter._is_filtered_by_rooms(listing))

    def test_is_filtered_by_rooms_above_max(self):
        """Tests rooms filtering with value above maximum."""
        config = self._create_config({
            "enabled": True,
            "properties": {"rooms": {"max": 1}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(rooms="2.0")

        self.assertTrue(listing_filter._is_filtered_by_rooms(listing))

    def test_is_filtered_by_rooms_na_value(self):
        """Tests rooms filtering with N/A value."""
        config = self._create_config({
            "enabled": True,
            "properties": {"rooms": {"min": 2}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(rooms="N/A")

        self.assertFalse(listing_filter._is_filtered_by_rooms(listing))

    # Tests for _is_filtered_by_wbs

    def test_is_filtered_by_wbs_no_allowed_values(self):
        """Tests WBS filtering when no allowed values specified."""
        config = self._create_config({
            "enabled": True,
            "properties": {"wbs": {}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(wbs="N/A")

        self.assertFalse(listing_filter._is_filtered_by_wbs(listing))

    def test_is_filtered_by_wbs_value_allowed(self):
        """Tests WBS filtering with allowed value."""
        config = self._create_config({
            "enabled": True,
            "properties": {"wbs": {"allowed_values": ["required", "N/A"]}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(wbs="N/A")

        self.assertFalse(listing_filter._is_filtered_by_wbs(listing))

    def test_is_filtered_by_wbs_value_not_allowed(self):
        """Tests WBS filtering with value not in allowed list."""
        config = self._create_config({
            "enabled": True,
            "properties": {"wbs": {"allowed_values": ["required"]}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(wbs="N/A")

        self.assertTrue(listing_filter._is_filtered_by_wbs(listing))

    def test_is_filtered_by_wbs_case_insensitive(self):
        """Tests WBS filtering is case insensitive."""
        config = self._create_config({
            "enabled": True,
            "properties": {"wbs": {"allowed_values": ["REQUIRED"]}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(wbs="required")

        self.assertFalse(listing_filter._is_filtered_by_wbs(listing))

    def test_is_filtered_by_wbs_with_whitespace(self):
        """Tests WBS filtering handles whitespace correctly."""
        config = self._create_config({
            "enabled": True,
            "properties": {"wbs": {"allowed_values": ["required"]}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(wbs="  required  ")

        self.assertFalse(listing_filter._is_filtered_by_wbs(listing))

    # Tests for _is_filtered_by_borough

    def test_is_filtered_by_borough_no_allowed_values(self):
        """Tests borough filtering when no allowed values specified."""
        config = self._create_config({
            "enabled": True,
            "properties": {"boroughs": {}}
        })
        resolver = self._create_resolver({"10115": ["Mitte"]})
        listing_filter = ListingFilter(config, resolver)
        listing = self._create_listing(address="Teststrasse 1, 10115 Berlin")

        self.assertFalse(listing_filter._is_filtered_by_borough(listing))

    def test_is_filtered_by_borough_value_allowed(self):
        """Tests borough filtering with allowed borough."""
        config = self._create_config({
            "enabled": True,
            "properties": {"boroughs": {"allowed_values": ["Mitte"]}}
        })
        resolver = self._create_resolver({"10115": ["Mitte"]})
        listing_filter = ListingFilter(config, resolver)
        listing = self._create_listing(address="Teststrasse 1, 10115 Berlin")

        self.assertFalse(listing_filter._is_filtered_by_borough(listing))

    def test_is_filtered_by_borough_value_not_allowed(self):
        """Tests borough filtering with borough not in allowed list."""
        config = self._create_config({
            "enabled": True,
            "properties": {"boroughs": {"allowed_values": ["Charlottenburg"]}}
        })
        resolver = self._create_resolver({"10115": ["Mitte"]})
        listing_filter = ListingFilter(config, resolver)
        listing = self._create_listing(address="Teststrasse 1, 10115 Berlin")

        self.assertTrue(listing_filter._is_filtered_by_borough(listing))

    def test_is_filtered_by_borough_case_insensitive(self):
        """Tests borough filtering is case insensitive."""
        config = self._create_config({
            "enabled": True,
            "properties": {"boroughs": {"allowed_values": ["MITTE"]}}
        })
        resolver = self._create_resolver({"10115": ["Mitte"]})
        listing_filter = ListingFilter(config, resolver)
        listing = self._create_listing(address="Teststrasse 1, 10115 Berlin")

        self.assertFalse(listing_filter._is_filtered_by_borough(listing))

    def test_is_filtered_by_borough_no_zipcode_in_address(self):
        """Tests borough filtering when no zipcode found in address."""
        config = self._create_config({
            "enabled": True,
            "properties": {"boroughs": {"allowed_values": ["Mitte"]}}
        })
        resolver = self._create_resolver({"10115": ["Mitte"]})
        listing_filter = ListingFilter(config, resolver)
        listing = self._create_listing(address="Teststrasse 1, Berlin")

        # Should not filter when borough cannot be determined
        self.assertFalse(listing_filter._is_filtered_by_borough(listing))

    def test_is_filtered_by_borough_zipcode_not_in_map(self):
        """Tests borough filtering when zipcode not found in map."""
        config = self._create_config({
            "enabled": True,
            "properties": {"boroughs": {"allowed_values": ["Mitte"]}}
        })
        resolver = self._create_resolver({"10115": ["Mitte"]})
        listing_filter = ListingFilter(config, resolver)
        listing = self._create_listing(address="Teststrasse 1, 99999 Berlin")

        # Should not filter when borough cannot be determined
        self.assertFalse(listing_filter._is_filtered_by_borough(listing))

    def test_is_filtered_by_borough_updates_listing_borough(self):
        """Tests that borough filtering updates the listing borough field."""
        config = self._create_config({
            "enabled": True,
            "properties": {"boroughs": {"allowed_values": ["Mitte"]}}
        })
        resolver = self._create_resolver({"10115": ["Mitte"]})
        listing_filter = ListingFilter(config, resolver)
        listing = self._create_listing(address="Teststrasse 1, 10115 Berlin")

        listing_filter._is_filtered_by_borough(listing)
        self.assertEqual(listing.borough, "Mitte")

    def test_is_filtered_by_borough_multiple_boroughs(self):
        """Tests borough filtering with multiple boroughs for same zipcode."""
        config = self._create_config({
            "enabled": True,
            "properties": {"boroughs": {"allowed_values": ["Mitte"]}}
        })
        resolver = self._create_resolver({"10115": ["Mitte", "Tiergarten"]})
        listing_filter = ListingFilter(config, resolver)
        listing = self._create_listing(address="Teststrasse 1, 10115 Berlin")

        self.assertFalse(listing_filter._is_filtered_by_borough(listing))
        self.assertEqual(listing.borough, "Mitte, Tiergarten")

    def test_is_filtered_by_borough_no_resolver(self):
        """Tests borough filtering when resolver is not available."""
        config = self._create_config({
            "enabled": True,
            "properties": {"boroughs": {"allowed_values": ["Mitte"]}}
        })
        listing_filter = ListingFilter(config, None)
        listing = self._create_listing(address="Teststrasse 1, 10115 Berlin")

        # Should not filter when resolver not available
        self.assertFalse(listing_filter._is_filtered_by_borough(listing))

    # Tests for _to_numeric

    def test_to_numeric_valid_integer(self):
        """Tests converting valid integer string to numeric."""
        result = ListingFilter._to_numeric("100")
        self.assertEqual(result, 100.0)

    def test_to_numeric_valid_float_with_decimal(self):
        """Tests converting float with period decimal separator."""
        result = ListingFilter._to_numeric("100.50")
        self.assertEqual(result, 100.5)
        
        result2 = ListingFilter._to_numeric("1234.56")
        self.assertEqual(result2, 1234.56)

    def test_to_numeric_large_values(self):
        """Tests converting large numeric values in standard format."""
        self.assertEqual(ListingFilter._to_numeric("2345"), 2345.0)
        self.assertEqual(ListingFilter._to_numeric("2825"), 2825.0)
        self.assertEqual(ListingFilter._to_numeric("1800"), 1800.0)
        self.assertEqual(ListingFilter._to_numeric("1200"), 1200.0)
        self.assertEqual(ListingFilter._to_numeric("999"), 999.0)
        
        self.assertEqual(ListingFilter._to_numeric("2345.67"), 2345.67)
        self.assertEqual(ListingFilter._to_numeric("1234.56"), 1234.56)

    def test_to_numeric_na_value(self):
        """Tests converting N/A string returns None."""
        result = ListingFilter._to_numeric("N/A")
        self.assertIsNone(result)

    def test_to_numeric_empty_string(self):
        """Tests converting empty string returns None."""
        result = ListingFilter._to_numeric("")
        self.assertIsNone(result)

    def test_to_numeric_invalid_value(self):
        """Tests converting invalid string returns None."""
        result = ListingFilter._to_numeric("not a number")
        self.assertIsNone(result)

    def test_to_numeric_none_value(self):
        """Tests converting None returns None."""
        result = ListingFilter._to_numeric(None)
        self.assertIsNone(result)

    def test_to_numeric_non_string_type(self):
        """Tests converting non-string type returns None."""
        result = ListingFilter._to_numeric(123)
        self.assertIsNone(result)

    def test_to_numeric_zero(self):
        """Tests converting zero string to numeric."""
        result = ListingFilter._to_numeric("0")
        self.assertEqual(result, 0.0)

    def test_to_numeric_negative_number(self):
        """Tests converting negative number string in standard format."""
        result = ListingFilter._to_numeric("-50.5")
        self.assertEqual(result, -50.5)


if __name__ == '__main__':
    unittest.main()
