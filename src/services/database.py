"""
Database module for managing listings storage using SQLite.

This module provides a robust database interface for storing and retrieving
apartment listings with proper error handling and connection management.
"""
import logging
import sqlite3
from contextlib import contextmanager
from typing import Dict, List, Optional

from src.core.listing import Listing

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages SQLite database operations for apartment listings.

    This class provides a comprehensive interface for CRUD operations on
    apartment listings, with automatic schema creation and connection management.
    """

    _SELECT_COLUMNS = """identifier, source, address, borough, sqm, 
               price_cold, price_total, rooms, wbs"""

    _UPSERT_QUERY = """
    INSERT INTO listings 
    (identifier, source, address, borough, sqm, price_cold, 
     price_total, rooms, wbs, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ON CONFLICT(identifier) DO UPDATE SET
        source = excluded.source,
        address = excluded.address,
        borough = excluded.borough,
        sqm = excluded.sqm,
        price_cold = excluded.price_cold,
        price_total = excluded.price_total,
        rooms = excluded.rooms,
        wbs = excluded.wbs,
        updated_at = CURRENT_TIMESTAMP
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

    def _row_to_listing(self, row: sqlite3.Row) -> Listing:
        """
        Converts a database row to a Listing object.

        Args:
            row: A sqlite3.Row containing listing data.

        Returns:
            A Listing object populated with data from the row.
        """
        return Listing(
            source=row["source"],
            address=row["address"],
            borough=row["borough"],
            sqm=row["sqm"],
            price_cold=row["price_cold"],
            price_total=row["price_total"],
            rooms=row["rooms"],
            wbs=bool(row["wbs"]),
            identifier=row["identifier"],
        )

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
            wbs INTEGER NOT NULL DEFAULT 0,
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
                # Migrate old schema if link column exists
                self._migrate_schema(cursor)
                conn.commit()
                logger.info("Database initialized successfully")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def _migrate_schema(self, cursor: sqlite3.Cursor) -> None:
        """
        Migrates old schema to current version.
        
        Handles:
        - Removing deprecated 'link' column
        - Converting 'wbs' from TEXT to INTEGER (boolean)

        Args:
            cursor: Active database cursor.
        """
        cursor.execute("PRAGMA table_info(listings)")
        columns_info = cursor.fetchall()
        columns = {col[1]: col[2] for col in columns_info}  # name -> type

        needs_migration = "link" in columns or columns.get("wbs") == "TEXT"

        if needs_migration:
            logger.info("Migrating database schema...")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS listings_new (
                    identifier TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    address TEXT NOT NULL,
                    borough TEXT NOT NULL,
                    sqm TEXT NOT NULL,
                    price_cold TEXT NOT NULL,
                    price_total TEXT NOT NULL,
                    rooms TEXT NOT NULL,
                    wbs INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )
            # Convert TEXT wbs to INTEGER: 'erforderlich' -> 1, else -> 0
            cursor.execute(
                """
                INSERT INTO listings_new 
                (identifier, source, address, borough, sqm, price_cold, 
                 price_total, rooms, wbs, created_at, updated_at)
                SELECT identifier, source, address, borough, sqm, price_cold, 
                       price_total, rooms, 
                       CASE WHEN LOWER(wbs) LIKE '%erforderlich%' THEN 1 ELSE 0 END,
                       created_at, updated_at
                FROM listings
            """
            )
            cursor.execute("DROP TABLE listings")
            cursor.execute("ALTER TABLE listings_new RENAME TO listings")
            logger.info("Database migration completed successfully")

    def save_listing(self, listing: Listing) -> bool:
        """
        Saves or updates a single listing in the database.

        Uses INSERT with ON CONFLICT to handle both new and existing listings.
        For new listings, both created_at and updated_at are set to current time.
        For existing listings, only updated_at is updated while created_at is
        preserved.

        Args:
            listing: The Listing object to save.

        Returns:
            True if the operation was successful, False otherwise.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(self._UPSERT_QUERY, self._listing_to_tuple(listing))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logger.error(f"Failed to save listing {listing.identifier}: {e}")
            return False

    def _listing_to_tuple(self, listing: Listing) -> tuple:
        """
        Converts a Listing object to a tuple for database operations.

        Args:
            listing: The Listing object to convert.

        Returns:
            Tuple of listing fields in database column order.
        """
        return (
            listing.identifier,
            listing.source,
            listing.address,
            listing.borough,
            listing.sqm,
            listing.price_cold,
            listing.price_total,
            listing.rooms,
            int(listing.wbs),
        )

    def save_listings(self, listings: Dict[str, Listing]) -> bool:
        """
        Saves multiple listings in a single transaction for efficiency.

        Uses INSERT with ON CONFLICT to handle both new and existing listings.
        For new listings, both created_at and updated_at are set to current time.
        For existing listings, only updated_at is updated while created_at is
        preserved.

        Args:
            listings: Dictionary mapping identifiers to Listing objects.

        Returns:
            True if all listings were saved successfully, False otherwise.
        """
        if not listings:
            return True

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(
                    self._UPSERT_QUERY,
                    [self._listing_to_tuple(lst) for lst in listings.values()],
                )
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
        query = f"SELECT {self._SELECT_COLUMNS} FROM listings"

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()

                listings = {
                    row["identifier"]: self._row_to_listing(row) for row in rows
                }

                logger.info(f"Loaded {len(listings)} listings from database")
                return listings
        except sqlite3.Error as e:
            logger.error(f"Failed to load listings: {e}")
            return {}

    def get_listing_by_identifier(self, identifier: str) -> Optional[Listing]:
        """
        Retrieves a specific listing by its identifier.

        Args:
            identifier: The unique identifier of the listing.

        Returns:
            Listing object if found, None otherwise.
        """
        query = f"SELECT {self._SELECT_COLUMNS} FROM listings WHERE identifier = ?"

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (identifier,))
                row = cursor.fetchone()

                return self._row_to_listing(row) if row else None
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
        query = f"SELECT {self._SELECT_COLUMNS} FROM listings WHERE source = ?"

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (source,))
                rows = cursor.fetchall()

                return {row["identifier"]: self._row_to_listing(row) for row in rows}
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

        placeholders = ",".join("?" * len(identifiers))
        query = f"DELETE FROM listings WHERE identifier IN ({placeholders})"

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, identifiers)
                conn.commit()
                logger.info(f"Deleted {cursor.rowcount} listings")
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
                return row["count"] if row else 0
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

    def delete_old_listings(self, max_age_days: int = 2) -> int:
        """
        Deletes listings older than the specified number of days.

        Uses the updated_at timestamp to determine listing age.

        Args:
            max_age_days: Maximum age in days before a listing is deleted.
                          Defaults to 2 days.

        Returns:
            Number of listings deleted.
        """
        query = """
        DELETE FROM listings 
        WHERE updated_at < datetime('now', ?)
        """

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (f"-{max_age_days} days",))
                deleted_count = cursor.rowcount
                conn.commit()

                if deleted_count > 0:
                    logger.info(
                        f"Cleaned up {deleted_count} listings older than "
                        f"{max_age_days} days"
                    )
                return deleted_count
        except sqlite3.Error as e:
            logger.error(f"Failed to delete old listings: {e}")
            return 0
