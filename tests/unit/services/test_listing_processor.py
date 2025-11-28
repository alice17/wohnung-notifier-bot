"""
Tests for the ListingProcessor class.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch

from src.core.listing import Listing
from src.services.listing_processor import ListingProcessor


def create_test_listing(
    identifier: str = "test-123",
    address: str = "Test Street 1",
    link: str = "https://example.com/listing/123",
) -> Listing:
    """Create a test listing with default values."""
    return Listing(
        identifier=identifier,
        source="test",
        address=address,
        sqm="50",
        rooms="2",
        price_cold="500",
        price_total="600",
        wbs="Nein",
        borough="Mitte",
        link=link,
    )


class TestListingProcessorInit:
    """Tests for ListingProcessor initialization."""

    def test_init_with_notifier_only(self):
        """Test initialization with only notifier."""
        notifier = Mock()
        processor = ListingProcessor(notifier=notifier)

        assert processor._notifier == notifier
        assert processor._filter is None
        assert processor._appliers == []

    def test_init_with_all_components(self):
        """Test initialization with all components."""
        notifier = Mock()
        listing_filter = Mock()
        appliers = [Mock(), Mock()]

        processor = ListingProcessor(
            notifier=notifier,
            listing_filter=listing_filter,
            appliers=appliers,
        )

        assert processor._notifier == notifier
        assert processor._filter == listing_filter
        assert len(processor._appliers) == 2


class TestProcessNewListings:
    """Tests for process_new_listings method."""

    def test_returns_zero_for_empty_dict(self):
        """Test that empty input returns 0."""
        notifier = Mock()
        processor = ListingProcessor(notifier=notifier)

        result = processor.process_new_listings({})

        assert result == 0
        notifier.send_message.assert_not_called()

    @patch("src.services.listing_processor.time.sleep")
    def test_processes_all_listings(self, mock_sleep):
        """Test that all listings are processed."""
        notifier = Mock()
        notifier.format_listing_message.return_value = "Test message"
        processor = ListingProcessor(notifier=notifier)

        listings = {
            "1": create_test_listing(identifier="1"),
            "2": create_test_listing(identifier="2"),
            "3": create_test_listing(identifier="3"),
        }

        result = processor.process_new_listings(listings)

        assert result == 3
        assert notifier.send_message.call_count == 3

    @patch("src.services.listing_processor.time.sleep")
    def test_sleeps_between_notifications(self, mock_sleep):
        """Test that sleep is called between notifications."""
        notifier = Mock()
        notifier.format_listing_message.return_value = "Test message"
        processor = ListingProcessor(notifier=notifier)

        listings = {
            "1": create_test_listing(identifier="1"),
            "2": create_test_listing(identifier="2"),
        }

        processor.process_new_listings(listings)

        assert mock_sleep.call_count == 2


class TestFilteredListings:
    """Tests for filtering behavior."""

    @patch("src.services.listing_processor.time.sleep")
    def test_filtered_listings_are_not_notified(self, mock_sleep):
        """Test that filtered listings are skipped."""
        notifier = Mock()
        listing_filter = Mock()
        listing_filter.is_filtered.return_value = True

        processor = ListingProcessor(
            notifier=notifier, listing_filter=listing_filter
        )

        listings = {"1": create_test_listing(identifier="1")}
        result = processor.process_new_listings(listings)

        assert result == 0
        notifier.send_message.assert_not_called()

    @patch("src.services.listing_processor.time.sleep")
    def test_unfiltered_listings_are_notified(self, mock_sleep):
        """Test that unfiltered listings are processed."""
        notifier = Mock()
        notifier.format_listing_message.return_value = "Test message"
        listing_filter = Mock()
        listing_filter.is_filtered.return_value = False

        processor = ListingProcessor(
            notifier=notifier, listing_filter=listing_filter
        )

        listings = {"1": create_test_listing(identifier="1")}
        result = processor.process_new_listings(listings)

        assert result == 1
        notifier.send_message.assert_called_once()

    @patch("src.services.listing_processor.time.sleep")
    def test_mixed_filtered_and_unfiltered(self, mock_sleep):
        """Test processing with mix of filtered and unfiltered listings."""
        notifier = Mock()
        notifier.format_listing_message.return_value = "Test message"
        listing_filter = Mock()
        # First listing passes, second is filtered
        listing_filter.is_filtered.side_effect = [False, True, False]

        processor = ListingProcessor(
            notifier=notifier, listing_filter=listing_filter
        )

        listings = {
            "1": create_test_listing(identifier="1"),
            "2": create_test_listing(identifier="2"),
            "3": create_test_listing(identifier="3"),
        }
        result = processor.process_new_listings(listings)

        assert result == 2
        assert notifier.send_message.call_count == 2


class TestAutoApply:
    """Tests for auto-apply behavior."""

    @patch("src.services.listing_processor.time.sleep")
    def test_applier_is_called_for_matching_listing(self, mock_sleep):
        """Test that applier is called when it can handle the listing."""
        notifier = Mock()
        notifier.format_listing_message.return_value = "Test message"

        applier = Mock()
        applier.can_apply.return_value = True
        apply_result = Mock()
        apply_result.is_success = True
        apply_result.applicant_data = {"name": "Test User"}
        applier.apply.return_value = apply_result
        applier.format_success_message.return_value = "Success!"

        processor = ListingProcessor(notifier=notifier, appliers=[applier])

        listings = {"1": create_test_listing(identifier="1")}
        processor.process_new_listings(listings)

        applier.can_apply.assert_called_once()
        applier.apply.assert_called_once()
        # Two messages: one for listing, one for success
        assert notifier.send_message.call_count == 2

    @patch("src.services.listing_processor.time.sleep")
    def test_applier_not_called_for_non_matching_listing(self, mock_sleep):
        """Test that applier is not called when it can't handle the listing."""
        notifier = Mock()
        notifier.format_listing_message.return_value = "Test message"

        applier = Mock()
        applier.can_apply.return_value = False

        processor = ListingProcessor(notifier=notifier, appliers=[applier])

        listings = {"1": create_test_listing(identifier="1")}
        processor.process_new_listings(listings)

        applier.can_apply.assert_called_once()
        applier.apply.assert_not_called()
        # Only one message: listing notification
        assert notifier.send_message.call_count == 1

    @patch("src.services.listing_processor.time.sleep")
    def test_no_success_message_on_failed_apply(self, mock_sleep):
        """Test that no success message is sent when apply fails."""
        notifier = Mock()
        notifier.format_listing_message.return_value = "Test message"

        applier = Mock()
        applier.can_apply.return_value = True
        apply_result = Mock()
        apply_result.is_success = False
        applier.apply.return_value = apply_result

        processor = ListingProcessor(notifier=notifier, appliers=[applier])

        listings = {"1": create_test_listing(identifier="1")}
        processor.process_new_listings(listings)

        # Only one message: listing notification (no success message)
        assert notifier.send_message.call_count == 1

    @patch("src.services.listing_processor.time.sleep")
    def test_only_first_matching_applier_is_used(self, mock_sleep):
        """Test that only the first matching applier is used."""
        notifier = Mock()
        notifier.format_listing_message.return_value = "Test message"

        applier1 = Mock()
        applier1.can_apply.return_value = True
        apply_result1 = Mock()
        apply_result1.is_success = True
        apply_result1.applicant_data = {"name": "User 1"}
        applier1.apply.return_value = apply_result1
        applier1.format_success_message.return_value = "Success 1!"

        applier2 = Mock()
        applier2.can_apply.return_value = True

        processor = ListingProcessor(
            notifier=notifier, appliers=[applier1, applier2]
        )

        listings = {"1": create_test_listing(identifier="1")}
        processor.process_new_listings(listings)

        # First applier should be used
        applier1.apply.assert_called_once()
        # Second applier should not be checked or used
        applier2.can_apply.assert_not_called()
        applier2.apply.assert_not_called()


class TestIsFiltered:
    """Tests for _is_filtered method."""

    def test_returns_false_when_no_filter(self):
        """Test that listings pass when no filter is set."""
        notifier = Mock()
        processor = ListingProcessor(notifier=notifier, listing_filter=None)

        listing = create_test_listing()
        result = processor._is_filtered(listing)

        assert result is False

    def test_returns_filter_result(self):
        """Test that filter result is returned correctly."""
        notifier = Mock()
        listing_filter = Mock()
        listing_filter.is_filtered.return_value = True

        processor = ListingProcessor(
            notifier=notifier, listing_filter=listing_filter
        )

        listing = create_test_listing()
        result = processor._is_filtered(listing)

        assert result is True
        listing_filter.is_filtered.assert_called_once_with(listing)

