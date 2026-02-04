"""
Validation core module.

Contains base classes, interfaces, and utilities for the validation system.
"""

from modules.extraction.validation.core.base import BaseValidator, ValidationResult, ValidationSeverity
from modules.extraction.validation.core.registry import VALIDATOR_REGISTRY, register_validator, get_validator

__all__ = [
    'BaseValidator',
    'ValidationResult',
    'ValidationSeverity',
    'VALIDATOR_REGISTRY',
    'register_validator',
    'get_validator',
]
