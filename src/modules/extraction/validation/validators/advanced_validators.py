"""
Cross-field and aggregate validators.

Validators that operate across multiple fields or aggregate data:
- FieldComparisonValidator: Compare two fields
- FieldDependencyValidator: If field1 exists, field2 must exist
- FormulaValidator: Validate calculated fields
- AggregateValidator: Validate aggregations over items (sum, count, avg, etc.)
"""

import operator
from typing import Any, Dict, Optional, List, Callable
from modules.extraction.validation.core.base import BaseValidator, ValidationResult
from modules.extraction.validation.core.registry import register_validator
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


@register_validator("field_comparison")
class FieldComparisonValidator(BaseValidator):
    """
    Compare two fields using an operator.
    
    Supported operators: ==, !=, >, <, >=, <=, eq, ne, gt, lt, gte, lte
    
    Configuration:
        params:
          field1: "start_date"
          operator: "<"
          field2: "end_date"
        severity: "warning"
        message: "Custom message"
    
    Example:
        - validator: field_comparison
          params:
            field1: start_date
            operator: "<"
            field2: end_date
          message: "Start date must be before end date"
    """
    
    OPERATORS = {
        '==': operator.eq,
        'eq': operator.eq,
        '!=': operator.ne,
        'ne': operator.ne,
        '>': operator.gt,
        'gt': operator.gt,
        '<': operator.lt,
        'lt': operator.lt,
        '>=': operator.ge,
        'gte': operator.ge,
        '<=': operator.le,
        'lte': operator.le,
    }
    
    async def validate(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        params = self.config.get('params', {})
        field1 = params.get('field1')
        field2 = params.get('field2')
        op = params.get('operator', '==')
        
        if not field1 or not field2:
            return self._create_result(
                passed=False,
                message="Field comparison requires 'field1' and 'field2' parameters",
                layer="business_rules"
            )
        
        value1 = self._get_field_value(data, field1)
        value2 = self._get_field_value(data, field2)
        
        # If either field doesn't exist, skip validation
        if value1 is None or value2 is None:
            return self._create_result(
                passed=True,
                message="",
                layer="business_rules"
            )
        
        # Get operator function
        op_fn = self.OPERATORS.get(op)
        if not op_fn:
            return self._create_result(
                passed=False,
                message=f"Unknown operator: {op}",
                layer="business_rules"
            )
        
        try:
            passed = op_fn(value1, value2)
        except TypeError as e:
            return self._create_result(
                passed=False,
                message=f"Cannot compare {field1} and {field2}: {e}",
                layer="business_rules"
            )
        
        message = self.message_template or f"Field '{field1}' must be {op} '{field2}'"
        
        return self._create_result(
            passed=passed,
            message=message if not passed else "",
            actual_value=f"{field1}={value1}",
            expected_value=f"{field1} {op} {field2} (where {field2}={value2})",
            layer="business_rules"
        )


@register_validator("field_dependency")
class FieldDependencyValidator(BaseValidator):
    """
    Validate field dependencies (if field1 exists, field2 must exist).
    
    Configuration:
        params:
          field1: "insurance_included"
          field2: "insurance_amount"
          condition: "equals"  # optional: equals, not_equals, exists
          value: true  # optional: required if condition is equals/not_equals
        severity: "error"
    
    Example:
        - validator: field_dependency
          params:
            field1: insurance_included
            condition: equals
            value: true
            field2: insurance_amount
          message: "Insurance amount required when insurance is included"
    """
    
    async def validate(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        params = self.config.get('params', {})
        field1 = params.get('field1')
        field2 = params.get('field2')
        condition = params.get('condition', 'exists')
        condition_value = params.get('value')
        
        if not field1 or not field2:
            return self._create_result(
                passed=False,
                message="Field dependency requires 'field1' and 'field2' parameters",
                layer="business_rules"
            )
        
        value1 = self._get_field_value(data, field1)
        value2 = self._get_field_value(data, field2)
        
        # Check if condition is met
        condition_met = False
        
        if condition == 'exists':
            condition_met = value1 is not None
        elif condition == 'equals':
            condition_met = value1 == condition_value
        elif condition == 'not_equals':
            condition_met = value1 != condition_value
        else:
            return self._create_result(
                passed=False,
                message=f"Unknown condition: {condition}",
                layer="business_rules"
            )
        
        # If condition not met, validation passes
        if not condition_met:
            return self._create_result(
                passed=True,
                message="",
                layer="business_rules"
            )
        
        # Condition is met, check if field2 exists
        passed = value2 is not None and value2 != ""
        
        message = self.message_template or f"Field '{field2}' is required when '{field1}' is {condition_value}"
        
        return self._create_result(
            passed=passed,
            message=message if not passed else "",
            actual_value=value2,
            layer="business_rules"
        )


@register_validator("formula")
class FormulaValidator(BaseValidator):
    """
    Validate a calculated field using a formula.
    
    Uses simpleeval for safe formula evaluation.
    
    Configuration:
        params:
          expression: "field_c == field_a + field_b"
          tolerance: 0.01  # optional, for floating point comparisons
        severity: "error"
    
    Example:
        - validator: formula
          params:
            expression: "total == subtotal + tax"
            tolerance: 0.01
          message: "Total must equal subtotal + tax"
    """
    
    async def validate(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        params = self.config.get('params', {})
        expression = params.get('expression')
        tolerance = params.get('tolerance', 0)
        
        if not expression:
            return self._create_result(
                passed=False,
                message="Formula validator requires 'expression' parameter",
                layer="business_rules"
            )
        
        try:
            # Use simpleeval for safe evaluation
            from simpleeval import simple_eval, DEFAULT_FUNCTIONS, DEFAULT_NAMES
            
            # Create namespace with all data fields
            namespace = {**data}
            
            # Add tolerance-aware comparison functions
            if tolerance > 0:
                namespace['__builtins__'] = {}
                def approx_eq(a, b):
                    return abs(a - b) <= tolerance
                namespace['approx_eq'] = approx_eq
                
                # Replace == with approx_eq in expression if tolerance specified
                # This is a simple approach - more sophisticated parsing could be added
                if '==' in expression:
                    logger.warning("Using tolerance with ==, consider using approx_eq() function in expression")
            
            result = simple_eval(
                expression,
                names=namespace,
                functions=DEFAULT_FUNCTIONS
            )
            
            passed = bool(result)
            
            return self._create_result(
                passed=passed,
                message=self.message_template or f"Formula validation failed: {expression}",
                actual_value=result,
                expected_value=True,
                layer="business_rules",
                metadata={'expression': expression}
            )
            
        except ImportError:
            logger.warning("simpleeval not installed, using basic eval (less safe)")
            # Fallback to basic evaluation (less safe, but works without dependency)
            try:
                result = eval(expression, {"__builtins__": {}}, data)
                passed = bool(result)
                
                return self._create_result(
                    passed=passed,
                    message=self.message_template or f"Formula validation failed: {expression}",
                    layer="business_rules"
                )
            except Exception as e:
                return self._create_result(
                    passed=False,
                    message=f"Formula evaluation error: {e}",
                    layer="business_rules"
                )
        
        except Exception as e:
            return self._create_result(
                passed=False,
                message=f"Formula evaluation error: {e}",
                layer="business_rules",
                metadata={'expression': expression, 'error': str(e)}
            )


@register_validator("aggregate")
class AggregateValidator(BaseValidator):
    """
    Validate aggregations over arrays/items.
    
    Supported functions: sum, count, avg, min, max
    
    Configuration:
        params:
          items_path: "items"  # path to array
          function: "sum"  # sum, count, avg, min, max
          source_field: "items.*.amount"  # field to aggregate
          target_field: "total_amount"  # field to compare against
          tolerance: 0.01  # optional
        severity: "warning"
    
    Example:
        - validator: aggregate
          params:
            items_path: "items"
            function: "sum"
            source_field: "amount"
            target_field: "total"
            tolerance: 0.01
          message: "Total must equal sum of item amounts"
    """
    
    AGGREGATE_FUNCTIONS = {
        'sum': lambda values: sum(values),
        'count': lambda values: len(values),
        'avg': lambda values: sum(values) / len(values) if values else 0,
        'min': lambda values: min(values) if values else None,
        'max': lambda values: max(values) if values else None,
    }
    
    async def validate(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        params = self.config.get('params', {})
        items_path = params.get('items_path', 'items')
        function = params.get('function', 'sum')
        source_field = params.get('source_field')
        target_field = params.get('target_field')
        tolerance = params.get('tolerance', 0)
        
        if not source_field or not target_field:
            return self._create_result(
                passed=False,
                message="Aggregate validator requires 'source_field' and 'target_field' parameters",
                layer="business_rules"
            )
        
        # Get items array
        items = self._get_field_value(data, items_path)
        
        if not isinstance(items, list):
            return self._create_result(
                passed=True,
                message="",
                layer="business_rules"
            )
        
        # Get aggregate function
        agg_fn = self.AGGREGATE_FUNCTIONS.get(function)
        if not agg_fn:
            return self._create_result(
                passed=False,
                message=f"Unknown aggregate function: {function}",
                layer="business_rules"
            )
        
        # Extract values from items
        values = []
        for item in items:
            val = item.get(source_field) if isinstance(item, dict) else None
            if val is not None:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    logger.warning(f"Skipping non-numeric value: {val}")
        
        # Calculate aggregate
        try:
            aggregated = agg_fn(values)
        except Exception as e:
            return self._create_result(
                passed=False,
                message=f"Aggregation error: {e}",
                layer="business_rules"
            )
        
        # Get target value
        target_value = self._get_field_value(data, target_field)
        
        if target_value is None:
            return self._create_result(
                passed=True,
                message="",
                layer="business_rules"
            )
        
        # Compare with tolerance
        try:
            target_value = float(target_value)
            if tolerance > 0:
                passed = abs(aggregated - target_value) <= tolerance
            else:
                passed = aggregated == target_value
        except (ValueError, TypeError):
            return self._create_result(
                passed=False,
                message=f"Target field '{target_field}' is not numeric",
                layer="business_rules"
            )
        
        message = self.message_template or f"{function}({source_field}) must equal {target_field}"
        
        return self._create_result(
            passed=passed,
            message=message if not passed else "",
            actual_value=aggregated,
            expected_value=target_value,
            layer="business_rules",
            metadata={'function': function, 'item_count': len(values)}
        )
