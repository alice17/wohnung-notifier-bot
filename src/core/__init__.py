"""
Core module containing domain models, constants, and shared utilities.
"""
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

__all__ = [
    "Colors",
    "PLZ_BEZIRK_FILE",
    "DATABASE_FILE",
    "SUSPENSION_SLEEP_SECONDS",
    "RATE_LIMIT_SLEEP_SECONDS",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "LISTING_MAX_AGE_DAYS",
    "REQUEST_TIMEOUT_SECONDS",
    "DEFAULT_USER_AGENT",
]

