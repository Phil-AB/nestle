"""Version control data models"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from enum import Enum


class VersionStatus(str, Enum):
    """Version status enumeration"""
    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class ChangeType(str, Enum):
    """Type of change between versions"""
    FIXED = "fixed"              # Discrepancy present in V1, not in V2
    NEW = "new"                  # Discrepancy not in V1, present in V2
    PERSISTENT = "persistent"    # Discrepancy in both V1 and V2
    IMPROVED = "improved"        # Severity decreased (critical → major)
    WORSENED = "worsened"       # Severity increased (minor → major)
    VALUE_CHANGED = "value_changed"  # Source/target values changed


class VersionMetadata(BaseModel):
    """Metadata for a validation version"""

    session_id: UUID
    version: int
    status: VersionStatus = VersionStatus.ACTIVE

    # Validation summary
    total_validations: int = 0
    passed_validations: int = 0
    failed_validations: int = 0

    # Discrepancy summary
    total_discrepancies: int = 0
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0
    info_count: int = 0

    # Auto-fix summary
    auto_fixed_count: int = 0
    user_confirmed_count: int = 0

    # Final status
    final_status: Optional[str] = None
    accuracy_score: Optional[float] = None

    # Version lineage
    is_revalidation: bool = False
    previous_version_id: Optional[UUID] = None
    parent_version: Optional[int] = None

    # Metadata
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Tags and notes
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

    class Config:
        use_enum_values = True


class DiscrepancyChange(BaseModel):
    """Represents a change in a discrepancy between versions"""

    field_name: str
    change_type: ChangeType

    # V1 data
    v1_present: bool = False
    v1_severity: Optional[str] = None
    v1_source_value: Any = None
    v1_target_value: Any = None
    v1_confidence: Optional[float] = None

    # V2 data
    v2_present: bool = False
    v2_severity: Optional[str] = None
    v2_source_value: Any = None
    v2_target_value: Any = None
    v2_confidence: Optional[float] = None

    # Change details
    severity_changed: bool = False
    values_changed: bool = False
    auto_fixed: bool = False
    user_action: Optional[str] = None

    class Config:
        use_enum_values = True


class VersionComparison(BaseModel):
    """Comparison results between two validation versions"""

    # Version identification
    v1_session_id: UUID
    v1_version: int
    v2_session_id: UUID
    v2_version: int

    # Comparison summary
    total_changes: int = 0
    fixed_count: int = 0
    new_count: int = 0
    persistent_count: int = 0
    improved_count: int = 0
    worsened_count: int = 0

    # Detailed changes
    changes: List[DiscrepancyChange] = Field(default_factory=list)

    # Progress metrics
    v1_discrepancy_count: int = 0
    v2_discrepancy_count: int = 0
    improvement_rate: float = 0.0  # Percentage of fixed discrepancies
    regression_rate: float = 0.0   # Percentage of new discrepancies

    # Status comparison
    v1_final_status: Optional[str] = None
    v2_final_status: Optional[str] = None
    status_improved: bool = False

    # Accuracy comparison
    v1_accuracy: Optional[float] = None
    v2_accuracy: Optional[float] = None
    accuracy_delta: Optional[float] = None

    # Metadata
    compared_at: datetime = Field(default_factory=datetime.utcnow)
    comparison_notes: Optional[str] = None

    class Config:
        use_enum_values = True


class RevalidationRequest(BaseModel):
    """Request to create a new validation version"""

    original_session_id: UUID
    revalidation_reason: str

    # Optional new documents (if any changed)
    updated_documents: Optional[Dict[str, Dict[str, Any]]] = None

    # Optional configuration overrides
    tolerance_overrides: Optional[Dict[str, float]] = None
    skip_steps: Optional[List[str]] = None

    # Metadata
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_by: Optional[str] = None


class RevalidationResult(BaseModel):
    """Result of revalidation operation"""

    # New session info
    new_session_id: UUID
    new_version: int

    # Original session reference
    original_session_id: UUID
    original_version: int

    # Revalidation status
    status: str
    workflow_status: str
    final_status: Optional[str] = None

    # Comparison with original
    comparison: Optional[VersionComparison] = None

    # Summary
    total_discrepancies: int = 0
    fixed_count: int = 0
    new_count: int = 0
    persistent_count: int = 0

    # Messages
    messages: List[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)
