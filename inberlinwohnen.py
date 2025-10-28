import logging
import sys
import json

from scraper.app import App
from scraper.config import Config
from scraper.notifier import TelegramNotifier
from scraper.scraper import Scraper
from scraper.store import ListingStore


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
        logger.info(f"Loaded scraper configuration:\n{json.dumps(config.scraper, indent=2)}")
        logger.info(f"Loaded filter configuration:\n{json.dumps(config.filters, indent=2)}")
        notifier = TelegramNotifier(config.telegram)
        store = ListingStore()
        scraper = Scraper(config.scraper)

        app = App(config, scraper, store, notifier)
        app.run()

    except (ValueError, FileNotFoundError) as e:
        logger.fatal(f"Application failed to start: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nMonitoring stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()