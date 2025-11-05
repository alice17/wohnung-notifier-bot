"""
This module defines the ListingStore class for persistence of listings.
"""
import json
import logging
import os
from typing import Dict
from dataclasses import asdict, is_dataclass

from scraper.listing import Listing

logger = logging.getLogger(__name__)


class EnhancedJSONEncoder(json.JSONEncoder):
    """A JSON encoder that can handle dataclasses."""
    def default(self, o):
        if is_dataclass(o):
            return asdict(o)
        return super().default(o)


class ListingStore:
    """Manages the persistence of known listing identifiers."""

    def __init__(self, filepath: str = "known_listings_by_url.json"):
        self.filepath = filepath

    def load(self) -> Dict[str, Listing]:
        """Loads the set of known listing identifiers from the file."""
        if not os.path.exists(self.filepath):
            return {}
        try:
            with open(self.filepath, 'r', encoding="utf-8") as f:
                data = json.load(f)
                return {
                    identifier: Listing(**listing_data)
                    for identifier, listing_data in data.items()
                }
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading {self.filepath}: {e}. Starting fresh.")
            return {}

    def save(self, listings: Dict[str, Listing]):
        """Saves the current set of listing identifiers to the file."""
        try:
            with open(self.filepath, 'w', encoding="utf-8") as f:
                json.dump(listings, f, indent=2, cls=EnhancedJSONEncoder)
        except IOError as e:
            logger.error(f"Error writing to {self.filepath}: {e}")
