"""
This module contains tests for the DatabaseManager class.
"""
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from src.services.database import DatabaseManager
from src.core.listing import Listing


class TestDatabaseManager(unittest.TestCase):
    """Base test class for DatabaseManager tests."""

    def setUp(self):
        """Set up a temporary database for each test."""
        self.temp_db = tempfile.NamedTemporaryFile(
            suffix='.db',
            delete=False
        )
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        self.db_manager = DatabaseManager(self.temp_db_path)

    def tearDown(self):
        """Clean up temporary database after each test."""
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def _create_sample_listing(
        self,
        identifier: str = "test-123",
        source: str = "test_source"
    ) -> Listing:
        """
        Creates a sample Listing object for testing.
        
        Args:
            identifier: Unique identifier for the listing.
            source: Source name for the listing.
            
        Returns:
            A Listing object with test data.
        """
        return Listing(
            identifier=identifier,
            source=source,
            address="Test Street 42, 12345 Berlin",
            borough="Mitte",
            sqm="75.5",
            price_cold="800",
            price_total="1000",
            rooms="3",
            wbs="No",
            link="https://example.com/listing/" + identifier
        )


class TestDatabaseManagerInitialization(TestDatabaseManager):
    """Tests for DatabaseManager initialization."""

    def test_init_creates_database_file(self):
        """Tests that initialization creates the database file."""
        self.assertTrue(os.path.exists(self.temp_db_path))

    def test_init_creates_listings_table(self):
        """Tests that initialization creates the listings table."""
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='listings'"
        )
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'listings')

    def test_init_creates_source_index(self):
        """Tests that initialization creates the source index."""
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='idx_source'"
        )
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'idx_source')

    def test_init_with_custom_path(self):
        """Tests that initialization works with a custom database path."""
        custom_path = os.path.join(
            tempfile.gettempdir(),
            "custom_test.db"
        )
        try:
            manager = DatabaseManager(custom_path)
            self.assertEqual(manager.db_path, custom_path)
            self.assertTrue(os.path.exists(custom_path))
        finally:
            if os.path.exists(custom_path):
                os.remove(custom_path)

    def test_table_has_correct_columns(self):
        """Tests that the listings table has all required columns."""
        expected_columns = [
            'identifier', 'source', 'address', 'borough', 'sqm',
            'price_cold', 'price_total', 'rooms', 'wbs', 'link',
            'created_at', 'updated_at'
        ]
        
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(listings)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        
        for col in expected_columns:
            self.assertIn(col, columns)


class TestSaveListing(TestDatabaseManager):
    """Tests for DatabaseManager.save_listing() method."""

    def test_save_listing_returns_true_on_success(self):
        """Tests that save_listing returns True on success."""
        listing = self._create_sample_listing()
        result = self.db_manager.save_listing(listing)
        self.assertTrue(result)

    def test_save_listing_persists_data(self):
        """Tests that save_listing correctly persists listing data."""
        listing = self._create_sample_listing()
        self.db_manager.save_listing(listing)
        
        loaded = self.db_manager.get_listing_by_identifier(listing.identifier)
        
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.source, listing.source)
        self.assertEqual(loaded.address, listing.address)
        self.assertEqual(loaded.borough, listing.borough)
        self.assertEqual(loaded.sqm, listing.sqm)
        self.assertEqual(loaded.price_cold, listing.price_cold)
        self.assertEqual(loaded.price_total, listing.price_total)
        self.assertEqual(loaded.rooms, listing.rooms)
        self.assertEqual(loaded.wbs, listing.wbs)
        self.assertEqual(loaded.link, listing.link)

    def test_save_listing_updates_existing(self):
        """Tests that save_listing updates existing listing."""
        listing = self._create_sample_listing("update-test")
        self.db_manager.save_listing(listing)
        
        updated_listing = Listing(
            identifier="update-test",
            source="updated_source",
            address="New Address 99",
            borough="Kreuzberg",
            sqm="100",
            price_cold="1200",
            price_total="1500",
            rooms="4",
            wbs="Yes",
            link="https://example.com/updated"
        )
        self.db_manager.save_listing(updated_listing)
        
        loaded = self.db_manager.get_listing_by_identifier("update-test")
        self.assertEqual(loaded.address, "New Address 99")
        self.assertEqual(loaded.borough, "Kreuzberg")
        self.assertEqual(self.db_manager.count_listings(), 1)

    @patch('src.services.database.DatabaseManager._get_connection')
    def test_save_listing_returns_false_on_error(self, mock_conn):
        """Tests that save_listing returns False on database error."""
        mock_conn.side_effect = sqlite3.Error("Database error")
        
        listing = self._create_sample_listing()
        result = self.db_manager.save_listing(listing)
        
        self.assertFalse(result)


