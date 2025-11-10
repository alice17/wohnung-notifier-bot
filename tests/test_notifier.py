"""
This module contains tests for the TelegramNotifier class.
"""
import unittest
from unittest.mock import MagicMock, patch

from src.listing import Listing
from src.notifier import TelegramNotifier, escape_markdown_v2


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
            identifier='60-7903/24/366',
            link='https://www.wbm.de/wohnungen-berlin/angebote/details/'
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
            "(https://www.google.com/maps/search/?api=1&query=Goltzstrasse%2047%2C%2013587%20Berlin)\n"
            f"🏙️ *Borough:* {escape_markdown_v2(listing.borough)}\n"
            f"📐 *SQM:* {escape_markdown_v2(listing.sqm)} m²\n"
            f"💶 *Cold Rent:* {escape_markdown_v2(listing.price_cold)} €\n"
            f"💰 *Total Rent:* {escape_markdown_v2(listing.price_total)} €\n"
            f"🚪 *Rooms:* {escape_markdown_v2(listing.rooms)}\n\n"
            r"🔗 Details: https://www\.wbm\.de/wohnungen\-berlin/angebote/details/"
            r"?tx\_openimmo\_immobilie\[immobilie\]\=60\-7903/24/366"
        )

        self.assertEqual(self.notifier.format_listing_message(listing), expected_message)

if __name__ == '__main__':
    unittest.main()
