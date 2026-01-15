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
    """
    Represents a single apartment listing with its details.

    The identifier field serves as both the unique key and the URL to the listing.
    For listings with a valid URL, the identifier IS the URL. For listings without
    a URL, a hash-based fallback identifier is generated.
    """

    source: str
    address: str = "N/A"
    borough: str = "N/A"
    sqm: str = "N/A"
    price_cold: str = "N/A"
    price_total: str = "N/A"
    rooms: str = "N/A"
    wbs: bool = False
    identifier: Optional[str] = None

    def __post_init__(self):
        """Generate a fallback identifier if not provided."""
        if not self.identifier:
            self.identifier = self._generate_fallback_id()
            logger.warning(
                f"No URL provided for listing. Using fallback ID: {self.identifier}"
            )

    def _generate_fallback_id(self) -> str:
        """
        Generates a hash-based identifier when no URL is available.

        Returns:
            A 16-character hash based on listing details.
        """
        key_info = (
            f"{self.address}-{self.sqm}-{self.price_cold}-"
            f"{self.price_total}-{self.rooms}-{self.wbs}"
        )
        return hashlib.sha256(key_info.encode("utf-8")).hexdigest()[:16]

    @property
    def url(self) -> str:
        """
        Returns the listing URL.

        For most listings, identifier is the URL. This property provides
        a semantic alias for readability.

        Returns:
            The listing URL or 'N/A' if identifier is a fallback hash.
        """
        if self.identifier and self.identifier.startswith("http"):
            return self.identifier
        return "N/A"