class TestSaveListings(TestDatabaseManager):
    """Tests for DatabaseManager.save_listings() method."""

    def test_save_listings_returns_true_for_empty_dict(self):
        """Tests that save_listings returns True for empty dict."""
        result = self.db_manager.save_listings({})
        self.assertTrue(result)

    def test_save_listings_returns_true_on_success(self):
        """Tests that save_listings returns True on success."""
        listings = {
            "listing-1": self._create_sample_listing("listing-1"),
            "listing-2": self._create_sample_listing("listing-2")
        }
        result = self.db_manager.save_listings(listings)
        self.assertTrue(result)

    def test_save_listings_persists_all_listings(self):
        """Tests that save_listings persists all provided listings."""
        listings = {}
        for i in range(5):
            listing = self._create_sample_listing(f"batch-{i}")
            listings[listing.identifier] = listing
        
        self.db_manager.save_listings(listings)
        
        self.assertEqual(self.db_manager.count_listings(), 5)

    def test_save_listings_updates_existing(self):
        """Tests that save_listings updates existing listings."""
        original = self._create_sample_listing("update-batch")
        self.db_manager.save_listing(original)
        
        updated = Listing(
            identifier="update-batch",
            source="batch_source",
            address="Batch Updated Address",
            borough="Wedding",
            sqm="90",
            price_cold="950",
            price_total="1200",
            rooms="3.5",
            wbs="No",
            link="https://example.com/batch-updated"
        )
        self.db_manager.save_listings({updated.identifier: updated})
        
        loaded = self.db_manager.get_listing_by_identifier("update-batch")
        self.assertEqual(loaded.address, "Batch Updated Address")

    @patch('src.services.database.DatabaseManager._get_connection')
    def test_save_listings_returns_false_on_error(self, mock_conn):
        """Tests that save_listings returns False on database error."""
        mock_conn.side_effect = sqlite3.Error("Batch save error")
        
        listings = {"test": self._create_sample_listing()}
        result = self.db_manager.save_listings(listings)
        
        self.assertFalse(result)


class TestLoadAllListings(TestDatabaseManager):
    """Tests for DatabaseManager.load_all_listings() method."""

    def test_load_all_returns_empty_dict_for_empty_database(self):
        """Tests that load_all_listings returns empty dict when empty."""
        result = self.db_manager.load_all_listings()
        self.assertEqual(result, {})

    def test_load_all_returns_all_listings(self):
        """Tests that load_all_listings returns all saved listings."""
        for i in range(3):
            self.db_manager.save_listing(
                self._create_sample_listing(f"load-all-{i}")
            )
        
        result = self.db_manager.load_all_listings()
        
        self.assertEqual(len(result), 3)
        self.assertIn("load-all-0", result)
        self.assertIn("load-all-1", result)
        self.assertIn("load-all-2", result)

    def test_load_all_returns_correct_listing_objects(self):
        """Tests that load_all returns proper Listing objects."""
        listing = self._create_sample_listing("load-test")
        self.db_manager.save_listing(listing)
        
        result = self.db_manager.load_all_listings()
        loaded = result["load-test"]
        
        self.assertIsInstance(loaded, Listing)
        self.assertEqual(loaded.source, listing.source)
        self.assertEqual(loaded.address, listing.address)

    @patch('src.services.database.DatabaseManager._get_connection')
    def test_load_all_returns_empty_dict_on_error(self, mock_conn):
        """Tests that load_all_listings returns empty dict on error."""
        mock_conn.side_effect = sqlite3.Error("Load error")
        
        result = self.db_manager.load_all_listings()
        
        self.assertEqual(result, {})


