"""Statistical validators"""

# Import validators to trigger auto-registration
from .tolerance_validator import ToleranceValidator

__all__ = [
    "ToleranceValidator",
]
