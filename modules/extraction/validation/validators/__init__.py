"""
Validators module.

Contains all built-in validators organized by category:
- field_validators: Validators for individual fields
- advanced_validators: Cross-field and aggregate validators
- metadata_validators: Validators for extraction metadata
- accuracy_validators: Ground truth comparison validators

All validators are automatically registered via decorators.
"""

# Import all validators to trigger registration
from modules.extraction.validation.validators import field_validators
from modules.extraction.validation.validators import advanced_validators
from modules.extraction.validation.validators import metadata_validators
from modules.extraction.validation.validators import accuracy_validators

__all__ = ['field_validators', 'advanced_validators', 'metadata_validators', 'accuracy_validators']
