"""
Database module for managing listings storage using SQLite.

This module provides a robust database interface for storing and retrieving
apartment listings with proper error handling and connection management.
"""
import logging
import sqlite3
from contextlib import contextmanager
from typing import Dict, Optional, List

from src.listing import Listing

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database operations for apartment listings.
    
    This class provides a comprehensive interface for CRUD operations on
    apartment listings, with automatic schema creation and connection management.
    """

    def __init__(self, db_path: str = "listings.db"):
        """
        Initialize the DatabaseManager with a database path.
        
        Args:
            db_path: Path to the SQLite database file. Defaults to "listings.db".
        """
        self.db_path = db_path
        self._initialize_database()

    @contextmanager
    def _get_connection(self):
        """
        Context manager for database connections with automatic cleanup.
        
        Yields:
            sqlite3.Connection: Active database connection.
            
        Raises:
            sqlite3.Error: If connection cannot be established.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def _initialize_database(self) -> None:
        """
        Creates the listings table if it doesn't exist.
        
        The table schema matches the Listing dataclass structure with
        proper indexing on identifier for fast lookups.
        """
        create_table_query = """
        CREATE TABLE IF NOT EXISTS listings (
            identifier TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            address TEXT NOT NULL,
            borough TEXT NOT NULL,
            sqm TEXT NOT NULL,
            price_cold TEXT NOT NULL,
            price_total TEXT NOT NULL,
            rooms TEXT NOT NULL,
            wbs TEXT NOT NULL,
            link TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        create_index_query = """
        CREATE INDEX IF NOT EXISTS idx_source 
        ON listings(source);
        """
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(create_table_query)
                cursor.execute(create_index_query)
                conn.commit()
                logger.info("Database initialized successfully")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def save_listing(self, listing: Listing) -> bool:
        """
        Saves or updates a single listing in the database.
        
        Uses INSERT OR REPLACE to handle both new and existing listings,
        updating the timestamp on each save.
        
        Args:
            listing: The Listing object to save.
            
        Returns:
            True if the operation was successful, False otherwise.
        """
        query = """
        INSERT OR REPLACE INTO listings 
        (identifier, source, address, borough, sqm, price_cold, 
         price_total, rooms, wbs, link, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    listing.identifier,
                    listing.source,
                    listing.address,
                    listing.borough,
                    listing.sqm,
                    listing.price_cold,
                    listing.price_total,
                    listing.rooms,
                    listing.wbs,
                    listing.link
                ))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Failed to save listing {listing.identifier}: {e}")
            return False

    def save_listings(self, listings: Dict[str, Listing]) -> bool:
        """
        Saves multiple listings in a single transaction for efficiency.
        
        Args:
            listings: Dictionary mapping identifiers to Listing objects.
            
        Returns:
            True if all listings were saved successfully, False otherwise.
        """
        if not listings:
            return True
            
        query = """
        INSERT OR REPLACE INTO listings 
        (identifier, source, address, borough, sqm, price_cold, 
         price_total, rooms, wbs, link, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                for listing in listings.values():
                    cursor.execute(query, (
                        listing.identifier,
                        listing.source,
                        listing.address,
                        listing.borough,
                        listing.sqm,
                        listing.price_cold,
                        listing.price_total,
                        listing.rooms,
                        listing.wbs,
                        listing.link
                    ))
                conn.commit()
                logger.info(f"Successfully saved {len(listings)} listings")
                return True
        except sqlite3.Error as e:
            logger.error(f"Failed to save listings: {e}")
            return False

    def load_all_listings(self) -> Dict[str, Listing]:
        """
        Loads all listings from the database.
        
        Returns:
            Dictionary mapping identifiers to Listing objects.
        """
        query = """
        SELECT identifier, source, address, borough, sqm, 
               price_cold, price_total, rooms, wbs, link
        FROM listings
        """
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                
                listings = {}
                for row in rows:
                    listing = Listing(
                        source=row['source'],
                        address=row['address'],
                        borough=row['borough'],
                        sqm=row['sqm'],
                        price_cold=row['price_cold'],
                        price_total=row['price_total'],
                        rooms=row['rooms'],
                        wbs=row['wbs'],
                        link=row['link'],
                        identifier=row['identifier']
                    )
                    listings[listing.identifier] = listing
                
                logger.info(f"Loaded {len(listings)} listings from database")
                return listings
        except sqlite3.Error as e:
            logger.error(f"Failed to load listings: {e}")
            return {}

    def get_listing_by_identifier(
        self, 
        identifier: str
    ) -> Optional[Listing]:
        """
        Retrieves a specific listing by its identifier.
        
        Args:
            identifier: The unique identifier of the listing.
            
        Returns:
            Listing object if found, None otherwise.
        """
        query = """
        SELECT identifier, source, address, borough, sqm, 
               price_cold, price_total, rooms, wbs, link
        FROM listings
        WHERE identifier = ?
        """
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (identifier,))
                row = cursor.fetchone()
                
                if row:
                    return Listing(
                        source=row['source'],
                        address=row['address'],
                        borough=row['borough'],
                        sqm=row['sqm'],
                        price_cold=row['price_cold'],
                        price_total=row['price_total'],
                        rooms=row['rooms'],
                        wbs=row['wbs'],
                        link=row['link'],
                        identifier=row['identifier']
                    )
                return None
        except sqlite3.Error as e:
            logger.error(f"Failed to get listing {identifier}: {e}")
            return None

    def get_listings_by_source(self, source: str) -> Dict[str, Listing]:
        """
        Retrieves all listings from a specific source.
        
        Args:
            source: The source name to filter by.
            
        Returns:
            Dictionary mapping identifiers to Listing objects for the source.
        """
        query = """
        SELECT identifier, source, address, borough, sqm, 
               price_cold, price_total, rooms, wbs, link
        FROM listings
        WHERE source = ?
        """
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (source,))
                rows = cursor.fetchall()
                
                listings = {}
                for row in rows:
                    listing = Listing(
                        source=row['source'],
                        address=row['address'],
                        borough=row['borough'],
                        sqm=row['sqm'],
                        price_cold=row['price_cold'],
                        price_total=row['price_total'],
                        rooms=row['rooms'],
                        wbs=row['wbs'],
                        link=row['link'],
                        identifier=row['identifier']
                    )
                    listings[listing.identifier] = listing
                
                return listings
        except sqlite3.Error as e:
            logger.error(f"Failed to get listings for source {source}: {e}")
            return {}

    def delete_listing(self, identifier: str) -> bool:
        """
        Deletes a listing from the database.
        
        Args:
            identifier: The unique identifier of the listing to delete.
            
        Returns:
            True if deletion was successful, False otherwise.
        """
        query = "DELETE FROM listings WHERE identifier = ?"
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (identifier,))
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to delete listing {identifier}: {e}")
            return False

    def delete_listings(self, identifiers: List[str]) -> bool:
        """
        Deletes multiple listings in a single transaction.
        
        Args:
            identifiers: List of identifiers to delete.
            
        Returns:
            True if all deletions were successful, False otherwise.
        """
        if not identifiers:
            return True
            
        query = "DELETE FROM listings WHERE identifier = ?"
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                for identifier in identifiers:
                    cursor.execute(query, (identifier,))
                conn.commit()
                logger.info(f"Deleted {len(identifiers)} listings")
                return True
        except sqlite3.Error as e:
            logger.error(f"Failed to delete listings: {e}")
            return False

    def count_listings(self) -> int:
        """
        Returns the total number of listings in the database.
        
        Returns:
            Total count of listings.
        """
        query = "SELECT COUNT(*) as count FROM listings"
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                row = cursor.fetchone()
                return row['count'] if row else 0
        except sqlite3.Error as e:
            logger.error(f"Failed to count listings: {e}")
            return 0

    def clear_all_listings(self) -> bool:
        """
        Removes all listings from the database.
        
        Use with caution - this operation cannot be undone.
        
        Returns:
            True if the operation was successful, False otherwise.
        """
        query = "DELETE FROM listings"
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                conn.commit()
                logger.warning("All listings cleared from database")
                return True
        except sqlite3.Error as e:
            logger.error(f"Failed to clear listings: {e}")
            return False

