"""
Borough resolution service for Berlin zip codes.

This module provides a centralized service for resolving Berlin zip codes
to their corresponding borough (Bezirk) names, eliminating code duplication
across the application.
"""
import json
import logging
import re
from typing import Dict, List, Optional

from src.core.constants import PLZ_BEZIRK_FILE

logger = logging.getLogger(__name__)


class BoroughResolver:
    """
    Resolves Berlin zip codes to borough names.
    
    This service loads and caches the zip-to-borough mapping from a JSON file
    and provides methods for looking up boroughs by zip code or address.
    
    Usage:
        resolver = BoroughResolver()
        borough = resolver.get_borough("10115")  # Returns "Mitte"
        boroughs = resolver.get_boroughs_from_address("Teststr. 1, 10115 Berlin")
    """

    def __init__(self, plz_file: str = PLZ_BEZIRK_FILE):
        """
        Initialize the resolver and load the zip-to-borough mapping.
        
        Args:
            plz_file: Path to the JSON file containing zip-to-borough mapping.
        """
        self._mapping: Dict[str, List[str]] = {}
        self._load_mapping(plz_file)

    def _load_mapping(self, plz_file: str) -> None:
        """
        Load the zip-to-borough mapping from a JSON file.
        
        Args:
            plz_file: Path to the JSON file.
        """
        try:
            with open(plz_file, 'r', encoding='utf-8') as f:
                self._mapping = json.load(f)
            logger.info(f"Loaded {len(self._mapping)} zip code mappings")
        except FileNotFoundError:
            logger.error(f"Borough mapping file not found: {plz_file}")
            self._mapping = {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse borough mapping file: {e}")
            self._mapping = {}

    @property
    def mapping(self) -> Dict[str, List[str]]:
        """
        Get the raw zip-to-borough mapping dictionary.
        
        Returns:
            Dictionary mapping zip codes to lists of borough names.
        """
        return self._mapping

    def is_loaded(self) -> bool:
        """
        Check if the mapping was successfully loaded.
        
        Returns:
            True if mapping contains entries, False otherwise.
        """
        return bool(self._mapping)

    def get_borough(self, zip_code: str) -> Optional[str]:
        """
        Get the primary borough name for a zip code.
        
        Supports both exact zip code matches and range patterns (e.g., "10115-10119").
        
        Args:
            zip_code: A 5-digit Berlin zip code.
            
        Returns:
            The primary borough name, or None if not found.
        """
        boroughs = self.get_all_boroughs(zip_code)
        return boroughs[0] if boroughs else None

    def get_all_boroughs(self, zip_code: str) -> Optional[List[str]]:
        """
        Get all borough names for a zip code.
        
        Some zip codes span multiple boroughs. This method returns all of them.
        
        Args:
            zip_code: A 5-digit Berlin zip code.
            
        Returns:
            List of borough names, or None if not found.
        """
        if not self._mapping:
            return None

        # Try exact match first
        if zip_code in self._mapping:
            return self._mapping[zip_code]

        # Try range patterns (e.g., "10115-10119")
        try:
            zip_int = int(zip_code)
            for pattern, boroughs in self._mapping.items():
                if '-' in pattern:
                    try:
                        start, end = map(int, pattern.split('-'))
                        if start <= zip_int <= end:
                            return boroughs
                    except ValueError:
                        continue
        except ValueError:
            pass

        return None

    def get_borough_or_default(self, zip_code: str, default: str = "N/A") -> str:
        """
        Get the primary borough name, with a default fallback.
        
        Args:
            zip_code: A 5-digit Berlin zip code.
            default: Value to return if borough is not found.
            
        Returns:
            The borough name or the default value.
        """
        borough = self.get_borough(zip_code)
        return borough if borough else default

    def get_boroughs_from_address(self, address: str) -> Optional[List[str]]:
        """
        Extract the zip code from an address and resolve to boroughs.
        
        Args:
            address: A street address potentially containing a 5-digit zip code.
            
        Returns:
            List of borough names, or None if no valid zip found.
        """
        if not self._mapping:
            logger.warning("Zip to borough map is not loaded")
            return None

        zip_code = self.extract_zipcode(address)
        if not zip_code:
            logger.debug(f"No zipcode found in address: {address}")
            return None

        return self.get_all_boroughs(zip_code)

    @staticmethod
    def extract_zipcode(address: str) -> Optional[str]:
        """
        Extract a 5-digit German zip code from an address string.
        
        Args:
            address: A string potentially containing a zip code.
            
        Returns:
            The 5-digit zip code if found, None otherwise.
        """
        match = re.search(r'\b\d{5}\b', address)
        return match.group(0) if match else None

    @staticmethod
    def format_boroughs(boroughs: List[str]) -> str:
        """
        Format a list of boroughs as a comma-separated string.
        
        Args:
            boroughs: List of borough names.
            
        Returns:
            Comma-separated borough string.
        """
        return ", ".join(boroughs)

