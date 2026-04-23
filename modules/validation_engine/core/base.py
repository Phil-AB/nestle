"""Base interfaces and contracts for validation engine"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum

from ..utils.constants import (
    Severity, ValidatorType, DiscrepancyType, DiscrepancyCategory,
    ResolutionStatus, LikelyCause, AutoFixType
)


class ValidationResult(BaseModel):
    """Standard validation result format"""

    # Identification
    id: UUID = Field(default_factory=uuid4)
    validator_name: str
    validator_type: str  # ValidatorType

    # Validation target
    field_name: Optional[str] = None
    source_document: Optional[str] = None
    target_document: Optional[str] = None

    # Values
    source_value: Any = None
    target_value: Any = None
    expected_value: Optional[Any] = None

    # Result
    passed: bool
    confidence: float = Field(ge=0.0, le=1.0)  # 0.0 - 1.0
    severity: str = Severity.INFO

    # Details
    message: str
    auto_fixed: bool = False
    discrepancy: Optional[Dict[str, Any]] = None

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }


class Discrepancy(BaseModel):
    """Detected discrepancy"""

    # Identification
    id: UUID = Field(default_factory=uuid4)

    # Location
    field_name: str
    source_document: Optional[str] = None
    target_document: Optional[str] = None

    # Values
    source_value: Any = None
    target_value: Any = None
    difference: Optional[Any] = None

    # Classification
    discrepancy_type: str = DiscrepancyType.VALUE_MISMATCH
    severity: str = Severity.ERROR
    category: str = DiscrepancyCategory.OTHER

    # Human-readable explanation of what was checked and why it failed
    message: Optional[str] = None

    # Analysis
    likely_cause: str = LikelyCause.UNKNOWN
    confidence: float = Field(ge=0.0, le=1.0)

    # Resolution
    auto_fixable: bool = False
    auto_fixed: bool = False
    fix_type: Optional[str] = None  # AutoFixType
    suggested_fix: Optional[Dict[str, Any]] = None

    # User interaction
    user_confirmed: Optional[bool] = None
    user_comment: Optional[str] = None
    resolution_status: str = ResolutionStatus.OPEN

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }


class ValidationContext(BaseModel):
    """Context passed through validation workflow"""

    # Session identification
    session_id: UUID
    use_case: str
    version: int = 1

    # Documents
    documents: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    primary_document: Optional[str] = None
    supporting_documents: List[str] = Field(default_factory=list)

    # Configuration
    config: Dict[str, Any] = Field(default_factory=dict)
    tolerance_overrides: Dict[str, float] = Field(default_factory=dict)

    # Workflow state
    current_step: str = "initialize"
    normalized_data: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # Results
    validation_results: List[ValidationResult] = Field(default_factory=list)
    discrepancies: List[Discrepancy] = Field(default_factory=list)

    # User interaction
    user_provided_data: Dict[str, Any] = Field(default_factory=dict)
    user_confirmations: Dict[str, bool] = Field(default_factory=dict)

    # Versioning
    is_revalidation: bool = False
    previous_version_id: Optional[UUID] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat()
        }


class IValidator(ABC):
    """
    Base interface for all validators

    All validators must implement this interface and register with ValidatorRegistry
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize validator with configuration

        Args:
            config: Validator-specific configuration from YAML
        """
        self.config = config
        self.validator_type: str = ValidatorType.RULE_BASED
        self.validator_name: str = self.__class__.__name__

    @abstractmethod
    async def validate(
        self,
        source_data: Dict[str, Any],
        target_data: Optional[Dict[str, Any]],
        context: ValidationContext
    ) -> List[ValidationResult]:
        """
        Execute validation logic

        Args:
            source_data: Source document data
            target_data: Target document data (None for single-document validation)
            context: Validation context with session info and state

        Returns:
            List of validation results
        """
        pass

    @abstractmethod
    def supports_field_type(self, field_type: str) -> bool:
        """
        Check if validator supports this field type

        Args:
            field_type: Type of field (string, number, date, etc.)

        Returns:
            True if validator can handle this field type
        """
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """
        Return validator metadata

        Returns:
            Dictionary with validator information
        """
        return {
            "name": self.validator_name,
            "type": self.validator_type,
            "config": self.config,
            "description": self.__doc__ or "No description available"
        }

    def get_severity(self, discrepancy: Dict[str, Any]) -> str:
        """
        Determine severity of discrepancy

        Args:
            discrepancy: Discrepancy details

        Returns:
            Severity level (critical, major, minor, info)
        """
        # Default implementation - can be overridden
        return self.config.get("severity", Severity.ERROR)


class INormalizer(ABC):
    """
    Base interface for normalizers

    Normalizers transform data to standard formats before validation
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize normalizer with configuration

        Args:
            config: Normalizer-specific configuration
        """
        self.config = config
        self.normalizer_name: str = self.__class__.__name__

    @abstractmethod
    async def normalize(
        self,
        data: Dict[str, Any],
        context: ValidationContext
    ) -> Dict[str, Any]:
        """
        Normalize data

        Args:
            data: Raw data to normalize
            context: Validation context

        Returns:
            Normalized data
        """
        pass

    @abstractmethod
    def supports_field(self, field_name: str) -> bool:
        """
        Check if normalizer supports this field

        Args:
            field_name: Name of field

        Returns:
            True if normalizer can handle this field
        """
        pass


class IDiscrepancyClassifier(ABC):
    """
    Base interface for discrepancy classifiers

    Classifiers analyze discrepancies to determine severity, category, and root cause
    """

    @abstractmethod
    async def classify(
        self,
        discrepancy: Discrepancy,
        context: ValidationContext
    ) -> Discrepancy:
        """
        Classify discrepancy

        Args:
            discrepancy: Discrepancy to classify
            context: Validation context

        Returns:
            Updated discrepancy with classification
        """
        pass


class IAutoFixer(ABC):
    """
    Base interface for auto-fixers

    Auto-fixers attempt to automatically resolve common discrepancies
    """

    @abstractmethod
    async def can_fix(
        self,
        discrepancy: Discrepancy,
        context: ValidationContext
    ) -> bool:
        """
        Determine if discrepancy can be auto-fixed

        Args:
            discrepancy: Discrepancy to check
            context: Validation context

        Returns:
            True if discrepancy is auto-fixable
        """
        pass

    @abstractmethod
    async def fix(
        self,
        discrepancy: Discrepancy,
        context: ValidationContext
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt to fix discrepancy

        Args:
            discrepancy: Discrepancy to fix
            context: Validation context

        Returns:
            Fixed value or None if fix failed
        """
        pass


