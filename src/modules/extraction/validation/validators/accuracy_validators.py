"""
Ground truth accuracy validators.

Validates extracted data against known correct (ground truth) values:
- GroundTruthValidator: Compare fields against ground truth
"""

from typing import Any, Dict, Optional, List
from difflib import SequenceMatcher
from modules.extraction.validation.core.base import BaseValidator, ValidationResult
from modules.extraction.validation.core.registry import register_validator


@register_validator("ground_truth")
class GroundTruthValidator(BaseValidator):
    """
    Validate extracted data against ground truth values.
    
    Measures extraction accuracy by comparing with known correct values.
    Supports multiple comparison strategies for different data types.
    
    Configuration:
        params:
          fields:
            - field: "field_name"
              strategy: "exact"  # exact, numeric, fuzzy, ignore_case
              tolerance: 0.01    # for numeric
              threshold: 0.90    # for fuzzy (0.0-1.0)
          min_accuracy: 0.95     # overall accuracy threshold
          require_all_fields: false  # fail if ground truth missing fields
        severity: "error"
    
    Ground truth provided via context:
        context = {
            "ground_truth": {
                "field1": "correct_value1",
                "field2": 123.45
            }
        }
    
    Example:
        - validator: ground_truth
          params:
            fields:
              - field: invoice_number
                strategy: exact
              - field: amount
                strategy: numeric
                tolerance: 0.01
              - field: supplier_name
                strategy: fuzzy
                threshold: 0.85
            min_accuracy: 0.90
          severity: error
          message: "Extraction accuracy below 90%"
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.strategies = {
            'exact': self._exact_match,
            'numeric': self._numeric_match,
            'fuzzy': self._fuzzy_match,
            'ignore_case': self._ignore_case_match,
        }
    
    async def validate(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        # Get ground truth from context
        if not context or 'ground_truth' not in context:
            return self._create_result(
                passed=True,
                message="No ground truth provided for comparison",
                layer="accuracy",
                metadata={'skipped': True}
            )
        
        ground_truth = context['ground_truth']
        params = self.config.get('params', {})
        field_configs = params.get('fields', [])
        min_accuracy = params.get('min_accuracy', 1.0)
        require_all = params.get('require_all_fields', False)
        
        if not field_configs:
            return self._create_result(
                passed=False,
                message="Ground truth validator requires 'fields' configuration",
                layer="accuracy"
            )
        
        # Compare each configured field
        field_results = {}
        total_score = 0.0
        compared_count = 0
        
        for field_config in field_configs:
            field_name = field_config.get('field')
            if not field_name:
                continue
            
            extracted_value = self._get_field_value(data, field_name)
            truth_value = ground_truth.get(field_name)
            
            # Check if ground truth exists for this field
            if truth_value is None:
                if require_all:
                    field_results[field_name] = {
                        'match': False,
                        'score': 0.0,
                        'reason': 'Missing ground truth value'
                    }
                    compared_count += 1
                continue
            
            # If extracted value missing, it's a fail
            if extracted_value is None:
                field_results[field_name] = {
                    'match': False,
                    'score': 0.0,
                    'extracted': None,
                    'ground_truth': truth_value,
                    'reason': 'Field not extracted'
                }
                compared_count += 1
                continue
            
            # Apply comparison strategy
            strategy = field_config.get('strategy', 'exact')
            strategy_fn = self.strategies.get(strategy)
            
            if not strategy_fn:
                field_results[field_name] = {
                    'match': False,
                    'score': 0.0,
                    'reason': f'Unknown strategy: {strategy}'
                }
                compared_count += 1
                continue
            
            # Execute comparison
            result = strategy_fn(extracted_value, truth_value, field_config)
            field_results[field_name] = result
            total_score += result['score']
            compared_count += 1
        
        # Calculate overall accuracy
        overall_accuracy = total_score / compared_count if compared_count > 0 else 0.0
        passed = overall_accuracy >= min_accuracy
        
        # Build detailed message
        if not passed:
            failed_fields = [
                f"{fname} ({r['score']:.2%})"
                for fname, r in field_results.items()
                if not r['match']
            ]
            message = self.message_template or \
                f"Accuracy {overall_accuracy:.2%} below threshold {min_accuracy:.2%}. " \
                f"Failed: {', '.join(failed_fields)}"
        else:
            message = f"Accuracy {overall_accuracy:.2%} meets threshold"
        
        return self._create_result(
            passed=passed,
            message=message if not passed else "",
            actual_value=overall_accuracy,
            expected_value=min_accuracy,
            layer="accuracy",
            metadata={
                'field_results': field_results,
                'compared_fields': compared_count,
                'accuracy_score': overall_accuracy
            }
        )
    
    def _exact_match(
        self,
        extracted: Any,
        truth: Any,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Exact match comparison."""
        match = extracted == truth
        return {
            'match': match,
            'score': 1.0 if match else 0.0,
            'extracted': extracted,
            'ground_truth': truth,
            'strategy': 'exact'
        }
    
    def _numeric_match(
        self,
        extracted: Any,
        truth: Any,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Numeric comparison with tolerance."""
        tolerance = config.get('tolerance', 0.0)
        
        try:
            ext_val = float(extracted)
            truth_val = float(truth)
            diff = abs(ext_val - truth_val)
            match = diff <= tolerance
            
            # Score based on how close it is
            if match:
                score = 1.0
            else:
                # Partial credit based on how far off
                max_diff = abs(truth_val) * 0.1  # 10% of truth value
                score = max(0.0, 1.0 - (diff / max(max_diff, 1.0)))
            
            return {
                'match': match,
                'score': score,
                'extracted': ext_val,
                'ground_truth': truth_val,
                'difference': diff,
                'tolerance': tolerance,
                'strategy': 'numeric'
            }
        except (ValueError, TypeError):
            return {
                'match': False,
                'score': 0.0,
                'extracted': extracted,
                'ground_truth': truth,
                'reason': 'Non-numeric values',
                'strategy': 'numeric'
            }
    
    def _fuzzy_match(
        self,
        extracted: Any,
        truth: Any,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fuzzy string matching using similarity ratio."""
        threshold = config.get('threshold', 0.90)
        
        ext_str = str(extracted).strip().lower()
        truth_str = str(truth).strip().lower()
        
        # Calculate similarity ratio
        similarity = SequenceMatcher(None, ext_str, truth_str).ratio()
        match = similarity >= threshold
        
        return {
            'match': match,
            'score': similarity,
            'extracted': str(extracted),
            'ground_truth': str(truth),
            'similarity': similarity,
            'threshold': threshold,
            'strategy': 'fuzzy'
        }
    
    def _ignore_case_match(
        self,
        extracted: Any,
        truth: Any,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Case-insensitive string comparison."""
        ext_str = str(extracted).strip().lower()
        truth_str = str(truth).strip().lower()
        match = ext_str == truth_str
        
        return {
            'match': match,
            'score': 1.0 if match else 0.0,
            'extracted': str(extracted),
            'ground_truth': str(truth),
            'strategy': 'ignore_case'
        }