class TestGetListingByIdentifier(TestDatabaseManager):
    """Tests for DatabaseManager.get_listing_by_identifier() method."""

    def test_get_by_identifier_returns_none_for_missing(self):
        """Tests that get_listing_by_identifier returns None if not found."""
        result = self.db_manager.get_listing_by_identifier("nonexistent")
        self.assertIsNone(result)

    def test_get_by_identifier_returns_correct_listing(self):
        """Tests that get_listing_by_identifier returns correct listing."""
        listing = self._create_sample_listing("specific-id")
        self.db_manager.save_listing(listing)
        
        result = self.db_manager.get_listing_by_identifier("specific-id")
        
        self.assertIsNotNone(result)
        self.assertEqual(result.identifier, "specific-id")
        self.assertEqual(result.source, listing.source)

    def test_get_by_identifier_returns_listing_object(self):
        """Tests that get_listing_by_identifier returns Listing instance."""
        self.db_manager.save_listing(self._create_sample_listing("obj-test"))
        
        result = self.db_manager.get_listing_by_identifier("obj-test")
        
        self.assertIsInstance(result, Listing)

    @patch('src.services.database.DatabaseManager._get_connection')
    def test_get_by_identifier_returns_none_on_error(self, mock_conn):
        """Tests that get_listing_by_identifier returns None on error."""
        mock_conn.side_effect = sqlite3.Error("Get error")
        
        result = self.db_manager.get_listing_by_identifier("test-id")
        
        self.assertIsNone(result)


class TestGetListingsBySource(TestDatabaseManager):
    """Tests for DatabaseManager.get_listings_by_source() method."""

    def test_get_by_source_returns_empty_for_no_matches(self):
        """Tests that get_listings_by_source returns empty for no matches."""
        result = self.db_manager.get_listings_by_source("nonexistent_source")
        self.assertEqual(result, {})

    def test_get_by_source_returns_matching_listings(self):
        """Tests that get_listings_by_source returns matching listings."""
        self.db_manager.save_listing(
            self._create_sample_listing("degewo-1", "degewo")
        )
        self.db_manager.save_listing(
            self._create_sample_listing("degewo-2", "degewo")
        )
        self.db_manager.save_listing(
            self._create_sample_listing("wbm-1", "wbm")
        )
        
        result = self.db_manager.get_listings_by_source("degewo")
        
        self.assertEqual(len(result), 2)
        self.assertIn("degewo-1", result)
        self.assertIn("degewo-2", result)
        self.assertNotIn("wbm-1", result)

    def test_get_by_source_excludes_other_sources(self):
        """Tests that get_listings_by_source excludes other sources."""
        self.db_manager.save_listing(
            self._create_sample_listing("source-a-1", "source_a")
        )
        self.db_manager.save_listing(
            self._create_sample_listing("source-b-1", "source_b")
        )
        
        result = self.db_manager.get_listings_by_source("source_a")
        
        self.assertEqual(len(result), 1)
        self.assertIn("source-a-1", result)

    @patch('src.services.database.DatabaseManager._get_connection')
    def test_get_by_source_returns_empty_on_error(self, mock_conn):
        """Tests that get_listings_by_source returns empty dict on error."""
        mock_conn.side_effect = sqlite3.Error("Source query error")
        
        result = self.db_manager.get_listings_by_source("test_source")
        
        self.assertEqual(result, {})


