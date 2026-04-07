"""Validators for validation engine"""

from .validator_registry import ValidatorRegistry, get_validator_registry

# Import validator modules to trigger auto-registration
from . import rule_based
from . import statistical
from . import cross_document
from . import ai_based

__all__ = [
    "ValidatorRegistry",
    "get_validator_registry",
]
