"""
This module defines the Listing dataclass.
"""
import hashlib
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Listing:
    """Represents a single apartment listing with its details."""
    source: str
    address: str = "N/A"
    borough: str = "N/A"
    sqm: str = "N/A"
    price_cold: str = "N/A"
    price_total: str = "N/A"
    rooms: str = "N/A"
    wbs: str = "N/A"
    link: str = "N/A"
    identifier: Optional[str] = None

    def __post_init__(self):
        """Generate a fallback identifier if a link is not provided."""
        if not self.identifier:
            self.identifier = self.generate_fallback_id()
            logger.warning(f"No deeplink found for a listing. Using fallback ID: {self.identifier}")

    def generate_fallback_id(self) -> str:
        """Generates a hash based on key details if a URL is missing."""
        key_info = (
            f"{self.address}-{self.sqm}-{self.price_cold}-"
            f"{self.price_total}-{self.rooms}-{self.wbs}"
        )
        return hashlib.sha256(key_info.encode('utf-8')).hexdigest()[:16]
