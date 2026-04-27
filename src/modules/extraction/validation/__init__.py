"""
Validation service module.

Provides universal validation functionality for document data.

Main components:
- ValidationEngine: Main orchestrator for validation
- BaseValidator: Base class for all validators
- Built-in validators: field, advanced, metadata validators

Usage:
    from modules.extraction.validation import ValidationEngine
    
    engine = ValidationEngine()
    result = await engine.validate("document_type", data, context)
    
    if result.passed:
        print("Validation passed!")
    else:
        for error in result.results:
            if not error['passed']:
                print(f"Error: {error['message']}")
"""

from modules.extraction.validation.engine import ValidationEngine, DocumentValidationResult, ValidationSummary
from modules.extraction.validation.core.base import BaseValidator, ValidationResult, ValidationSeverity
from modules.extraction.validation.core.registry import register_validator, VALIDATOR_REGISTRY

__all__ = [
    'ValidationEngine',
    'DocumentValidationResult',
    'ValidationSummary',
    'BaseValidator',
    'ValidationResult',
    'ValidationSeverity',
    'register_validator',
    'VALIDATOR_REGISTRY',
]
