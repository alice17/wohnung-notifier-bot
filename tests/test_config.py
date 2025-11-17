"""
Tests for the Config class.
"""
import json
import tempfile
import unittest
from pathlib import Path

from src.config import Config


class TestConfig(unittest.TestCase):
    """Test suite for Config class."""

    def test_load_valid_config_from_file(self):
        """Tests loading a valid configuration from file."""
        config_data = {
            "telegram": {
                "bot_token": "test_token_123",
                "chat_id": "test_chat_456"
            },
            "scrapers": {
                "kleinanzeigen": {"enabled": True}
            },
            "poll_interval_seconds": 300,
            "filters": {"enabled": False}
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            config = Config.from_file(temp_path)
            self.assertEqual(config.telegram['bot_token'], "test_token_123")
            self.assertEqual(config.telegram['chat_id'], "test_chat_456")
            self.assertEqual(config.poll_interval, 300)
        finally:
            Path(temp_path).unlink()

    def test_missing_config_file_raises_error(self):
        """Tests that missing config file raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError) as context:
            Config.from_file('nonexistent_file.json')
        self.assertIn("not found", str(context.exception))

    def test_invalid_json_raises_error(self):
        """Tests that invalid JSON raises ValueError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name

        try:
            with self.assertRaises(ValueError) as context:
                Config.from_file(temp_path)
            self.assertIn("not valid JSON", str(context.exception))
        finally:
            Path(temp_path).unlink()

    def test_missing_telegram_section_raises_error(self):
        """Tests that missing telegram section raises ValueError."""
        config_data = {"scrapers": {}}
        with self.assertRaises(ValueError) as context:
            Config(config_data)
        self.assertIn("telegram", str(context.exception).lower())

    def test_missing_scrapers_section_raises_error(self):
        """Tests that missing scrapers section raises ValueError."""
        config_data = {
            "telegram": {
                "bot_token": "valid_token",
                "chat_id": "123456"
            }
        }
        with self.assertRaises(ValueError) as context:
            Config(config_data)
        self.assertIn("scrapers", str(context.exception).lower())

    def test_placeholder_bot_token_raises_error(self):
        """Tests that placeholder bot token raises ValueError."""
        config_data = {
            "telegram": {
                "bot_token": "YOUR_TELEGRAM_BOT_TOKEN_HERE",
                "chat_id": "123456"
            },
            "scrapers": {}
        }
        with self.assertRaises(ValueError) as context:
            Config(config_data)
        self.assertIn("Bot token", str(context.exception))

    def test_missing_bot_token_raises_error(self):
        """Tests that missing bot_token raises ValueError."""
        config_data = {
            "telegram": {
                "chat_id": "123456"
            },
            "scrapers": {}
        }
        with self.assertRaises(ValueError) as context:
            Config(config_data)
        self.assertIn("Bot token", str(context.exception))

    def test_placeholder_chat_id_raises_error(self):
        """Tests that placeholder chat_id raises ValueError."""
        config_data = {
            "telegram": {
                "bot_token": "valid_token",
                "chat_id": "YOUR_TELEGRAM_CHAT_ID_HERE"
            },
            "scrapers": {}
        }
        with self.assertRaises(ValueError) as context:
            Config(config_data)
        self.assertIn("Chat ID", str(context.exception))

    def test_missing_chat_id_raises_error(self):
        """Tests that missing chat_id raises ValueError."""
        config_data = {
            "telegram": {
                "bot_token": "valid_token"
            },
            "scrapers": {}
        }
        with self.assertRaises(ValueError) as context:
            Config(config_data)
        self.assertIn("Chat ID", str(context.exception))

    def test_default_poll_interval(self):
        """Tests default poll interval when not specified."""
        config_data = {
            "telegram": {"bot_token": "token", "chat_id": "123"},
            "scrapers": {}
        }
        config = Config(config_data)
        self.assertEqual(config.poll_interval, 300)

    def test_custom_poll_interval(self):
        """Tests custom poll interval."""
        config_data = {
            "telegram": {"bot_token": "token", "chat_id": "123"},
            "scrapers": {},
            "poll_interval_seconds": 600
        }
        config = Config(config_data)
        self.assertEqual(config.poll_interval, 600)

    def test_telegram_property(self):
        """Tests telegram property returns correct dictionary."""
        config_data = {
            "telegram": {
                "bot_token": "my_token",
                "chat_id": "my_chat"
            },
            "scrapers": {}
        }
        config = Config(config_data)
        telegram = config.telegram
        self.assertEqual(telegram['bot_token'], "my_token")
        self.assertEqual(telegram['chat_id'], "my_chat")

    def test_scrapers_property(self):
        """Tests scrapers property returns correct dictionary."""
        config_data = {
            "telegram": {"bot_token": "token", "chat_id": "123"},
            "scrapers": {
                "kleinanzeigen": {"enabled": True},
                "immowelt": {"enabled": False}
            }
        }
        config = Config(config_data)
        scrapers = config.scrapers
        self.assertIn("kleinanzeigen", scrapers)
        self.assertIn("immowelt", scrapers)
        self.assertTrue(scrapers["kleinanzeigen"]["enabled"])
        self.assertFalse(scrapers["immowelt"]["enabled"])

    def test_filters_property(self):
        """Tests filters property returns correct dictionary."""
        config_data = {
            "telegram": {"bot_token": "token", "chat_id": "123"},
            "scrapers": {},
            "filters": {
                "enabled": True,
                "properties": {
                    "price_total": {"max": 1000}
                }
            }
        }
        config = Config(config_data)
        filters = config.filters
        self.assertTrue(filters["enabled"])
        self.assertEqual(filters["properties"]["price_total"]["max"], 1000)

    def test_filters_property_default_empty(self):
        """Tests filters property returns empty dict when not specified."""
        config_data = {
            "telegram": {"bot_token": "token", "chat_id": "123"},
            "scrapers": {}
        }
        config = Config(config_data)
        self.assertEqual(config.filters, {})

    def test_suspension_periods_property(self):
        """Tests accessing suspension periods."""
        config_data = {
            "telegram": {"bot_token": "token", "chat_id": "123"},
            "scrapers": {},
            "suspension_periods": [
                {"start": "22:00", "end": "07:00"},
                {"start": "12:00", "end": "13:00"}
            ]
        }
        config = Config(config_data)
        periods = config.suspension_periods
        self.assertEqual(len(periods), 2)
        self.assertEqual(periods[0]["start"], "22:00")
        self.assertEqual(periods[1]["end"], "13:00")

    def test_suspension_periods_default_empty(self):
        """Tests default suspension periods when not specified."""
        config_data = {
            "telegram": {"bot_token": "token", "chat_id": "123"},
            "scrapers": {}
        }
        config = Config(config_data)
        self.assertEqual(config.suspension_periods, [])

    def test_suspension_start_hour_default(self):
        """Tests default suspension start hour."""
        config_data = {
            "telegram": {"bot_token": "token", "chat_id": "123"},
            "scrapers": {}
        }
        config = Config(config_data)
        self.assertEqual(config.suspension_start_hour, 0)

    def test_suspension_end_hour_default(self):
        """Tests default suspension end hour."""
        config_data = {
            "telegram": {"bot_token": "token", "chat_id": "123"},
            "scrapers": {}
        }
        config = Config(config_data)
        self.assertEqual(config.suspension_end_hour, 7)

    def test_suspension_hours_custom_values(self):
        """Tests custom suspension hours."""
        config_data = {
            "telegram": {"bot_token": "token", "chat_id": "123"},
            "scrapers": {},
            "scraper": {
                "suspension_start_hour": 22,
                "suspension_end_hour": 8
            }
        }
        config = Config(config_data)
        self.assertEqual(config.suspension_start_hour, 22)
        self.assertEqual(config.suspension_end_hour, 8)

    def test_config_with_all_sections(self):
        """Tests loading config with all possible sections."""
        config_data = {
            "telegram": {
                "bot_token": "full_token",
                "chat_id": "full_chat"
            },
            "scrapers": {
                "kleinanzeigen": {"enabled": True}
            },
            "poll_interval_seconds": 450,
            "filters": {
                "enabled": True,
                "properties": {
                    "price_total": {"min": 500, "max": 1500}
                }
            },
            "suspension_periods": [{"start": "23:00", "end": "06:00"}],
            "scraper": {
                "suspension_start_hour": 23,
                "suspension_end_hour": 6
            }
        }
        config = Config(config_data)

        # Verify all properties
        self.assertEqual(config.telegram['bot_token'], "full_token")
        self.assertEqual(config.poll_interval, 450)
        self.assertTrue(config.filters['enabled'])
        self.assertEqual(len(config.suspension_periods), 1)
        self.assertEqual(config.suspension_start_hour, 23)
        self.assertEqual(config.suspension_end_hour, 6)

    def test_empty_bot_token_raises_error(self):
        """Tests that empty bot token raises ValueError."""
        config_data = {
            "telegram": {
                "bot_token": "",
                "chat_id": "123456"
            },
            "scrapers": {}
        }
        with self.assertRaises(ValueError) as context:
            Config(config_data)
        self.assertIn("Bot token", str(context.exception))

    def test_empty_chat_id_raises_error(self):
        """Tests that empty chat_id raises ValueError."""
        config_data = {
            "telegram": {
                "bot_token": "valid_token",
                "chat_id": ""
            },
            "scrapers": {}
        }
        with self.assertRaises(ValueError) as context:
            Config(config_data)
        self.assertIn("Chat ID", str(context.exception))


if __name__ == '__main__':
    unittest.main()

