"""
Centralized constants for the wohnung_scraper application.

This module provides a single source of truth for all application-wide
constants, including file paths, timing values, colors, and HTTP settings.
"""


# =============================================================================
# File Paths
# =============================================================================

PLZ_BEZIRK_FILE = 'data/plz_bezirk.json'
"""Path to the ZIP code to borough mapping file."""

DATABASE_FILE = 'listings.db'
"""Default path to the SQLite database file."""


# =============================================================================
# Timing Constants (in seconds)
# =============================================================================

SUSPENSION_SLEEP_SECONDS = 600
"""Sleep duration when service is in suspension period (10 minutes)."""

RATE_LIMIT_SLEEP_SECONDS = 1
"""Sleep between notifications to avoid Telegram rate limiting."""

DEFAULT_POLL_INTERVAL_SECONDS = 300
"""Default interval between scraping runs (5 minutes)."""

LISTING_MAX_AGE_DAYS = 30
"""Maximum age of listings before cleanup (in days)."""

REQUEST_TIMEOUT_SECONDS = 10
"""Default timeout for HTTP requests."""

APPLY_RETRY_DELAY_SECONDS = 300
"""Delay between application retry attempts (5 minutes)."""

APPLY_MAX_RETRIES = 6
"""Maximum number of retry attempts for failed applications."""


# =============================================================================
# Console Colors (ANSI escape codes)
# =============================================================================

class Colors:
    """
    ANSI color codes for console output.
    
    Usage:
        print(f"{Colors.GREEN}Success!{Colors.RESET}")
    """
    GREEN = "\033[92m"
    """Green text for success messages."""
    
    YELLOW = "\033[93m"
    """Yellow text for warning messages."""
    
    RED = "\033[91m"
    """Red text for error messages."""
    
    RESET = "\033[0m"
    """Reset to default terminal color."""


# =============================================================================
# HTTP Settings
# =============================================================================

DEFAULT_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/91.0.4472.124 Safari/537.36'
)
"""Default User-Agent header for HTTP requests."""

