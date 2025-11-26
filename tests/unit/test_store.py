"""
This module contains tests for the ListingStore class.
"""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.listing import Listing
from src.store import ListingStore


class TestListingStore(unittest.TestCase):
    """Test suite for the ListingStore class."""

    def setUp(self):
        """Set up a temporary database for each test."""
        self.temp_db = tempfile.NamedTemporaryFile(
            suffix='.db',
            delete=False
        )
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        self.store = ListingStore(self.temp_db_path)

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
            link="https://example.com/listing/test-123"
        )


class TestListingStoreInitialization(TestListingStore):
    """Tests for ListingStore initialization."""

    def test_init_creates_store_with_default_path(self):
        """Tests that ListingStore initializes with a DatabaseManager."""
        self.assertIsNotNone(self.store.db_manager)
        self.assertEqual(self.store.db_manager.db_path, self.temp_db_path)

    def test_init_creates_database_file(self):
        """Tests that initialization creates the database file."""
        self.assertTrue(os.path.exists(self.temp_db_path))

    @patch('src.store.DatabaseManager')
    def test_init_logs_database_path(self, mock_db_manager):
        """Tests that initialization logs the database path."""
        with patch('src.store.logger') as mock_logger:
            ListingStore("custom_path.db")
            mock_logger.info.assert_called()


class TestListingStoreLoad(TestListingStore):
    """Tests for ListingStore.load() method."""

    def test_load_returns_empty_dict_when_no_listings(self):
        """Tests that load returns empty dict for empty database."""
        listings = self.store.load()
        self.assertEqual(listings, {})

    def test_load_returns_saved_listings(self):
        """Tests that load returns previously saved listings."""
        sample_listing = self._create_sample_listing()
        listings_to_save = {sample_listing.identifier: sample_listing}
        
        self.store.save(listings_to_save)
        loaded_listings = self.store.load()
        
        self.assertEqual(len(loaded_listings), 1)
        self.assertIn(sample_listing.identifier, loaded_listings)
        loaded = loaded_listings[sample_listing.identifier]
        self.assertEqual(loaded.address, sample_listing.address)
        self.assertEqual(loaded.borough, sample_listing.borough)
        self.assertEqual(loaded.sqm, sample_listing.sqm)

    def test_load_returns_multiple_listings(self):
        """Tests that load correctly returns multiple listings."""
        listing_one = self._create_sample_listing("listing-1", "source_a")
        listing_two = self._create_sample_listing("listing-2", "source_b")
        listings_to_save = {
            listing_one.identifier: listing_one,
            listing_two.identifier: listing_two
        }
        
        self.store.save(listings_to_save)
        loaded_listings = self.store.load()
        
        self.assertEqual(len(loaded_listings), 2)
        self.assertIn("listing-1", loaded_listings)
        self.assertIn("listing-2", loaded_listings)

    @patch('src.store.DatabaseManager')
    def test_load_returns_empty_dict_on_database_error(
        self,
        mock_db_manager_class
    ):
        """Tests that load returns empty dict when database raises error."""
        mock_db_manager = MagicMock()
        mock_db_manager.load_all_listings.side_effect = Exception(
            "Database error"
        )
        mock_db_manager_class.return_value = mock_db_manager
        
        store = ListingStore("error_test.db")
        result = store.load()
        
        self.assertEqual(result, {})


class TestListingStoreSave(TestListingStore):
    """Tests for ListingStore.save() method."""

    def test_save_persists_single_listing(self):
        """Tests that save persists a single listing to database."""
        sample_listing = self._create_sample_listing()
        listings = {sample_listing.identifier: sample_listing}
        
        self.store.save(listings)
        
        loaded = self.store.load()
        self.assertEqual(len(loaded), 1)
        self.assertIn(sample_listing.identifier, loaded)

    def test_save_persists_multiple_listings(self):
        """Tests that save persists multiple listings."""
        listings = {}
        for i in range(5):
            listing = self._create_sample_listing(f"listing-{i}")
            listings[listing.identifier] = listing
        
        self.store.save(listings)
        
        loaded = self.store.load()
        self.assertEqual(len(loaded), 5)

    def test_save_empty_dict_does_not_error(self):
        """Tests that saving an empty dict doesn't cause errors."""
        self.store.save({})
        loaded = self.store.load()
        self.assertEqual(loaded, {})

    def test_save_updates_existing_listing(self):
        """Tests that save updates an existing listing."""
        original_listing = self._create_sample_listing("update-test")
        self.store.save({original_listing.identifier: original_listing})
        
        updated_listing = Listing(
            identifier="update-test",
            source="test_source",
            address="New Address 99, 99999 Berlin",
            borough="Kreuzberg",
            sqm="100",
            price_cold="1200",
            price_total="1500",
            rooms="4",
            wbs="Yes",
            link="https://example.com/listing/updated"
        )
        self.store.save({updated_listing.identifier: updated_listing})
        
        loaded = self.store.load()
        self.assertEqual(len(loaded), 1)
        loaded_listing = loaded["update-test"]
        self.assertEqual(loaded_listing.address, "New Address 99, 99999 Berlin")
        self.assertEqual(loaded_listing.borough, "Kreuzberg")
        self.assertEqual(loaded_listing.sqm, "100")

    @patch('src.store.DatabaseManager')
    def test_save_handles_database_error_gracefully(
        self,
        mock_db_manager_class
    ):
        """Tests that save handles database errors without raising."""
        mock_db_manager = MagicMock()
        mock_db_manager.save_listings.side_effect = Exception("Save failed")
        mock_db_manager_class.return_value = mock_db_manager
        
        store = ListingStore("error_test.db")
        sample_listing = self._create_sample_listing()
        
        # Should not raise an exception
        store.save({sample_listing.identifier: sample_listing})


