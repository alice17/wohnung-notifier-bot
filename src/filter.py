"""
This module defines the ListingFilter class, which is responsible for filtering
apartment listings based on user-defined criteria.
"""
from __future__ import annotations

import logging
from typing import Optional, Dict, List, TYPE_CHECKING

from src.config import Config
from src.core.constants import Colors
from src.listing import Listing

if TYPE_CHECKING:
    from src.services import BoroughResolver

logger = logging.getLogger(__name__)


class ListingFilter:
    # pylint: disable=too-few-public-methods
    """Encapsulates all logic for filtering listings."""

    def __init__(self, config: Config, borough_resolver: Optional[BoroughResolver]):
        """
        Initialize the listing filter.
        
        Args:
            config: Application configuration containing filter rules.
            borough_resolver: Service for resolving zip codes to boroughs.
        """
        self.filters = config.filters
        self.borough_resolver = borough_resolver

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
        price_type = "Warm"
        price_to_log = listing.price_total

        if price_val is None:
            price_val = self._to_numeric(listing.price_cold)
            price_type = "Cold"
            price_to_log = listing.price_cold

        rules = self.filters.get("properties", {}).get("price_total", {})
        if not self._passes_numeric_filter(price_val, rules):
            logger.info(f"{Colors.YELLOW}FILTERED (Price {price_type}): {price_to_log}€{Colors.RESET}")
            return True
        return False

    def _is_filtered_by_sqm(self, listing: Listing) -> bool:
        sqm_val = self._to_numeric(listing.sqm)
        rules = self.filters.get("properties", {}).get("sqm", {})
        if not self._passes_numeric_filter(sqm_val, rules):
            logger.info(f"{Colors.YELLOW}FILTERED (SQM): {listing.sqm}m²{Colors.RESET}")
            return True
        return False

    def _is_filtered_by_rooms(self, listing: Listing) -> bool:
        rooms_val = self._to_numeric(listing.rooms)
        rules = self.filters.get("properties", {}).get("rooms", {})
        if not self._passes_numeric_filter(rooms_val, rules):
            logger.info(f"{Colors.YELLOW}FILTERED (Rooms): {listing.rooms}{Colors.RESET}")
            return True
        return False

    def _is_filtered_by_wbs(self, listing: Listing) -> bool:
        rules = self.filters.get("properties", {}).get("wbs", {})
        allowed_values = rules.get("allowed_values", [])
        if allowed_values and listing.wbs.strip().lower() not in [v.lower() for v in allowed_values]:
            logger.info(f"{Colors.YELLOW}FILTERED (WBS): '{listing.wbs}'{Colors.RESET}")
            return True
        return False

    def _is_filtered_by_borough(self, listing: Listing) -> bool:
        rules = self.filters.get("properties", {}).get("boroughs", {})
        allowed_boroughs = rules.get("allowed_values", [])
        if not allowed_boroughs:
            return False

        if not self.borough_resolver:
            logger.warning("Borough resolver not available. Cannot filter by borough.")
            return False

        listing_boroughs = self.borough_resolver.get_boroughs_from_address(listing.address)
        if listing_boroughs:
            listing.borough = self.borough_resolver.format_boroughs(listing_boroughs)
            allowed_set = {b.lower() for b in allowed_boroughs}
            if not any(b.lower() in allowed_set for b in listing_boroughs):
                logger.info(
                    f"{Colors.YELLOW}FILTERED (Borough): "
                    f"'{listing.borough}' not in allowed boroughs.{Colors.RESET}"
                )
                return True
        else:
            logger.info(
                f"Borough: Could not determine borough for address "
                f"'{listing.address}'. Sending it anyway."
            )
            return False
        return False

    @staticmethod
    def _to_numeric(value_str: str) -> Optional[float]:
        """
        Converts a string to a numeric value.
        
        Expects standard format (period as decimal separator, no thousands separators)
        since all scrapers normalize their numbers before passing to the filter.
        
        Examples:
            '1234.56' -> 1234.56
            '850' -> 850.0
            '679.45' -> 679.45
        
        Args:
            value_str: String representation of a number in standard format
            
        Returns:
            Float value or None if conversion fails
        """
        if not isinstance(value_str, str) or value_str == 'N/A':
            return None
        
        try:
            return float(value_str.strip())
        except (ValueError, TypeError):
            return None
