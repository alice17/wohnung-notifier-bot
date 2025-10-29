import logging
from typing import Dict, Any
import urllib.parse

import requests

from scraper.listing import Listing

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Handles sending notifications via Telegram."""

    def __init__(self, telegram_config: Dict[str, Any]):
        self.bot_token = telegram_config['bot_token']
        self.chat_id = telegram_config['chat_id']
        self.url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def send_message(self, message: str):
        """Sends a message to the configured Telegram chat."""
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        try:
            response = requests.post(self.url, data=payload, timeout=10)
            logger.info(f"Telegram response: {response.json().get('ok', False)}")
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")

    def format_listing_message(self, listing: Listing) -> str:
        """Formats the details of a listing into a message string."""
        escaped_link = listing.link.replace('_', r'\_').replace('[', r'\[').replace(']', r'\]') \
            if listing.link != 'N/A' else f"Link not found, ID: {listing.identifier}"
        
        google_maps_url = "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(listing.address)
        address_line = f"[{listing.address}]({google_maps_url})"

        return (
            f"🏠 *New Listing*\n\n"
            f"📍 *Address:* {listing.address}\n"
            f"🏙️ *Borough:* {listing.borough}\n"
            f"📐 *SQM:* {listing.sqm} m²\n"
            f"💶 *Cold Rent:* {listing.price_cold} €\n"
            f"💰 *Total Rent:* {listing.price_total} €\n"
            f"🚪 *Rooms:* {listing.rooms}\n\n"
            f"🔗 *Details:* {escaped_link}"
        )
