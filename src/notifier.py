"""
This module handles sending notifications via Telegram.
"""
import logging
import urllib.parse
from typing import Dict, Any, Union

import requests

from src.listing import Listing

logger = logging.getLogger(__name__)

RED = "\033[91m"
RESET = "\033[0m"

TELEGRAM_API_URL_TEMPLATE = "https://api.telegram.org/bot{token}/sendMessage"
REQUEST_TIMEOUT = 10


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
            response = requests.post(self.url, data=payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()  # Raise an exception for bad status codes
            logger.info(f"Telegram response: {response.json().get('ok', False)}")
        except requests.exceptions.HTTPError as http_err:
            logger.exception(f"{RED}Telegram API Error: {http_err} - {response.text}{RESET}")
        except Exception:
            logger.exception(f"{RED}Error sending Telegram message{RESET}")

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
            details_link = f"Details: {escape_markdown_v2(listing.link)}"
        else:
            details_link = f"Link not found, ID: {escape_markdown_v2(listing.identifier)}"

        google_maps_url = (
            "https://www.google.com/maps/search/?api=1&query="
            + urllib.parse.quote(listing.address)
        )
        address_line = f"[{escape_markdown_v2(listing.address)}]({google_maps_url})"

        return (
            f"🏠 *New Listing*\n\n"
            f"📍 *Address:* {address_line}\n"
            f"🏙️ *Borough:* {escape_markdown_v2(listing.borough)}\n"
            f"📐 *Size:* {escape_markdown_v2(listing.sqm)} m²\n"
            f"💶 *Cold Rent:* {escape_markdown_v2(listing.price_cold)} €\n"
            f"💰 *Total Rent:* {escape_markdown_v2(listing.price_total)} €\n"
            f"🚪 *Rooms:* {escape_markdown_v2(listing.rooms)}\n\n"
            f"🔗 {details_link}"
        )