class TestDeleteListing(TestDatabaseManager):
    """Tests for DatabaseManager.delete_listing() method."""

    def test_delete_listing_returns_false_for_missing(self):
        """Tests that delete_listing returns False for nonexistent listing."""
        result = self.db_manager.delete_listing("nonexistent")
        self.assertFalse(result)

    def test_delete_listing_returns_true_on_success(self):
        """Tests that delete_listing returns True on successful deletion."""
        self.db_manager.save_listing(self._create_sample_listing("delete-me"))
        
        result = self.db_manager.delete_listing("delete-me")
        
        self.assertTrue(result)

    def test_delete_listing_removes_from_database(self):
        """Tests that delete_listing removes the listing from database."""
        self.db_manager.save_listing(self._create_sample_listing("to-remove"))
        self.assertEqual(self.db_manager.count_listings(), 1)
        
        self.db_manager.delete_listing("to-remove")
        
        self.assertEqual(self.db_manager.count_listings(), 0)
        self.assertIsNone(
            self.db_manager.get_listing_by_identifier("to-remove")
        )

    def test_delete_listing_only_deletes_specified(self):
        """Tests that delete_listing only removes the specified listing."""
        self.db_manager.save_listing(self._create_sample_listing("keep-1"))
        self.db_manager.save_listing(self._create_sample_listing("delete-2"))
        self.db_manager.save_listing(self._create_sample_listing("keep-3"))
        
        self.db_manager.delete_listing("delete-2")
        
        self.assertEqual(self.db_manager.count_listings(), 2)
        self.assertIsNotNone(
            self.db_manager.get_listing_by_identifier("keep-1")
        )
        self.assertIsNotNone(
            self.db_manager.get_listing_by_identifier("keep-3")
        )

    @patch('src.services.database.DatabaseManager._get_connection')
    def test_delete_listing_returns_false_on_error(self, mock_conn):
        """Tests that delete_listing returns False on database error."""
        mock_conn.side_effect = sqlite3.Error("Delete error")
        
        result = self.db_manager.delete_listing("test-id")
        
        self.assertFalse(result)


class TestDeleteListings(TestDatabaseManager):
    """Tests for DatabaseManager.delete_listings() method."""

    def test_delete_listings_returns_true_for_empty_list(self):
        """Tests that delete_listings returns True for empty list."""
        result = self.db_manager.delete_listings([])
        self.assertTrue(result)

    def test_delete_listings_returns_true_on_success(self):
        """Tests that delete_listings returns True on success."""
        self.db_manager.save_listing(self._create_sample_listing("batch-del-1"))
        self.db_manager.save_listing(self._create_sample_listing("batch-del-2"))
        
        result = self.db_manager.delete_listings(["batch-del-1", "batch-del-2"])
        
        self.assertTrue(result)

    def test_delete_listings_removes_all_specified(self):
        """Tests that delete_listings removes all specified listings."""
        for i in range(5):
            self.db_manager.save_listing(
                self._create_sample_listing(f"multi-del-{i}")
            )
        
        self.db_manager.delete_listings(
            ["multi-del-0", "multi-del-2", "multi-del-4"]
        )
        
        self.assertEqual(self.db_manager.count_listings(), 2)
        self.assertIsNotNone(
            self.db_manager.get_listing_by_identifier("multi-del-1")
        )
        self.assertIsNotNone(
            self.db_manager.get_listing_by_identifier("multi-del-3")
        )

    @patch('src.services.database.DatabaseManager._get_connection')
    def test_delete_listings_returns_false_on_error(self, mock_conn):
        """Tests that delete_listings returns False on database error."""
        mock_conn.side_effect = sqlite3.Error("Batch delete error")
        
        result = self.db_manager.delete_listings(["id-1", "id-2"])
        
        self.assertFalse(result)


