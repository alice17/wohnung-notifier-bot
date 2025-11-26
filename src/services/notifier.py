"""
This module handles sending notifications via Telegram.
"""
import logging
import urllib.parse
from typing import Dict, Any, Union

import requests

from src.core.constants import Colors, REQUEST_TIMEOUT_SECONDS
from src.core.listing import Listing

logger = logging.getLogger(__name__)

TELEGRAM_API_URL_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"


def escape_markdown_v2(text: Union[str, int, float]) -> str:
    """
    Escapes characters in a string to be compatible with Telegram's MarkdownV2 format.

    In MarkdownV2, the following characters must be escaped:
    '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'

    Args:
        text: The string or number to escape.

    Returns:
        The escaped string.
    """
    text = str(text)
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)


class TelegramNotifier:
    """Handles sending notifications via Telegram."""

    def __init__(self, telegram_config: Dict[str, Any]) -> None:
        """
        Initialize the TelegramNotifier with configuration.

        Args:
            telegram_config: Dictionary containing 'bot_token' and 'chat_id'.
        """
        self.bot_token = telegram_config['bot_token']
        self.chat_id = telegram_config['chat_id']
        self.url = TELEGRAM_API_URL_TEMPLATE.format(token=self.bot_token)

    def send_message(self, message: str) -> None:
        """
        Sends a message to the configured Telegram chat.

        Args:
            message: The message text to send.
        """
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": True
        }
        try:
            response = requests.post(self.url, data=payload, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()  # Raise an exception for bad status codes
            logger.info(f"Telegram response: {response.json().get('ok', False)}")
        except requests.exceptions.HTTPError as http_err:
            logger.exception(f"{Colors.RED}Telegram API Error: {http_err} - {response.text}{Colors.RESET}")
        except Exception:
            logger.exception(f"{Colors.RED}Error sending Telegram message{Colors.RESET}")

    def format_listing_message(self, listing: Listing) -> str:
        """
        Formats the details of a listing into a message string.

        Args:
            listing: The listing object to format.

        Returns:
            A formatted string suitable for Telegram MarkdownV2.
        """
        if listing.link != 'N/A':
            # Format the link using MarkdownV2 syntax to make it clickable
            escaped_link = escape_markdown_v2(listing.link)
            details_link = f"{escaped_link}"
        else:
            details_link = f"Link not found, ID: {escape_markdown_v2(listing.identifier)}"

        google_maps_url = (
            "https://www.google.com/maps/search/?api=1&query="
            + urllib.parse.quote(listing.address)
        )
        escaped_maps_url = escape_markdown_v2(google_maps_url)
        address_line = f"[{escape_markdown_v2(listing.address)}]({escaped_maps_url})"

        return (
            f"🏠 *New Listing*\n\n"
            f"📍 *Address:* {address_line}\n"
            f"🏙️ *Borough:* {escape_markdown_v2(listing.borough)}\n"
            f"📐 *Size:* {escape_markdown_v2(listing.sqm)} m²\n"
            f"💶 *Cold Rent:* {escape_markdown_v2(listing.price_cold)} €\n"
            f"💰 *Total Rent:* {escape_markdown_v2(listing.price_total)} €\n"
            f"🚪 *Rooms:* {escape_markdown_v2(listing.rooms)}\n\n"
            f"🔗 Details: {details_link}"
        )
