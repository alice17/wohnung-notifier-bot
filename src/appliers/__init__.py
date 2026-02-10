"""
Auto-application handlers for various housing providers.

This package contains applier classes that can automatically submit
applications to apartment listing websites on behalf of the user.
"""
from src.appliers.base import BaseApplier, ApplyResult, ApplyStatus
from src.appliers.berlinovo import BerlinovoApplier
from src.appliers.wbm import WBMApplier

# Registry mapping applier names to their classes (mirrors SCRAPER_CLASSES pattern)
APPLIER_CLASSES = {
    "berlinovo": BerlinovoApplier,
    "wbm": WBMApplier,
}

__all__ = [
    "BaseApplier",
    "ApplyResult",
    "ApplyStatus",
    "BerlinovoApplier",
    "WBMApplier",
    "APPLIER_CLASSES",
]

