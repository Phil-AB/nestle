"""
Metadata and confidence validators.

Validators that check extraction quality and confidence:
- ConfidenceValidator: Check extraction confidence scores
- OverallConfidenceValidator: Check document-wide confidence
"""

from typing import Any, Dict, Optional, List
from modules.extraction.validation.core.base import BaseValidator, ValidationResult
from modules.extraction.validation.core.registry import register_validator


@register_validator("confidence")
class ConfidenceValidator(BaseValidator):
    """
    Validate extraction confidence scores for specific fields.
    
    Configuration:
        params:
          fields: ["field1", "field2"]  # or ["*"] for all fields
          min_confidence: 0.85
        severity: "warning"
    
    Example:
        - validator: confidence
          params:
            fields: ["invoice_number", "total_amount"]
            min_confidence: 0.90
          message: "Critical fields have low confidence"
    """
    
    async def validate(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        params = self.config.get('params', {})
        fields = params.get('fields', ['*'])
        min_confidence = params.get('min_confidence', 0.70)
        
        # Get metadata (confidence scores)
        metadata = data.get('_metadata', {})
        confidence_scores = metadata.get('confidence_scores', {})
        
        if not confidence_scores:
            # No confidence scores available, pass validation
            return self._create_result(
                passed=True,
                message="",
                layer="accuracy"
            )
        
        # Determine which fields to check
        if '*' in fields:
            check_fields = list(confidence_scores.keys())
        else:
            check_fields = fields
        
        # Find low confidence fields
        low_confidence_fields = []
        for field in check_fields:
            confidence = confidence_scores.get(field, 1.0)
            if confidence < min_confidence:
                low_confidence_fields.append({
                    'field': field,
                    'confidence': confidence
                })
        
        passed = len(low_confidence_fields) == 0
        
        if not passed:
            field_list = ', '.join([f"{f['field']}({f['confidence']:.2f})" for f in low_confidence_fields])
            message = self.message_template or f"Low confidence fields: {field_list}"
        else:
            message = ""
        
        return self._create_result(
            passed=passed,
            message=message,
            actual_value=low_confidence_fields,
            expected_value=f"confidence >= {min_confidence}",
            layer="accuracy",
            confidence=min(f['confidence'] for f in low_confidence_fields) if low_confidence_fields else 1.0
        )


@register_validator("overall_confidence")
class OverallConfidenceValidator(BaseValidator):
    """
    Validate overall document extraction confidence.
    
    Configuration:
        params:
          min_confidence: 0.80
          aggregation: "average"  # average, min, weighted
        severity: "warning"
    
    Example:
        - validator: overall_confidence
          params:
            min_confidence: 0.75
            aggregation: "average"
    """
    
    async def validate(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        params = self.config.get('params', {})
        min_confidence = params.get('min_confidence', 0.70)
        aggregation = params.get('aggregation', 'average')
        
        # Get metadata
        metadata = data.get('_metadata', {})
        confidence_scores = metadata.get('confidence_scores', {})
        
        if not confidence_scores:
            return self._create_result(
                passed=True,
                message="",
                layer="accuracy"
            )
        
        # Calculate overall confidence
        scores = list(confidence_scores.values())
        
        if aggregation == 'average':
            overall = sum(scores) / len(scores) if scores else 1.0
        elif aggregation == 'min':
            overall = min(scores) if scores else 1.0
        elif aggregation == 'weighted':
            # Could implement weighted average based on field importance
            # For now, use simple average
            overall = sum(scores) / len(scores) if scores else 1.0
        else:
            overall = sum(scores) / len(scores) if scores else 1.0
        
        passed = overall >= min_confidence
        
        message = self.message_template or f"Overall document confidence ({overall:.2f}) is below threshold ({min_confidence})"
        
        return self._create_result(
            passed=passed,
            message=message if not passed else "",
            actual_value=overall,
            expected_value=min_confidence,
            layer="accuracy",
            confidence=overall
        )
