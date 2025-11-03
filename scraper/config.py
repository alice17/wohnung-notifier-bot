import json
from typing import Dict, Any


class Config:
    """Handles loading and validation of settings from a JSON file."""

    def __init__(self, settings_data: Dict[str, Any]):
        self.settings = settings_data
        self._validate()

    @classmethod
    def from_file(cls, filepath: str = 'settings.json'):
        """Loads settings from a specified JSON file."""
        try:
            with open(filepath, 'r') as f:
                return cls(json.load(f))
        except FileNotFoundError:
            raise FileNotFoundError(f"FATAL: {filepath} not found. Please create it.")
        except json.JSONDecodeError:
            raise ValueError(f"FATAL: {filepath} is not valid JSON.")

    def _validate(self):
        """Validates the structure and content of the settings."""
        if 'telegram' not in self.settings or 'scrapers' not in self.settings:
            raise ValueError("settings.json is missing 'telegram' or 'scrapers' sections.")

        bot_token = self.telegram.get('bot_token')
        if not bot_token or "YOUR_TELEGRAM_BOT_TOKEN_HERE" in bot_token:
            raise ValueError("Bot token is missing or not configured in settings.json.")

        chat_id = self.telegram.get('chat_id')
        if not chat_id or "YOUR_TELEGRAM_CHAT_ID_HERE" in chat_id:
            raise ValueError("Chat ID is missing or not configured in settings.json.")

    @property
    def telegram(self) -> Dict[str, Any]:
        return self.settings.get('telegram', {})

    @property
    def scrapers(self) -> Dict[str, Any]:
        return self.settings.get('scrapers', {})

    @property
    def poll_interval(self) -> int:
        return self.settings.get('poll_interval_seconds', 300)

    @property
    def filters(self) -> Dict[str, Any]:
        return self.settings.get('filters', {})
