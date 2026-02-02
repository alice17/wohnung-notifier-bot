"""
This module contains tests for the TelegramNotifier class.
"""
import unittest
from unittest.mock import MagicMock, patch

import requests

from src.core.listing import Listing
from src.services.notifier import TelegramNotifier, escape_markdown_v2, MAX_RETRIES


class TestTelegramNotifier(unittest.TestCase):
    """Test suite for the TelegramNotifier class."""

    def setUp(self):
        """Set up a dummy TelegramNotifier instance."""
        telegram_config = {
            'bot_token': 'test_token',
            'chat_id': 'test_chat_id'
        }
        self.notifier = TelegramNotifier(telegram_config)
        self.maxDiff = None

    def test_escape_markdown_v2(self):
        """Tests the MarkdownV2 escaping function."""
        text = "Test with _ * [ ] ( ) ~ ` > # + - = | { } . ! special characters"
        expected = (
            r"Test with \_ \* \[ \] \( \) \~ \` \> \# \+ \- \= \| \{ \} \. \! special characters"
        )
        self.assertEqual(escape_markdown_v2(text), expected)

    def test_format_listing_message_with_special_chars_in_link(self):
        # pylint: disable=duplicate-code
        """
        Tests that a listing with a URL containing special Markdown
        characters is formatted correctly.
        """
        listing = Listing(
            identifier='https://www.wbm.de/wohnungen-berlin/angebote/details/'
                       '?tx_openimmo_immobilie[immobilie]=60-7903/24/366',
            address='Goltzstrasse 47, 13587 Berlin',
            borough='Spandau',
            price_cold=1491.21,
            price_total=1965.21,
            rooms=4.0,
            sqm=110.46,
            source='wbm'
        )

        expected_message = (
            "🏠 *New Listing*\n\n"
            "📍 *Address:* [Goltzstrasse 47, 13587 Berlin]"
            "(https://www\\.google\\.com/maps/search/?api\\=1&query\\=Goltzstrasse%2047%2C%2013587%20Berlin)\n"
            f"🏙️ *Borough:* {escape_markdown_v2(listing.borough)}\n"
            f"📐 *Size:* {escape_markdown_v2(listing.sqm)} m²\n"
            f"💶 *Cold Rent:* {escape_markdown_v2(listing.price_cold)} €\n"
            f"💰 *Total Rent:* {escape_markdown_v2(listing.price_total)} €\n"
            f"🚪 *Rooms:* {escape_markdown_v2(listing.rooms)}\n\n"
            "🔗 Details: https://www\\.wbm\\.de/wohnungen\\-berlin/angebote/details/"
            "?tx\\_openimmo\\_immobilie\\[immobilie\\]\\=60\\-7903/24/366"
        )

        self.assertEqual(self.notifier.format_listing_message(listing), expected_message)

    @patch('src.services.notifier.requests.post')
    def test_send_message_success(self, mock_post):
        """Test that send_message succeeds on first attempt."""
        mock_response = MagicMock()
        mock_response.json.return_value = {'ok': True}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        self.notifier.send_message("Test message")

        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_count, 1)

    @patch('src.services.notifier.time.sleep')
    @patch('src.services.notifier.requests.post')
    def test_send_message_rate_limit_retry_success(self, mock_post, mock_sleep):
        """Test that send_message retries after 429 rate limit and succeeds."""
        # First call returns 429, second call succeeds
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_response.json.return_value = {
            'ok': False,
            'parameters': {'retry_after': 5}
        }
        rate_limit_response.raise_for_status.side_effect = requests.exceptions.HTTPError()

        success_response = MagicMock()
        success_response.json.return_value = {'ok': True}
        success_response.raise_for_status.return_value = None

        mock_post.side_effect = [rate_limit_response, success_response]

        self.notifier.send_message("Test message")

        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(5)

    @patch('src.services.notifier.time.sleep')
    @patch('src.services.notifier.requests.post')
    def test_send_message_rate_limit_max_retries_exceeded(self, mock_post, mock_sleep):
        """Test that send_message stops after MAX_RETRIES rate limit errors."""
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_response.json.return_value = {
            'ok': False,
            'parameters': {'retry_after': 5}
        }
        rate_limit_response.raise_for_status.side_effect = requests.exceptions.HTTPError()

        mock_post.return_value = rate_limit_response

        self.notifier.send_message("Test message")

        self.assertEqual(mock_post.call_count, MAX_RETRIES)
        # Sleep should be called MAX_RETRIES - 1 times (not on the last attempt)
        self.assertEqual(mock_sleep.call_count, MAX_RETRIES - 1)

    @patch('src.services.notifier.requests.post')
    def test_send_message_non_retryable_error(self, mock_post):
        """Test that send_message does not retry on non-429 HTTP errors."""
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.text = "Internal Server Error"
        error_response.raise_for_status.side_effect = requests.exceptions.HTTPError()
        mock_post.return_value = error_response

        self.notifier.send_message("Test message")

        # Should only be called once - no retry for 500 errors
        self.assertEqual(mock_post.call_count, 1)


if __name__ == '__main__':
    unittest.main()
