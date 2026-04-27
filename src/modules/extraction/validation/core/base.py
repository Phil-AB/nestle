"""
Base classes and data models for validation system.

This module provides the foundation for all validators:
- BaseValidator: Abstract base class for all validators
- ValidationResult: Standard result format
- ValidationSeverity: Severity levels
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field as dataclass_field, asdict
from enum import Enum
from datetime import datetime


class ValidationSeverity(str, Enum):
    """Severity levels for validation results"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """
    Standard validation result format.
    
    All validators must return this format for consistency.
    """
    # Core fields
    passed: bool
    validator_name: str
    severity: ValidationSeverity
    message: str
    
    # Optional context
    field: Optional[str] = None
    rule_name: Optional[str] = None
    layer: Optional[str] = None  # data_quality, business_rules, cross_document, compliance, accuracy
    
    # Value information
    actual_value: Any = None
    expected_value: Any = None
    
    # Metadata
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = dataclass_field(default_factory=dict)
    timestamp: datetime = dataclass_field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        # Convert enum to string
        data['severity'] = self.severity.value
        # Convert datetime to ISO format
        data['timestamp'] = self.timestamp.isoformat()
        return data


class BaseValidator(ABC):
    """
    Abstract base class for all validators.
    
    All custom validators must inherit from this class and implement
    the validate() method.
    
    Example:
        @register_validator("my_custom_validator")
        class MyValidator(BaseValidator):
            async def validate(self, data: Dict, context: Optional[Dict] = None) -> ValidationResult:
                # Validation logic here
                return ValidationResult(passed=True, ...)
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize validator with configuration.
        
        Args:
            config: Configuration dictionary from YAML/JSON
                    Contains validator-specific settings like field, params, severity, etc.
        """
        self.config = config
        self.severity = ValidationSeverity(config.get('severity', 'error'))
        self.field = config.get('field')
        self.message_template = config.get('message', '')
    
    @abstractmethod
    async def validate(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Execute validation logic.
        
        Args:
            data: Document data to validate
                  Format: {"field1": "value1", "field2": 123, "items": [...]}
            context: Optional context for cross-document validation
                     Format: {"related_documents": [...], "reference_data": {...}}
        
        Returns:
            ValidationResult object
        
        Raises:
            ValidationError: If validation logic encounters an error
        """
        pass
    
    def _get_field_value(self, data: Dict, field_path: str) -> Any:
        """
        Get field value from data using dot notation.
        
        Supports nested fields: "address.city", "items.0.name"
        
        Args:
            data: Data dictionary
            field_path: Field path in dot notation
        
        Returns:
            Field value or None if not found
        """
        try:
            keys = field_path.split('.')
            value = data
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                elif isinstance(value, list) and key.isdigit():
                    value = value[int(key)]
                else:
                    return None
                
                if value is None:
                    return None
            
            return value
        except (KeyError, IndexError, AttributeError, TypeError):
            return None
    
    def _set_field_value(self, data: Dict, field_path: str, value: Any) -> None:
        """
        Set field value in data using dot notation.
        
        Args:
            data: Data dictionary (modified in place)
            field_path: Field path in dot notation
            value: Value to set
        """
        keys = field_path.split('.')
        current = data
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def _create_result(
        self,
        passed: bool,
        message: str = "",
        actual_value: Any = None,
        expected_value: Any = None,
        **kwargs
    ) -> ValidationResult:
        """
        Helper to create ValidationResult with common fields.
        
        Args:
            passed: Whether validation passed
            message: Validation message (uses template if not provided)
            actual_value: Actual value found
            expected_value: Expected value
            **kwargs: Additional fields for ValidationResult
        
        Returns:
            ValidationResult object
        """
        return ValidationResult(
            passed=passed,
            validator_name=self.__class__.__name__.replace('Validator', '').lower(),
            severity=self.severity,
            message=message or self.message_template,
            field=self.field,
            actual_value=actual_value,
            expected_value=expected_value,
            **kwargs
        )


class ValidationError(Exception):
    """Exception raised when validation logic encounters an error"""
    pass
