import logging
import re
from typing import Optional, Dict, List

from scraper.config import Config
from scraper.listing import Listing

logger = logging.getLogger(__name__)


class ListingFilter:
    """Encapsulates all logic for filtering listings."""

    def __init__(self, config: Config, zip_to_borough_map: Optional[Dict[str, List[str]]]):
        self.filters = config.filters
        self.zip_to_borough_map = zip_to_borough_map

    def is_filtered(self, listing: Listing) -> bool:
        """Checks if a listing should be filtered out based on any criteria."""
        if not self.filters.get("enabled", False):
            return False

        if self._is_filtered_by_price(listing):
            return True
        if self._is_filtered_by_sqm(listing):
            return True
        if self._is_filtered_by_rooms(listing):
            return True
        if self._is_filtered_by_wbs(listing):
            return True
        if self._is_filtered_by_borough(listing):
            return True

        return False

    def _passes_numeric_filter(self, value: Optional[float], rules: Dict[str, float]) -> bool:
        if value is None:
            return True
        if rules.get("min") is not None and value < rules["min"]:
            return False
        if rules.get("max") is not None and value > rules["max"]:
            return False
        return True

    def _is_filtered_by_price(self, listing: Listing) -> bool:
        price_val = self._to_numeric(listing.price_total)
        rules = self.filters.get("properties", {}).get("price_total", {})
        if not self._passes_numeric_filter(price_val, rules):
            logger.debug(f"FILTERED (Price): {listing.price_total}€")
            return True
        return False

    def _is_filtered_by_sqm(self, listing: Listing) -> bool:
        sqm_val = self._to_numeric(listing.sqm)
        rules = self.filters.get("properties", {}).get("sqm", {})
        if not self._passes_numeric_filter(sqm_val, rules):
            logger.debug(f"FILTERED (SQM): {listing.sqm}m²")
            return True
        return False

    def _is_filtered_by_rooms(self, listing: Listing) -> bool:
        rooms_val = self._to_numeric(listing.rooms)
        rules = self.filters.get("properties", {}).get("rooms", {})
        if not self._passes_numeric_filter(rooms_val, rules):
            logger.debug(f"FILTERED (Rooms): {listing.rooms}")
            return True
        return False

    def _is_filtered_by_wbs(self, listing: Listing) -> bool:
        rules = self.filters.get("properties", {}).get("wbs", {})
        allowed_values = rules.get("allowed_values", [])
        if allowed_values and listing.wbs.strip().lower() not in [v.lower() for v in allowed_values]:
            logger.debug(f"FILTERED (WBS): '{listing.wbs}'")
            return True
        return False

    def _is_filtered_by_borough(self, listing: Listing) -> bool:
        rules = self.filters.get("properties", {}).get("boroughs", {})
        allowed_boroughs = rules.get("allowed_values", [])
        if not allowed_boroughs:
            return False

        listing_boroughs = self._get_boroughs_from_address(listing.address)
        if listing_boroughs:
            listing.borough = ", ".join(listing_boroughs)
            allowed_set = {b.lower() for b in allowed_boroughs}
            if not any(b.lower() in allowed_set for b in listing_boroughs):
                logger.debug(f"FILTERED (Borough): '{listing.borough}' not in allowed boroughs.")
                return True
        else:
            logger.debug(f"FILTERED (Borough): Could not determine borough for address '{listing.address}'.")
            return True
        return False

    def _get_boroughs_from_address(self, address: str) -> Optional[List[str]]:
        if not self.zip_to_borough_map:
            logger.warning("Zip to borough map is not loaded. Cannot determine borough.")
            return None

        zipcode = self._extract_zipcode(address)
        if not zipcode:
            logger.debug(f"No zipcode found in address: {address}")
            return None
        return self.zip_to_borough_map.get(zipcode)

    @staticmethod
    def _extract_zipcode(address: str) -> Optional[str]:
        match = re.search(r'\b\d{5}\b', address)
        return match.group(0) if match else None

    @staticmethod
    def _to_numeric(value_str: str) -> Optional[float]:
        if not isinstance(value_str, str) or value_str == 'N/A':
            return None
        try:
            return float(value_str.replace('.', '').replace(',', '.'))
        except (ValueError, TypeError):
            return None
