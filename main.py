"""
This module is the main entry point for the application.
"""
import logging
import sys
import json

from src.app import App
from src.config import Config
from src.notifier import TelegramNotifier
from src.scrapers import SCRAPER_CLASSES
from src.store import ListingStore


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)-8s - [%(filename)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    """Initializes and runs the monitoring application."""
    try:
        config = Config.from_file('settings.json')
        logger.info(
            "Loaded scraper configurations:\n%s", json.dumps(config.scrapers, indent=2)
        )
        logger.info(
            "Loaded filter configuration:\n%s", json.dumps(config.filters, indent=2)
        )

        scrapers = []
        for name, scraper_config in config.scrapers.items():
            if scraper_config.get("enabled", False):
                if name in SCRAPER_CLASSES:
                    scraper_class = SCRAPER_CLASSES[name]
                    scrapers.append(scraper_class(name=name))
                    logger.info("Enabled scraper: %s", name)
                else:
                    logger.warning(
                        "Scraper '%s' is configured but not found in SCRAPER_CLASSES.", name
                    )

        if not scrapers:
            logger.fatal("No scrapers enabled. Exiting.")
            sys.exit(1)

        notifier = TelegramNotifier(config.telegram)
        store = ListingStore()

        app = App(config, scrapers, store, notifier)
        app.run()

    except (ValueError, FileNotFoundError) as e:
        logger.fatal("Application failed to start: %s", e)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nMonitoring stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()