"""
This module defines the BaseScraper abstract base class.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Optional, TYPE_CHECKING

from src.core.constants import DEFAULT_USER_AGENT
from src.core.listing import Listing

if TYPE_CHECKING:
    from src.services import BoroughResolver


class BaseScraper(ABC):
    """Abstract base class for a scraper."""

    def __init__(self, name: str):
        self.name = name
        self.url: str = ""
        self.headers = {'User-Agent': DEFAULT_USER_AGENT}
        self.borough_resolver: Optional[BoroughResolver] = None

    def set_borough_resolver(self, borough_resolver: BoroughResolver) -> None:
        """
        Sets the borough resolver for the scraper.
        
        Args:
            borough_resolver: Service for resolving zip codes to boroughs.
        """
        self.borough_resolver = borough_resolver

    @abstractmethod
    def get_current_listings(
        self, known_listings: Optional[Dict[str, Listing]] = None
    ) -> Dict[str, Listing]:
        """Fetches the website and returns a dictionary of listings."""
        raise NotImplementedError

    def _get_borough_from_zip(self, zip_code: str) -> str:
        """
        Finds the borough for a given zip code.
        
        Args:
            zip_code: A 5-digit Berlin zip code.
            
        Returns:
            The borough name or "N/A" if not found.
        """
        if self.borough_resolver:
            return self.borough_resolver.get_borough_or_default(zip_code, "N/A")
        return "N/A"

    @staticmethod
    def _normalize_german_number(value_str: str) -> str:
        """
        Normalizes German number format to standard format.
        
        Converts German format (period as thousands, comma as decimal)
        to standard format (no thousands separator, period as decimal).
        
        Examples:
            '2.345' -> '2345' (thousands)
            '2.345,67' -> '2345.67' (thousands + decimal)
            '1.200' -> '1200'
            
        Args:
            value_str: Number string in German format
            
        Returns:
            Number string in standard format or original if not applicable
        """
        if not value_str or value_str == 'N/A':
            return value_str
            
        # German format uses period for thousands and comma for decimals
        # Remove thousands separators (periods) and convert decimal separator (comma to period)
        value_str = value_str.replace('.', '')  # Remove thousands separator
        value_str = value_str.replace(',', '.')  # Convert decimal separator
        
        return value_str

    @staticmethod
    def _normalize_rooms_format(value_str: str) -> str:
        """
        Normalizes room count format to use dot as decimal separator.
        
        Converts comma decimal separator to dot for consistent display
        (same format as prices).
        
        Examples:
            '2,5' -> '2.5' (comma to dot)
            '2.5' -> '2.5' (already correct)
            '3' -> '3' (whole number unchanged)
            
        Args:
            value_str: Room count string (may use dot or comma as decimal separator)
            
        Returns:
            Room count string with dot as decimal separator
        """
        if not value_str or value_str == 'N/A':
            return value_str
        
        # Replace comma with dot for decimal separator (same as prices)
        return value_str.replace(',', '.')

    def __str__(self):
        return f"Scraper({self.name})"
