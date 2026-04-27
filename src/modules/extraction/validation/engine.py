"""
ValidationEngine - Main orchestrator for document validation.

This is the primary entry point for validating documents.
It loads configuration, executes validators, and aggregates results.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

from modules.extraction.validation.core.base import ValidationResult, ValidationSeverity
from modules.extraction.validation.core.registry import VALIDATOR_REGISTRY, get_validator
from modules.extraction.validation.core.config_loader import ValidationConfigLoader
from shared.utils.logger import setup_logger

# Import validators to trigger registration
from modules.extraction.validation import validators  # noqa: F401

logger = setup_logger(__name__)


@dataclass
class ValidationSummary:
    """Summary of validation results for a document"""
    document_type: str
    passed: bool
    score: float  # 0.0 to 1.0
    total_checks: int
    passed_checks: int
    failed_checks: int
    warning_checks: int
    error_checks: int
    critical_checks: int
    requires_review: bool
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class DocumentValidationResult:
    """Complete validation result for a document"""
    document_type: str
    passed: bool
    score: float
    results: List[Dict[str, Any]]  # List of ValidationResult dicts
    summary: ValidationSummary
    metadata: Dict[str, Any]
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'document_type': self.document_type,
            'passed': self.passed,
            'score': self.score,
            'results': self.results,
            'summary': self.summary.to_dict(),
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


class ValidationEngine:
    """
    Universal validation engine.
    
    Orchestrates validation by:
    1. Loading rules from configuration
    2. Instantiating validators
    3. Executing validation checks
    4. Aggregating results
    
    This engine is completely independent and can validate data from ANY source.
    
    Usage:
        engine = ValidationEngine()
        result = await engine.validate("invoice", data, context)
        
        if result.passed:
            print("All validations passed!")
        else:
            for error in result.results:
                if not error['passed']:
                    print(f"Error: {error['message']}")
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize validation engine.
        
        Args:
            config_path: Path to validation rules YAML file
                        If None, uses default location
        """
        self.config_loader = ValidationConfigLoader(config_path)
        self.config = self.config_loader.load()
        self.global_settings = self.config_loader.get_global_settings()
        
        logger.info(
            f"ValidationEngine initialized with {len(VALIDATOR_REGISTRY)} validators"
        )
    
    async def validate(
        self,
        document_type: str,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> DocumentValidationResult:
        """
        Validate document data against configured rules.
        
        Automatically fetches ground truth if document_id is present in data.
        
        Args:
            document_type: Type identifier (e.g., "invoice", "contract")
            data: Document data to validate
                   Format: {"field1": "value", "field2": 123, ...}
            context: Optional context for cross-document validation
                      Format: {"related_documents": [...], "reference_data": {...}}
        
        Returns:
            DocumentValidationResult with all validation results
        
        Example:
            result = await engine.validate(
                "invoice",
                {"invoice_number": "INV-001", "amount": 1000},
                {"related_documents": [...]}
            )
        """
        logger.info(f"Validating document type: {document_type}")
        
        # Initialize context if None
        if context is None:
            context = {}
        
        # Auto-fetch ground truth if document has ID or _id
        document_id = data.get('_id') or data.get('id') or data.get('document_id')
        if document_id and 'ground_truth' not in context:
            try:
                from modules.extraction.ground_truth import GroundTruthService
                gt_service = GroundTruthService()
                ground_truth_data = await gt_service.get(document_id=str(document_id))
                
                if ground_truth_data and ground_truth_data.get('verified_data'):
                    context['ground_truth'] = ground_truth_data['verified_data']
                    logger.info(f"Auto-fetched ground truth for document: {document_id}")
            except Exception as e:
                logger.warning(f"Failed to auto-fetch ground truth: {e}")
        
        # Get validation rules for this document type
        rules = self.config_loader.get_document_rules(document_type)
        
        if not rules:
            logger.info(f"No validation rules defined for {document_type}")
            return self._create_empty_result(document_type)
        
        # Execute all validators
        results: List[ValidationResult] = []
        stop_on_error = self.global_settings.get('stop_on_first_error', False)
        
        for rule_config in rules:
            validator_name = rule_config.get('validator')
            
            if not validator_name:
                logger.warning(f"Rule missing 'validator' field: {rule_config}")
                continue
            
            # Get validator class from registry
            validator_class = get_validator(validator_name)
            
            if not validator_class:
                logger.warning(f"Validator '{validator_name}' not found in registry")
                continue
            
            # Instantiate and execute validator
            try:
                validator = validator_class(rule_config)
                result = await validator.validate(data, context)
                results.append(result)
                
                # Stop on first error if configured
                if stop_on_error and not result.passed and result.severity == ValidationSeverity.ERROR:
                    logger.info(f"Stopping validation on first error: {result.message}")
                    break
                    
            except Exception as e:
                logger.error(f"Validator '{validator_name}' failed: {e}", exc_info=True)
                # Create error result
                error_result = ValidationResult(
                    passed=False,
                    validator_name=validator_name,
                    severity=ValidationSeverity.ERROR,
                    message=f"Validator execution failed: {str(e)}",
                    layer="validation_engine"
                )
                results.append(error_result)
        
        # Generate summary and final result
        return self._generate_result(document_type, results)
    
    def _create_empty_result(self, document_type: str) -> DocumentValidationResult:
        """
        Create empty result when no rules are defined.
        
        Args:
            document_type: Document type
        
        Returns:
            DocumentValidationResult with passed=True
        """
        timestamp = datetime.utcnow()
        summary = ValidationSummary(
            document_type=document_type,
            passed=True,
            score=1.0,
            total_checks=0,
            passed_checks=0,
            failed_checks=0,
            warning_checks=0,
            error_checks=0,
            critical_checks=0,
            requires_review=False,
            timestamp=timestamp
        )
        
        return DocumentValidationResult(
            document_type=document_type,
            passed=True,
            score=1.0,
            results=[],
            summary=summary,
            metadata={'no_rules': True},
            timestamp=timestamp
        )
    
    def _generate_result(
        self,
        document_type: str,
        results: List[ValidationResult]
    ) -> DocumentValidationResult:
        """
        Generate final validation result with summary.
        
        Args:
            document_type: Document type
            results: List of validation results
        
        Returns:
            DocumentValidationResult
        """
        timestamp = datetime.utcnow()
        
        # Count results by severity
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed)
        
        warnings = sum(
            1 for r in results
            if not r.passed and r.severity == ValidationSeverity.WARNING
        )
        errors = sum(
            1 for r in results
            if not r.passed and r.severity == ValidationSeverity.ERROR
        )
        critical = sum(
            1 for r in results
            if not r.passed and r.severity == ValidationSeverity.CRITICAL
        )
        
        # Overall pass/fail (only ERROR and CRITICAL fail, WARNING passes)
        overall_passed = errors == 0 and critical == 0
        
        # Calculate score (percentage of passed checks)
        score = passed / total if total > 0 else 1.0
        
        # Determine if requires review
        confidence_threshold = self.global_settings.get('confidence_threshold', 0.70)
        low_confidence = any(
            r.confidence and r.confidence < confidence_threshold
            for r in results
        )
        requires_review = not overall_passed or low_confidence
        
        # Create summary
        summary = ValidationSummary(
            document_type=document_type,
            passed=overall_passed,
            score=score,
            total_checks=total,
            passed_checks=passed,
            failed_checks=failed,
            warning_checks=warnings,
            error_checks=errors,
            critical_checks=critical,
            requires_review=requires_review,
            timestamp=timestamp
        )
        
        # Convert results to dicts
        result_dicts = [r.to_dict() for r in results]
        
        # Build metadata
        metadata = {
            'validation_mode': self.global_settings.get('validation_mode', 'strict'),
            'rules_count': len(results),
            'layers': list(set(r.layer for r in results if r.layer))
        }
        
        return DocumentValidationResult(
            document_type=document_type,
            passed=overall_passed,
            score=score,
            results=result_dicts,
            summary=summary,
            metadata=metadata,
            timestamp=timestamp
        )
    
    def reload_config(self) -> None:
        """Reload validation configuration from file"""
        logger.info("Reloading validation configuration")
        self.config = self.config_loader.reload()
        self.global_settings = self.config_loader.get_global_settings()
    
    def get_available_validators(self) -> List[str]:
        """
        Get list of all registered validators.
        
        Returns:
            List of validator names
        """
        return list(VALIDATOR_REGISTRY.keys())
    
    def get_document_rules(self, document_type: str) -> List[Dict[str, Any]]:
        """
        Get validation rules for a document type.
        
        Args:
            document_type: Document type
        
        Returns:
            List of rule configurations
        """
        return self.config_loader.get_document_rules(document_type)