class TestListingStoreCleanup(TestListingStore):
    """Tests for ListingStore.cleanup_old_listings() method."""

    def test_cleanup_returns_zero_for_empty_database(self):
        """Tests that cleanup returns 0 when database is empty."""
        deleted_count = self.store.cleanup_old_listings()
        self.assertEqual(deleted_count, 0)

    def test_cleanup_returns_zero_for_fresh_listings(self):
        """Tests that cleanup returns 0 when all listings are fresh."""
        sample_listing = self._create_sample_listing()
        self.store.save({sample_listing.identifier: sample_listing})
        
        deleted_count = self.store.cleanup_old_listings(max_age_days=2)
        
        self.assertEqual(deleted_count, 0)
        loaded = self.store.load()
        self.assertEqual(len(loaded), 1)

    def test_cleanup_accepts_custom_max_age(self):
        """Tests that cleanup accepts custom max_age_days parameter."""
        sample_listing = self._create_sample_listing()
        self.store.save({sample_listing.identifier: sample_listing})
        
        # Fresh listing should not be deleted even with custom max_age
        deleted_count = self.store.cleanup_old_listings(max_age_days=7)
        
        self.assertEqual(deleted_count, 0)

    def test_cleanup_delegates_to_database_manager(self):
        """Tests that cleanup calls db_manager.delete_old_listings()."""
        with patch.object(
            self.store.db_manager,
            'delete_old_listings',
            return_value=5
        ) as mock_delete:
            result = self.store.cleanup_old_listings(max_age_days=3)
            
            mock_delete.assert_called_once_with(3)
            self.assertEqual(result, 5)


class TestListingStoreIntegration(TestListingStore):
    """Integration tests for ListingStore workflow."""

    def test_save_load_roundtrip_preserves_data(self):
        """Tests that save and load correctly preserve all listing data."""
        original_listing = Listing(
            identifier="roundtrip-test",
            source="integration_source",
            address="Integration Street 1, 10115 Berlin",
            borough="Prenzlauer Berg",
            sqm="85.5",
            price_cold="950",
            price_total="1150",
            rooms="3.5",
            wbs="WBS 140",
            link="https://example.com/roundtrip-test"
        )
        
        self.store.save({original_listing.identifier: original_listing})
        loaded_listings = self.store.load()
        loaded_listing = loaded_listings[original_listing.identifier]
        
        self.assertEqual(loaded_listing.source, original_listing.source)
        self.assertEqual(loaded_listing.address, original_listing.address)
        self.assertEqual(loaded_listing.borough, original_listing.borough)
        self.assertEqual(loaded_listing.sqm, original_listing.sqm)
        self.assertEqual(loaded_listing.price_cold, original_listing.price_cold)
        self.assertEqual(loaded_listing.price_total, original_listing.price_total)
        self.assertEqual(loaded_listing.rooms, original_listing.rooms)
        self.assertEqual(loaded_listing.wbs, original_listing.wbs)
        self.assertEqual(loaded_listing.link, original_listing.link)

    def test_multiple_save_operations_merge_correctly(self):
        """Tests that multiple save operations merge listings correctly."""
        listing_one = self._create_sample_listing("batch-1", "source_a")
        listing_two = self._create_sample_listing("batch-2", "source_a")
        listing_three = self._create_sample_listing("batch-3", "source_b")
        
        self.store.save({listing_one.identifier: listing_one})
        self.store.save({listing_two.identifier: listing_two})
        self.store.save({listing_three.identifier: listing_three})
        
        loaded = self.store.load()
        
        self.assertEqual(len(loaded), 3)
        self.assertIn("batch-1", loaded)
        self.assertIn("batch-2", loaded)
        self.assertIn("batch-3", loaded)

    def test_store_with_listings_from_different_sources(self):
        """Tests that store handles listings from different sources."""
        sources = ["degewo", "wbm", "deutschewohnen", "immowelt"]
        listings = {}
        
        for idx, source in enumerate(sources):
            listing = self._create_sample_listing(f"{source}-listing", source)
            listings[listing.identifier] = listing
        
        self.store.save(listings)
        loaded = self.store.load()
        
        self.assertEqual(len(loaded), len(sources))
        for source in sources:
            self.assertIn(f"{source}-listing", loaded)
            self.assertEqual(loaded[f"{source}-listing"].source, source)


if __name__ == '__main__':
    unittest.main()