class TestCountListings(TestDatabaseManager):
    """Tests for DatabaseManager.count_listings() method."""

    def test_count_returns_zero_for_empty_database(self):
        """Tests that count_listings returns 0 for empty database."""
        result = self.db_manager.count_listings()
        self.assertEqual(result, 0)

    def test_count_returns_correct_count(self):
        """Tests that count_listings returns correct count."""
        for i in range(7):
            self.db_manager.save_listing(
                self._create_sample_listing(f"count-{i}")
            )
        
        result = self.db_manager.count_listings()
        
        self.assertEqual(result, 7)

    def test_count_updates_after_delete(self):
        """Tests that count_listings updates after deletion."""
        for i in range(5):
            self.db_manager.save_listing(
                self._create_sample_listing(f"count-del-{i}")
            )
        
        self.assertEqual(self.db_manager.count_listings(), 5)
        
        self.db_manager.delete_listing("count-del-2")
        
        self.assertEqual(self.db_manager.count_listings(), 4)

    @patch('src.services.database.DatabaseManager._get_connection')
    def test_count_returns_zero_on_error(self, mock_conn):
        """Tests that count_listings returns 0 on database error."""
        mock_conn.side_effect = sqlite3.Error("Count error")
        
        result = self.db_manager.count_listings()
        
        self.assertEqual(result, 0)


class TestClearAllListings(TestDatabaseManager):
    """Tests for DatabaseManager.clear_all_listings() method."""

    def test_clear_all_returns_true_on_success(self):
        """Tests that clear_all_listings returns True on success."""
        result = self.db_manager.clear_all_listings()
        self.assertTrue(result)

    def test_clear_all_removes_all_listings(self):
        """Tests that clear_all_listings removes all listings."""
        for i in range(10):
            self.db_manager.save_listing(
                self._create_sample_listing(f"clear-all-{i}")
            )
        
        self.assertEqual(self.db_manager.count_listings(), 10)
        
        self.db_manager.clear_all_listings()
        
        self.assertEqual(self.db_manager.count_listings(), 0)

    def test_clear_all_on_empty_database(self):
        """Tests that clear_all_listings works on empty database."""
        result = self.db_manager.clear_all_listings()
        
        self.assertTrue(result)
        self.assertEqual(self.db_manager.count_listings(), 0)

    @patch('src.services.database.DatabaseManager._get_connection')
    def test_clear_all_returns_false_on_error(self, mock_conn):
        """Tests that clear_all_listings returns False on error."""
        mock_conn.side_effect = sqlite3.Error("Clear error")
        
        result = self.db_manager.clear_all_listings()
        
        self.assertFalse(result)


