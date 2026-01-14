"""
Shared pytest fixtures and configuration for tests.

This module provides reusable fixtures that can be used across all test modules.
"""
import os
import tempfile
from typing import Dict

import pytest

from src.core.config import Config
from src.core.listing import Listing


@pytest.fixture
def sample_listing() -> Listing:
    """
    Creates a sample Listing object for testing.

    Returns:
        A Listing object with typical test data.
    """
    return Listing(
        identifier="https://example.com/listing/test-123",
        source="test_source",
        address="Test Street 42, 12345 Berlin",
        borough="Mitte",
        sqm="75.5",
        price_cold="800",
        price_total="1000",
        rooms="3",
        wbs="No",
    )


@pytest.fixture
def sample_listing_factory():
    """
    Factory fixture for creating sample listings with custom attributes.

    Returns:
        A function that creates Listing objects with specified attributes.
    """

    def _create_listing(
        identifier: str = "https://example.com/listing/test-123",
        source: str = "test_source",
        **kwargs,
    ) -> Listing:
        defaults = {
            "address": "Test Street 42, 12345 Berlin",
            "borough": "Mitte",
            "sqm": "75.5",
            "price_cold": "800",
            "price_total": "1000",
            "rooms": "3",
            "wbs": "No",
        }
        defaults.update(kwargs)
        return Listing(identifier=identifier, source=source, **defaults)

    return _create_listing


@pytest.fixture
def temp_db_path():
    """
    Creates a temporary database file path for testing.

    Yields:
        Path to a temporary database file.

    Cleanup:
        Removes the temporary file after the test.
    """
    temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_db_path = temp_db.name
    temp_db.close()

    yield temp_db_path

    if os.path.exists(temp_db_path):
        os.remove(temp_db_path)


@pytest.fixture
def valid_config_data() -> Dict:
    """
    Creates valid configuration data for testing.

    Returns:
        Dictionary with valid configuration structure.
    """
    return {
        "telegram": {"bot_token": "test_token_123", "chat_id": "test_chat_456"},
        "scrapers": {"test_scraper": {"enabled": True}},
        "poll_interval_seconds": 300,
        "filters": {"enabled": False},
    }


@pytest.fixture
def sample_config(valid_config_data) -> Config:
    """
    Creates a sample Config object for testing.

    Returns:
        A Config object with valid test configuration.
    """
    return Config(valid_config_data)


@pytest.fixture
def zip_to_borough_map() -> Dict:
    """
    Creates a sample zip-to-borough mapping for testing.

    Returns:
        Dictionary mapping zip codes to borough lists.
    """
    return {
        "10115": ["Mitte"],
        "10179": ["Mitte"],
        "10243": ["Friedrichshain"],
        "10961": ["Kreuzberg"],
        "12043": ["Neukölln"],
        "14050": ["Charlottenburg"],
    }
