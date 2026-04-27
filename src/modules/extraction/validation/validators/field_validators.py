"""
Field validators module.

Contains validators that operate on individual fields:
- RequiredValidator: Check if field exists and is not empty
- PatternValidator: Validate against regex pattern
- TypeCheckValidator: Validate data type
- RangeValidator: Validate numeric range
- LengthValidator: Validate string/array length
- EnumValidator: Validate value is in allowed list
"""

import re
from typing import Any, Dict, Optional, List
from datetime import datetime
from modules.extraction.validation.core.base import BaseValidator, ValidationResult
from modules.extraction.validation.core.registry import register_validator


@register_validator("required")
class RequiredValidator(BaseValidator):
    """
    Validate that a field exists and is not null/empty.
    
    Configuration:
        field: "field_name"
        severity: "error"  # optional
        message: "Custom message"  # optional
    
    Example:
        - validator: required
          field: customer_id
          severity: error
    """
    
    async def validate(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        value = self._get_field_value(data, self.field)
        
        # Check if value exists and is not empty
        passed = value is not None and value != ""
        
        # Handle empty lists/dicts
        if isinstance(value, (list, dict)) and len(value) == 0:
            passed = False
        
        message = self.message_template or f"Field '{self.field}' is required"
        
        return self._create_result(
            passed=passed,
            message=message if not passed else "",
            actual_value=value,
            layer="data_quality"
        )


@register_validator("pattern")
class PatternValidator(BaseValidator):
    """
    Validate field value against a regex pattern.
    
    Configuration:
        field: "field_name"
        params:
          pattern: "^[A-Z]{3}-\\d{4}$"
          flags: 0  # optional, regex flags
        severity: "error"
        message: "Custom message"
    
    Example:
        - validator: pattern
          field: invoice_number
          params:
            pattern: "^INV-\\d{4,}$"
          message: "Invoice number must start with INV-"
    """
    
    async def validate(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        value = self._get_field_value(data, self.field)
        
        if value is None:
            # If field doesn't exist, don't validate pattern (use 'required' for that)
            return self._create_result(
                passed=True,
                message="",
                layer="data_quality"
            )
        
        # Get pattern from params
        params = self.config.get('params', {})
        pattern = params.get('pattern')
        flags = params.get('flags', 0)
        
        if not pattern:
            return self._create_result(
                passed=False,
                message="Pattern validator requires 'pattern' parameter",
                layer="data_quality"
            )
        
        # Convert value to string for matching
        str_value = str(value)
        
        try:
            matches = bool(re.match(pattern, str_value, flags=flags))
        except re.error as e:
            return self._create_result(
                passed=False,
                message=f"Invalid regex pattern: {e}",
                layer="data_quality"
            )
        
        message = self.message_template or f"Field '{self.field}' does not match pattern '{pattern}'"
        
        return self._create_result(
            passed=matches,
            message=message if not matches else "",
            actual_value=str_value,
            expected_value=pattern,
            layer="data_quality"
        )


@register_validator("type_check")
class TypeCheckValidator(BaseValidator):
    """
    Validate that a field is of the expected data type.
    
    Supported types:
    - string, number, integer, float, boolean
    - array, object
    - date, datetime, email, url
    
    Configuration:
        field: "field_name"
        params:
          expected_type: "string"
        severity: "error"
    
    Example:
        - validator: type_check
          field: amount
          params:
            expected_type: "number"
    """
    
    TYPE_VALIDATORS = {
        'string': lambda v: isinstance(v, str),
        'number': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        'integer': lambda v: isinstance(v, int) and not isinstance(v, bool),
        'float': lambda v: isinstance(v, float),
        'boolean': lambda v: isinstance(v, bool),
        'array': lambda v: isinstance(v, list),
        'list': lambda v: isinstance(v, list),
        'object': lambda v: isinstance(v, dict),
        'dict': lambda v: isinstance(v, dict),
    }
    
    async def validate(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        value = self._get_field_value(data, self.field)
        
        if value is None:
            return self._create_result(
                passed=True,
                message="",
                layer="data_quality"
            )
        
        params = self.config.get('params', {})
        expected_type = params.get('expected_type', 'string')
        
        # Get validator function
        validator_fn = self.TYPE_VALIDATORS.get(expected_type)
        
        # Handle special types
        if expected_type == 'date':
            passed = self._is_valid_date(value)
        elif expected_type == 'datetime':
            passed = self._is_valid_datetime(value)
        elif expected_type == 'email':
            passed = self._is_valid_email(value)
        elif expected_type == 'url':
            passed = self._is_valid_url(value)
        elif validator_fn:
            passed = validator_fn(value)
        else:
            return self._create_result(
                passed=False,
                message=f"Unknown type: {expected_type}",
                layer="data_quality"
            )
        
        actual_type = type(value).__name__
        message = self.message_template or f"Field '{self.field}' must be type '{expected_type}', got '{actual_type}'"
        
        return self._create_result(
            passed=passed,
            message=message if not passed else "",
            actual_value=actual_type,
            expected_value=expected_type,
            layer="data_quality"
        )
    
    def _is_valid_date(self, value: Any) -> bool:
        """Check if value is a valid date"""
        if isinstance(value, datetime):
            return True
        if isinstance(value, str):
            try:
                datetime.fromisoformat(value.replace('Z', '+00:00'))
                return True
            except ValueError:
                return False
        return False
    
    def _is_valid_datetime(self, value: Any) -> bool:
        """Check if value is a valid datetime"""
        return self._is_valid_date(value)
    
    def _is_valid_email(self, value: Any) -> bool:
        """Check if value is a valid email"""
        if not isinstance(value, str):
            return False
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, value))
    
    def _is_valid_url(self, value: Any) -> bool:
        """Check if value is a valid URL"""
        if not isinstance(value, str):
            return False
        url_pattern = r'^https?://[^\s]+$'
        return bool(re.match(url_pattern, value))


@register_validator("range")
class RangeValidator(BaseValidator):
    """
    Validate that a numeric field is within a specified range.
    
    Configuration:
        field: "field_name"
        params:
          min: 0  # optional
          max: 1000  # optional
          inclusive: true  # optional, default true
        severity: "error"
    
    Example:
        - validator: range
          field: amount
          params:
            min: 0
            max: 999999
    """
    
    async def validate(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        value = self._get_field_value(data, self.field)
        
        if value is None:
            return self._create_result(
                passed=True,
                message="",
                layer="data_quality"
            )
        
        # Check if numeric
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return self._create_result(
                passed=False,
                message=f"Field '{self.field}' must be numeric for range validation",
                actual_value=type(value).__name__,
                layer="data_quality"
            )
        
        params = self.config.get('params', {})
        min_val = params.get('min')
        max_val = params.get('max')
        inclusive = params.get('inclusive', True)
        
        passed = True
        reason_parts = []
        
        if min_val is not None:
            if inclusive:
                if value < min_val:
                    passed = False
                    reason_parts.append(f"≥ {min_val}")
            else:
                if value <= min_val:
                    passed = False
                    reason_parts.append(f"> {min_val}")
        
        if max_val is not None:
            if inclusive:
                if value > max_val:
                    passed = False
                    reason_parts.append(f"≤ {max_val}")
            else:
                if value >= max_val:
                    passed = False
                    reason_parts.append(f"< {max_val}")
        
        if reason_parts:
            message = f"Field '{self.field}' must be {' and '.join(reason_parts)}"
        else:
            message = ""
        
        message = self.message_template or message
        
        return self._create_result(
            passed=passed,
            message=message if not passed else "",
            actual_value=value,
            expected_value={"min": min_val, "max": max_val},
            layer="data_quality"
        )


@register_validator("length")
class LengthValidator(BaseValidator):
    """
    Validate string or array length.
    
    Configuration:
        field: "field_name"
        params:
          min_length: 1  # optional
          max_length: 100  # optional
        severity: "warning"
    
    Example:
        - validator: length
          field: description
          params:
            min_length: 10
            max_length: 500
    """
    
    async def validate(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        value = self._get_field_value(data, self.field)
        
        if value is None:
            return self._create_result(
                passed=True,
                message="",
                layer="data_quality"
            )
        
        # Get length
        if isinstance(value, (str, list, dict)):
            length = len(value)
        else:
            return self._create_result(
                passed=False,
                message=f"Field '{self.field}' must be string, array, or object for length validation",
                layer="data_quality"
            )
        
        params = self.config.get('params', {})
        min_length = params.get('min_length')
        max_length = params.get('max_length')
        
        passed = True
        reason_parts = []
        
        if min_length is not None and length < min_length:
            passed = False
            reason_parts.append(f"at least {min_length}")
        
        if max_length is not None and length > max_length:
            passed = False
            reason_parts.append(f"at most {max_length}")
        
        if reason_parts:
            message = f"Field '{self.field}' length must be {' and '.join(reason_parts)}, got {length}"
        else:
            message = ""
        
        message = self.message_template or message
        
        return self._create_result(
            passed=passed,
            message=message if not passed else "",
            actual_value=length,
            expected_value={"min": min_length, "max": max_length},
            layer="data_quality"
        )


@register_validator("enum")
class EnumValidator(BaseValidator):
    """
    Validate that field value is in a list of allowed values.
    
    Configuration:
        field: "field_name"
        params:
          allowed_values: ["value1", "value2", "value3"]
          case_sensitive: true  # optional, default true
        severity: "error"
    
    Example:
        - validator: enum
          field: status
          params:
            allowed_values: ["pending", "approved", "rejected"]
    """
    
    async def validate(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        value = self._get_field_value(data, self.field)
        
        if value is None:
            return self._create_result(
                passed=True,
                message="",
                layer="data_quality"
            )
        
        params = self.config.get('params', {})
        allowed_values = params.get('allowed_values', [])
        case_sensitive = params.get('case_sensitive', True)
        
        if not allowed_values:
            return self._create_result(
                passed=False,
                message="Enum validator requires 'allowed_values' parameter",
                layer="data_quality"
            )
        
        # Check if value is in allowed list
        if case_sensitive:
            passed = value in allowed_values
        else:
            # Case-insensitive comparison for strings
            if isinstance(value, str):
                lower_allowed = [str(v).lower() for v in allowed_values]
                passed = value.lower() in lower_allowed
            else:
                passed = value in allowed_values
        
        message = self.message_template or f"Field '{self.field}' must be one of {allowed_values}, got '{value}'"
        
        return self._create_result(
            passed=passed,
            message=message if not passed else "",
            actual_value=value,
            expected_value=allowed_values,
            layer="data_quality"
        )
