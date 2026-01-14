"""
This module is the main entry point for the application.
"""
import argparse
import logging
import sys
import json
from typing import List

from src.app import App
from src.appliers import APPLIER_CLASSES, BaseApplier
from src.core.config import Config
from src.scrapers import SCRAPER_CLASSES, BaseScraper
from src.services.notifier import TelegramNotifier
from src.services.store import ListingStore


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)-8s - [%(filename)s:%(lineno)d] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_scrapers(config: Config) -> List[BaseScraper]:
    """
    Load enabled scrapers based on configuration.

    Args:
        config: Application configuration object.

    Returns:
        List of instantiated scraper objects.
    """
    scrapers = []
    for name, scraper_config in config.scrapers.items():
        if scraper_config.get("enabled", False):
            if name in SCRAPER_CLASSES:
                scraper_class = SCRAPER_CLASSES[name]
                scrapers.append(scraper_class(name=name))
                logger.info(f"Enabled scraper: {name}")
            else:
                logger.warning(
                    f"Scraper '{name}' is configured but not found in SCRAPER_CLASSES."
                )
    return scrapers


def load_appliers(config: Config) -> List[BaseApplier]:
    """
    Load enabled appliers based on configuration.

    Args:
        config: Application configuration object.

    Returns:
        List of instantiated applier objects.
    """
    appliers = []
    for name, applier_config in config.appliers.items():
        if applier_config.get("enabled", False):
            if name in APPLIER_CLASSES:
                # Extract config without 'enabled' key for applier initialization
                applier_init_config = {
                    key: value
                    for key, value in applier_config.items()
                    if key != "enabled"
                }
                applier_class = APPLIER_CLASSES[name]
                appliers.append(applier_class(config=applier_init_config))
                logger.info(f"Enabled applier: {name}")
            else:
                logger.warning(
                    f"Applier '{name}' is configured but not found in APPLIER_CLASSES."
                )
    return appliers


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Apartment listing scraper and notifier."
    )
    parser.add_argument(
        "--cron",
        action="store_true",
        help="Run once and exit immediately (for cron job scheduling).",
    )
    return parser.parse_args()


def main():
    """Initializes and runs the monitoring application."""
    args = parse_arguments()

    try:
        config = Config.from_file('settings.json')
        logger.info(
            f"Loaded scraper configurations:\n{json.dumps(config.scrapers, indent=2)}"
        )
        logger.info(
            f"Loaded filter configuration:\n{json.dumps(config.filters, indent=2)}"
        )

        scrapers = load_scrapers(config)
        if not scrapers:
            logger.fatal("No scrapers enabled. Exiting.")
            sys.exit(1)

        appliers = load_appliers(config)

        notifier = TelegramNotifier(config.telegram)
        store = ListingStore()

        app = App(config, scrapers, store, notifier, appliers=appliers)
        app.run(cron_mode=args.cron)

    except (ValueError, FileNotFoundError) as e:
        logger.fatal(f"Application failed to start: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nMonitoring stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
