"""
Core module containing domain models, constants, and configuration.
"""
from src.core.config import Config
from src.core.constants import (
    Colors,
    PLZ_BEZIRK_FILE,
    DATABASE_FILE,
    SUSPENSION_SLEEP_SECONDS,
    RATE_LIMIT_SLEEP_SECONDS,
    DEFAULT_POLL_INTERVAL_SECONDS,
    LISTING_MAX_AGE_DAYS,
    REQUEST_TIMEOUT_SECONDS,
    DEFAULT_USER_AGENT,
)
from src.core.listing import Listing

__all__ = [
    "Config",
    "Colors",
    "PLZ_BEZIRK_FILE",
    "DATABASE_FILE",
    "SUSPENSION_SLEEP_SECONDS",
    "RATE_LIMIT_SLEEP_SECONDS",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "LISTING_MAX_AGE_DAYS",
    "REQUEST_TIMEOUT_SECONDS",
    "DEFAULT_USER_AGENT",
    "Listing",
]

