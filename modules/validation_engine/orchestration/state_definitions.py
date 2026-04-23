"""State definitions for LangGraph validation workflow"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from operator import add


class ValidationWorkflowState(TypedDict):
    """
    State for validation workflow

    This state is passed through all workflow nodes and maintains
    the complete validation context.
    """

    # Session identification
    session_id: str
    use_case: str
    version: int

    # Input documents
    documents: Dict[str, Dict[str, Any]]
    primary_document: str
    supporting_documents: List[str]

    # Configuration
    config: Dict[str, Any]
    tolerance_overrides: Dict[str, float]

    # Workflow progress
    current_step: str
    completed_steps: Annotated[List[str], add]  # Append-only list
    failed_steps: Annotated[List[str], add]

    # Normalization
    normalized: bool
    normalized_documents: Dict[str, Dict[str, Any]]
    normalization_errors: Annotated[List[Dict[str, Any]], add]

    # Validation
    validation_results: Annotated[List[Dict[str, Any]], add]  # Append-only
    all_validations_passed: bool

    # Discrepancies
    discrepancies: Annotated[List[Dict[str, Any]], add]  # Append-only
    critical_discrepancies: Annotated[List[Dict[str, Any]], add]
    auto_fixed_count: int

    # User interaction
    requires_user_confirmation: bool
    user_confirmed: bool
    user_confirmations: Dict[str, Any]  # disc_id → {confirmed: bool, comment: str|None}
    user_input: Dict[str, Any]
    awaiting_user: bool

    # Versioning
    is_revalidation: bool
    previous_version_id: Optional[str]
    changes_detected: Annotated[List[Dict[str, Any]], add]

    # Status
    workflow_status: str  # "running", "awaiting_user", "completed", "failed"
    final_status: str  # "passed", "failed", "requires_attention"

    # Error handling
    error: Optional[str]
    retry_count: int
    max_retries: int

    # Messages and logs
    messages: Annotated[List[str], add]  # Append-only log

    # Metadata
    created_at: str
    updated_at: str


# Workflow statuses
class WorkflowStatus:
    """Workflow execution statuses"""
    INITIALIZING = "initializing"
    NORMALIZING = "normalizing"
    VALIDATING = "validating"
    ANALYZING = "analyzing"
    AWAITING_USER = "awaiting_user"
    COMPLETED = "completed"
    FAILED = "failed"


# Node names (workflow steps)
class WorkflowNode:
    """Workflow node names"""
    START = "start"
    INITIALIZE = "initialize"
    NORMALIZE = "normalize"
    VALIDATE = "validate"
    ANALYZE_DISCREPANCIES = "analyze_discrepancies"
    AUTO_FIX = "auto_fix"
    CLASSIFY_DISCREPANCIES = "classify_discrepancies"
    REQUIRE_USER_CONFIRMATION = "require_user_confirmation"
    WAIT_FOR_USER = "wait_for_user"
    TRIGGER_AUTOMATION = "trigger_automation"
    GENERATE_REPORT = "generate_report"
    END = "end"


# Edge conditions
class EdgeCondition:
    """Edge condition names for conditional routing"""
    HAS_DISCREPANCIES = "has_discrepancies"
    NO_DISCREPANCIES = "no_discrepancies"
    AUTO_FIXABLE = "auto_fixable"
    REQUIRES_USER = "requires_user"
    USER_CONFIRMED = "user_confirmed"
    USER_REJECTED = "user_rejected"
    CRITICAL_ERRORS = "critical_errors"
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"
