"""
Base class for auto-application handlers.

This module defines the abstract base class that all appliers must implement,
providing a consistent interface for automatically applying to listings.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List

from src.core.listing import Listing


class ApplyStatus(Enum):
    """Enumeration of possible application result statuses."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    FORM_NOT_FOUND = "form_not_found"
    MISSING_CONFIG = "missing_config"
    LISTING_UNAVAILABLE = "listing_unavailable"


@dataclass
class ApplyResult:
    """
    Result of an application attempt.
    
    Attributes:
        status: The outcome status of the application.
        message: Human-readable description of the result.
        applicant_data: Data that was submitted (for logging/notification).
    """
    status: ApplyStatus
    message: str
    applicant_data: Dict[str, Any] = None

    @property
    def is_success(self) -> bool:
        """Check if the application was successful."""
        return self.status == ApplyStatus.SUCCESS


class BaseApplier(ABC):
    """
    Abstract base class for auto-application handlers.
    
    Subclasses should implement the URL matching logic and the actual
    application submission process for specific housing providers.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the applier with configuration.
        
        Args:
            config: Provider-specific configuration dictionary containing
                    applicant information and settings.
        """
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return the human-readable name of this applier.
        
        Returns:
            Name string identifying this applier (e.g., "WBM", "Degewo").
        """

    @property
    @abstractmethod
    def url_patterns(self) -> List[str]:
        """
        Return URL patterns this applier handles.
        
        Returns:
            List of URL prefixes that this applier can process.
        """

    def can_apply(self, listing: Listing) -> bool:
        """
        Check if this applier can handle the given listing.
        
        Args:
            listing: The listing to check.
            
        Returns:
            True if this applier handles the listing's URL, False otherwise.
        """
        if not listing.url or listing.url == "N/A":
            return False
        return any(listing.url.startswith(pattern) for pattern in self.url_patterns)

    def is_configured(self) -> bool:
        """
        Check if the applier has valid configuration.
        
        Returns:
            True if configuration is present and valid, False otherwise.
        """
        return bool(self.config)

    @abstractmethod
    def apply(self, listing: Listing) -> ApplyResult:
        """
        Submit an application for the given listing.
        
        Args:
            listing: The listing to apply for.
            
        Returns:
            ApplyResult containing the outcome and details of the application.
        """