class IVersionComparator(ABC):
    """
    Base interface for version comparators

    Comparators analyze differences between validation versions
    """

    @abstractmethod
    async def compare(
        self,
        previous_context: ValidationContext,
        current_context: ValidationContext
    ) -> Dict[str, Any]:
        """
        Compare two validation versions

        Args:
            previous_context: Previous validation context
            current_context: Current validation context

        Returns:
            Comparison results with fixed/remaining/new discrepancies
        """
        pass


class IReportGenerator(ABC):
    """
    Base interface for report generators

    Report generators create validation reports in various formats
    """

    @abstractmethod
    async def generate(
        self,
        context: ValidationContext,
        format: str
    ) -> Union[str, bytes, Dict[str, Any]]:
        """
        Generate validation report

        Args:
            context: Validation context with results
            format: Output format (json, pdf, csv, html)

        Returns:
            Report in requested format
        """
        pass


class ValidationResultSummary(BaseModel):
    """Summary of validation results"""

    # Counts
    total_validations: int = 0
    passed_validations: int = 0
    failed_validations: int = 0

    total_discrepancies: int = 0
    error_discrepancies: int = 0
    info_discrepancies: int = 0

    auto_fixed_count: int = 0

    # Status
    all_validations_passed: bool = False

    # Confidence
    average_confidence: float = 0.0

    # Timing
    processing_time_seconds: Optional[float] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
