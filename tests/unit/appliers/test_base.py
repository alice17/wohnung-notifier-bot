"""
Unit tests for the BaseApplier class and related types.
"""
import unittest
from typing import Dict, Any, List

from src.appliers.base import BaseApplier, ApplyResult, ApplyStatus
from src.core.listing import Listing


class ConcreteApplier(BaseApplier):
    """Concrete implementation of BaseApplier for testing."""

    @property
    def name(self) -> str:
        """Return the applier name."""
        return "TestApplier"

    @property
    def url_patterns(self) -> List[str]:
        """Return URL patterns this applier handles."""
        return ["https://test.example.com/", "https://other.test.com/"]

    def apply(self, listing: Listing) -> ApplyResult:
        """Dummy implementation for testing."""
        return ApplyResult(
            status=ApplyStatus.SUCCESS,
            message="Test application submitted"
        )


class TestApplyStatus(unittest.TestCase):
    """Test suite for ApplyStatus enum."""

    def test_status_values_exist(self):
        """Tests that all expected status values exist."""
        self.assertEqual(ApplyStatus.SUCCESS.value, "success")
        self.assertEqual(ApplyStatus.FAILED.value, "failed")
        self.assertEqual(ApplyStatus.SKIPPED.value, "skipped")
        self.assertEqual(ApplyStatus.FORM_NOT_FOUND.value, "form_not_found")
        self.assertEqual(ApplyStatus.MISSING_CONFIG.value, "missing_config")


class TestApplyResult(unittest.TestCase):
    """Test suite for ApplyResult dataclass."""

    def test_create_success_result(self):
        """Tests creating a successful ApplyResult."""
        result = ApplyResult(
            status=ApplyStatus.SUCCESS,
            message="Application submitted successfully"
        )
        self.assertEqual(result.status, ApplyStatus.SUCCESS)
        self.assertEqual(result.message, "Application submitted successfully")
        self.assertIsNone(result.applicant_data)

    def test_create_result_with_applicant_data(self):
        """Tests creating ApplyResult with applicant data."""
        applicant_data = {
            "Name": "Test User",
            "Email": "test@example.com"
        }
        result = ApplyResult(
            status=ApplyStatus.SUCCESS,
            message="Success",
            applicant_data=applicant_data
        )
        self.assertEqual(result.applicant_data, applicant_data)

    def test_is_success_returns_true_for_success(self):
        """Tests that is_success returns True for SUCCESS status."""
        result = ApplyResult(status=ApplyStatus.SUCCESS, message="OK")
        self.assertTrue(result.is_success)

    def test_is_success_returns_false_for_failed(self):
        """Tests that is_success returns False for FAILED status."""
        result = ApplyResult(status=ApplyStatus.FAILED, message="Error")
        self.assertFalse(result.is_success)

    def test_is_success_returns_false_for_other_statuses(self):
        """Tests that is_success returns False for non-SUCCESS statuses."""
        for status in [
            ApplyStatus.SKIPPED,
            ApplyStatus.FORM_NOT_FOUND,
            ApplyStatus.MISSING_CONFIG
        ]:
            result = ApplyResult(status=status, message="Test")
            self.assertFalse(result.is_success, f"is_success should be False for {status}")


class TestBaseApplier(unittest.TestCase):
    """Test suite for BaseApplier abstract class."""

    def setUp(self):
        """Set up common test fixtures."""
        self.config = {
            "name": "Test",
            "email": "test@example.com"
        }
        self.applier = ConcreteApplier(self.config)

    def test_initialization_stores_config(self):
        """Tests that initialization stores the configuration."""
        self.assertEqual(self.applier.config, self.config)

    def test_name_property(self):
        """Tests that the name property returns correct value."""
        self.assertEqual(self.applier.name, "TestApplier")

    def test_url_patterns_property(self):
        """Tests that url_patterns property returns correct patterns."""
        patterns = self.applier.url_patterns
        self.assertEqual(len(patterns), 2)
        self.assertIn("https://test.example.com/", patterns)
        self.assertIn("https://other.test.com/", patterns)

    def test_can_apply_returns_true_for_matching_url(self):
        """Tests can_apply returns True for URLs matching patterns."""
        listing = Listing(
            source="test",
            link="https://test.example.com/listing/123"
        )
        self.assertTrue(self.applier.can_apply(listing))

    def test_can_apply_returns_true_for_alternative_pattern(self):
        """Tests can_apply matches any of the URL patterns."""
        listing = Listing(
            source="test",
            link="https://other.test.com/apartment/456"
        )
        self.assertTrue(self.applier.can_apply(listing))

    def test_can_apply_returns_false_for_non_matching_url(self):
        """Tests can_apply returns False for non-matching URLs."""
        listing = Listing(
            source="test",
            link="https://different-site.com/listing/123"
        )
        self.assertFalse(self.applier.can_apply(listing))

    def test_can_apply_returns_false_for_empty_link(self):
        """Tests can_apply returns False for empty link."""
        listing = Listing(source="test", link="")
        self.assertFalse(self.applier.can_apply(listing))

    def test_can_apply_returns_false_for_na_link(self):
        """Tests can_apply returns False for N/A link."""
        listing = Listing(source="test", link="N/A")
        self.assertFalse(self.applier.can_apply(listing))

    def test_is_configured_returns_true_with_config(self):
        """Tests is_configured returns True when config is present."""
        self.assertTrue(self.applier.is_configured())

    def test_is_configured_returns_false_with_empty_config(self):
        """Tests is_configured returns False for empty config."""
        empty_applier = ConcreteApplier({})
        self.assertFalse(empty_applier.is_configured())

    def test_is_configured_returns_false_with_none_config(self):
        """Tests is_configured returns False for None config."""
        none_applier = ConcreteApplier(None)
        self.assertFalse(none_applier.is_configured())

    def test_apply_method_can_be_called(self):
        """Tests that apply method can be called on concrete implementation."""
        listing = Listing(
            source="test",
            link="https://test.example.com/listing/123"
        )
        result = self.applier.apply(listing)
        
        self.assertIsInstance(result, ApplyResult)
        self.assertEqual(result.status, ApplyStatus.SUCCESS)


if __name__ == '__main__':
    unittest.main()


