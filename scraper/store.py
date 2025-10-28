import json
import logging
import os
from typing import Set

logger = logging.getLogger(__name__)


class ListingStore:
    """Manages the persistence of known listing identifiers."""

    def __init__(self, filepath: str = "known_listings_by_url.json"):
        self.filepath = filepath

    def load(self) -> Set[str]:
        """Loads the set of known listing identifiers from the file."""
        if not os.path.exists(self.filepath):
            return set()
        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
                return set(data.get("listing_urls", []))
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading {self.filepath}: {e}. Starting fresh.")
            return set()

    def save(self, listing_ids: Set[str]):
        """Saves the current set of listing identifiers to the file."""
        try:
            with open(self.filepath, 'w') as f:
                json.dump({"listing_urls": sorted(list(listing_ids))}, f, indent=2)
        except IOError as e:
            logger.error(f"Error writing to {self.filepath}: {e}")
