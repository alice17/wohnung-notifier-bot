"""
This module defines the ListingStore class for persistence of listings.

The ListingStore provides a high-level interface for listing persistence,
now backed by a SQLite database for improved performance and reliability.
"""
import logging
from typing import Dict, List

from src.core.listing import Listing
from src.services.database import DatabaseManager

logger = logging.getLogger(__name__)


class ListingStore:
    """
    Manages the persistence of known listing identifiers using a database.
    
    This class provides a simplified interface for listing storage operations,
    maintaining backward compatibility with the previous JSON-based implementation.
    """

    def __init__(self, db_path: str = "listings.db"):
        """
        Initialize the ListingStore with a database connection.
        
        Args:
            db_path: Path to the SQLite database file. Defaults to "listings.db".
        """
        self.db_manager = DatabaseManager(db_path)
        logger.info(f"ListingStore initialized with database: {db_path}")

    def load(self) -> Dict[str, Listing]:
        """
        Loads all known listings from the database.
        
        Returns:
            Dictionary mapping identifiers to Listing objects.
        """
        try:
            listings = self.db_manager.load_all_listings()
            logger.info(f"Loaded {len(listings)} listings from database")
            return listings
        except Exception as e:
            logger.error(f"Error loading listings from database: {e}")
            return {}

    def save(self, listings: Dict[str, Listing]) -> None:
        """
        Saves the provided listings to the database.
        
        This method saves all provided listings (insert or update).
        Old listings are cleaned up separately via cleanup_old_listings().
        
        Args:
            listings: Dictionary of listings to persist.
        """
        try:
            if listings:
                self.db_manager.save_listings(listings)
                logger.info(f"Saved {len(listings)} listings to database")
        except Exception as e:
            logger.error(f"Error saving listings to database: {e}")

    def touch(self, identifiers: List[str]) -> int:
        """
        Updates the updated_at timestamp for active listings.

        This marks listings as "still seen" on websites, preventing
        them from being cleaned up as stale by cleanup_old_listings().

        Args:
            identifiers: List of listing identifiers still seen on websites.

        Returns:
            Number of listings updated.
        """
        return self.db_manager.touch_listings(identifiers)

    def cleanup_old_listings(self, max_age_days: int = 2) -> int:
        """
        Removes listings older than the specified number of days.
        
        Args:
            max_age_days: Maximum age in days before a listing is deleted.
                          Defaults to 2 days.
        
        Returns:
            Number of listings removed.
        """
        return self.db_manager.delete_old_listings(max_age_days)
