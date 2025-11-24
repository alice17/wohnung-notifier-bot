"""
This module defines the ListingStore class for persistence of listings.

The ListingStore provides a high-level interface for listing persistence,
now backed by a SQLite database for improved performance and reliability.
"""
import logging
from typing import Dict

from src.listing import Listing
from src.database import DatabaseManager

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
        Saves the current set of listings to the database.
        
        This method performs a full sync, saving all provided listings
        and removing any that are no longer present.
        
        Args:
            listings: Dictionary of listings to persist.
        """
        try:
            # Get current listings from database
            current_listings = self.db_manager.load_all_listings()
            current_ids = set(current_listings.keys())
            new_ids = set(listings.keys())
            
            # Determine what needs to be deleted
            ids_to_delete = current_ids - new_ids
            if ids_to_delete:
                self.db_manager.delete_listings(list(ids_to_delete))
                logger.info(f"Removed {len(ids_to_delete)} listings from database")
            
            # Save all current listings
            if listings:
                self.db_manager.save_listings(listings)
                logger.info(f"Saved {len(listings)} listings to database")
        except Exception as e:
            logger.error(f"Error saving listings to database: {e}")
