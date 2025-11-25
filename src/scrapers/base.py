"""
This module defines the BaseScraper abstract base class.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, List

from src.listing import Listing


class BaseScraper(ABC):
    """Abstract base class for a scraper."""

    def __init__(self, name: str):
        self.name = name
        self.url: str = ""
        self.headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/91.0.4472.124 Safari/537.36'
            )
        }
        self.zip_to_borough_map: Optional[Dict[str, List[str]]] = None

    def set_zip_to_borough_map(self, zip_to_borough_map: Dict[str, List[str]]):
        """Sets the zip to borough map for the scraper."""
        self.zip_to_borough_map = zip_to_borough_map

    @abstractmethod
    def get_current_listings(
        self, known_listings: Optional[Dict[str, Listing]] = None
    ) -> Dict[str, Listing]:
        """Fetches the website and returns a dictionary of listings."""
        raise NotImplementedError

    def _get_borough_from_zip(self, zip_code: str) -> str:
        """Finds the borough for a given zip code from the mapping."""
        if self.zip_to_borough_map:
            for zip_pattern, borough_list in self.zip_to_borough_map.items():
                if '-' in zip_pattern:
                    try:
                        start, end = map(int, zip_pattern.split('-'))
                        if start <= int(zip_code) <= end:
                            return borough_list[0] if borough_list else "Unknown"
                    except ValueError:
                        continue  # Ignore invalid patterns
                elif zip_code == zip_pattern:
                    return borough_list[0] if borough_list else "Unknown"
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

    def __str__(self):
        return f"Scraper({self.name})"