class TestDeleteOldListings(TestDatabaseManager):
    """Tests for DatabaseManager.delete_old_listings() method."""

    def test_delete_old_returns_zero_for_empty_database(self):
        """Tests that delete_old_listings returns 0 for empty database."""
        result = self.db_manager.delete_old_listings()
        self.assertEqual(result, 0)

    def test_delete_old_returns_zero_for_fresh_listings(self):
        """Tests that delete_old_listings returns 0 for fresh listings."""
        self.db_manager.save_listing(self._create_sample_listing("fresh"))
        
        result = self.db_manager.delete_old_listings(max_age_days=2)
        
        self.assertEqual(result, 0)
        self.assertEqual(self.db_manager.count_listings(), 1)

    def test_delete_old_accepts_custom_max_age(self):
        """Tests that delete_old_listings accepts custom max_age_days."""
        self.db_manager.save_listing(
            self._create_sample_listing("custom-age")
        )
        
        result = self.db_manager.delete_old_listings(max_age_days=7)
        
        self.assertEqual(result, 0)

    def test_delete_old_removes_expired_listings(self):
        """Tests that delete_old_listings removes expired listings."""
        # Insert a listing with manually set old timestamp
        conn = sqlite3.connect(self.temp_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO listings 
            (identifier, source, address, borough, sqm, price_cold, 
             price_total, rooms, wbs, link, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '-5 days'))
        """, (
            'old-listing', 'test', 'Old Address', 'Mitte', '50', 
            '500', '600', '2', 'No', 'https://example.com/old'
        ))
        conn.commit()
        conn.close()
        
        # Add a fresh listing
        self.db_manager.save_listing(self._create_sample_listing("fresh"))
        
        self.assertEqual(self.db_manager.count_listings(), 2)
        
        result = self.db_manager.delete_old_listings(max_age_days=2)
        
        self.assertEqual(result, 1)
        self.assertEqual(self.db_manager.count_listings(), 1)
        self.assertIsNotNone(
            self.db_manager.get_listing_by_identifier("fresh")
        )
        self.assertIsNone(
            self.db_manager.get_listing_by_identifier("old-listing")
        )

    @patch('src.services.database.DatabaseManager._get_connection')
    def test_delete_old_returns_zero_on_error(self, mock_conn):
        """Tests that delete_old_listings returns 0 on database error."""
        mock_conn.side_effect = sqlite3.Error("Delete old error")
        
        result = self.db_manager.delete_old_listings()
        
        self.assertEqual(result, 0)


class TestDatabaseManagerIntegration(TestDatabaseManager):
    """Integration tests for DatabaseManager operations."""

    def test_full_crud_workflow(self):
        """Tests complete create, read, update, delete workflow."""
        # Create
        listing = self._create_sample_listing("crud-test")
        self.assertTrue(self.db_manager.save_listing(listing))
        
        # Read
        loaded = self.db_manager.get_listing_by_identifier("crud-test")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.address, listing.address)
        
        # Update
        updated = Listing(
            identifier="crud-test",
            source="updated_source",
            address="Updated Address 123",
            borough="Neukölln",
            sqm="85",
            price_cold="900",
            price_total="1100",
            rooms="3",
            wbs="Yes",
            link="https://example.com/updated"
        )
        self.assertTrue(self.db_manager.save_listing(updated))
        loaded = self.db_manager.get_listing_by_identifier("crud-test")
        self.assertEqual(loaded.address, "Updated Address 123")
        
        # Delete
        self.assertTrue(self.db_manager.delete_listing("crud-test"))
        self.assertIsNone(
            self.db_manager.get_listing_by_identifier("crud-test")
        )

    def test_concurrent_operations(self):
        """Tests multiple operations in sequence."""
        # Save multiple listings
        for i in range(10):
            self.db_manager.save_listing(
                self._create_sample_listing(f"concurrent-{i}", "source_a")
            )
        
        # Delete some
        self.db_manager.delete_listings(
            [f"concurrent-{i}" for i in range(0, 10, 2)]
        )
        
        # Count remaining
        self.assertEqual(self.db_manager.count_listings(), 5)
        
        # Load all
        all_listings = self.db_manager.load_all_listings()
        self.assertEqual(len(all_listings), 5)
        
        # Get by source
        source_listings = self.db_manager.get_listings_by_source("source_a")
        self.assertEqual(len(source_listings), 5)

    def test_data_integrity_after_operations(self):
        """Tests that data remains consistent after multiple operations."""
        listings = {}
        for i in range(5):
            listing = self._create_sample_listing(f"integrity-{i}")
            listings[listing.identifier] = listing
        
        self.db_manager.save_listings(listings)
        
        # Update one
        updated = Listing(
            identifier="integrity-2",
            source="updated",
            address="New Address",
            borough="Charlottenburg",
            sqm="120",
            price_cold="1500",
            price_total="1800",
            rooms="5",
            wbs="WBS 180",
            link="https://example.com/integrity-2-updated"
        )
        self.db_manager.save_listing(updated)
        
        # Verify all data
        all_listings = self.db_manager.load_all_listings()
        self.assertEqual(len(all_listings), 5)
        
        # Check updated listing
        self.assertEqual(all_listings["integrity-2"].address, "New Address")
        
        # Check unchanged listings
        self.assertEqual(
            all_listings["integrity-0"].address,
            "Test Street 42, 12345 Berlin"
        )


if __name__ == '__main__':
    unittest.main()

