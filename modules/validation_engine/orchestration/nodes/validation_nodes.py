"""Workflow nodes for validation execution"""

from typing import Dict, Any
from datetime import datetime
from ...core.engine import get_validation_engine
from ...core.session_manager import get_session_manager
from ...core.result_aggregator import ResultAggregator
from ...normalization import get_normalization_engine
from ...validators.validator_registry import get_validator_registry
from ...utils.constants import Severity
from ..state_definitions import ValidationWorkflowState, WorkflowStatus
from shared.utils.logger import get_logger

logger = get_logger(__name__)


async def initialize_node(state: ValidationWorkflowState) -> Dict[str, Any]:
    """
    Initialize validation workflow

    Args:
        state: Current workflow state

    Returns:
        Updated state dict
    """
    logger.info(f"Initializing validation workflow for session {state['session_id']}")

    return {
        "current_step": "initialize",
        "completed_steps": ["initialize"],
        "workflow_status": WorkflowStatus.INITIALIZING,
        "messages": [f"Workflow initialized at {datetime.utcnow().isoformat()}"],
        "updated_at": datetime.utcnow().isoformat()
    }


async def normalize_node(state: ValidationWorkflowState) -> Dict[str, Any]:
    """
    Normalize documents (field names, units, formats)

    Args:
        state: Current workflow state

    Returns:
        Updated state dict
    """
    logger.info(f"Normalizing documents for session {state['session_id']}")

    try:
        # Get normalization engine
        norm_engine = get_normalization_engine()

        # Normalize all documents
        normalized_docs = await norm_engine.normalize_documents(
            documents=state["documents"]
        )

        return {
            "current_step": "normalize",
            "completed_steps": ["normalize"],
            "normalized": True,
            "normalized_documents": normalized_docs,
            "workflow_status": WorkflowStatus.NORMALIZING,
            "messages": [
                f"Normalized {len(normalized_docs)} documents: "
                f"{', '.join(normalized_docs.keys())}"
            ],
            "updated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Normalization failed: {str(e)}")
        return {
            "current_step": "normalize",
            "failed_steps": ["normalize"],
            "normalized": False,
            "normalized_documents": state["documents"],  # Use originals
            "normalization_errors": [{
                "step": "normalize",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }],
            "messages": [f"Normalization failed: {str(e)}. Using original documents."],
            "updated_at": datetime.utcnow().isoformat()
        }


async def validate_node(state: ValidationWorkflowState) -> Dict[str, Any]:
    """
    Execute validation workflow steps

    Args:
        state: Current workflow state

    Returns:
        Updated state dict
    """
    logger.info(f"Executing validation for session {state['session_id']}")

    try:
        # Get workflow configuration
        workflow_config = state["config"].get("use_case", {}).get("workflow", {})
        steps = workflow_config.get("steps", [])

        # Use normalized documents if available
        documents_to_validate = state.get("normalized_documents", state["documents"])

        # Get validator registry
        validator_registry = get_validator_registry()

        all_results = []
        all_discrepancies = []

        # Execute each workflow step
        for step_config in steps:
            step_name = step_config.get("name")
            validators = step_config.get("validators", [])
            step_severity = step_config.get("severity", "minor")

            logger.info(f"Executing step: {step_name}")

            # Execute validators in this step
            for validator_name in validators:
                try:
                    # Get validator config
                    validator_config = step_config.get("config", {})

                    # Get validator instance
                    validator = validator_registry.get_validator(
                        validator_name,
                        validator_config
                    )

                    # Create minimal context for validation
                    from ...core.base import ValidationContext
                    context = ValidationContext(
                        session_id=state["session_id"],
                        use_case=state["use_case"],
                        version=state["version"],
                        documents=documents_to_validate,
                        primary_document=state["primary_document"],
                        supporting_documents=state["supporting_documents"],
                        config=state["config"],
                        tolerance_overrides=state["tolerance_overrides"]
                    )

                    # Cross-document validators resolve field paths using dot-notation
                    # (e.g. "invoice.net_weight") and need the full documents dict.
                    # Single-document validators (range_validator, regex_validator) use
                    # plain field names and expect the primary document's flat fields.
                    def _has_dot_paths(cfg: dict) -> bool:
                        for val in cfg.get("validations", []):
                            if (isinstance(val, dict) and
                                    ("." in str(val.get("source", ""))
                                     or "." in str(val.get("target", "")))):
                                return True
                        return False

                    is_cross_doc = (
                        any(key in validator_config for key in ("calculations", "documents", "parties"))
                        or _has_dot_paths(validator_config)
                    )

                    if is_cross_doc:
                        source_data = documents_to_validate
                        target_data = documents_to_validate
                    else:
                        source_data = documents_to_validate.get(state["primary_document"], {})
                        target_data = None

                    # Execute validation
                    results = await validator.validate(
                        source_data=source_data,
                        target_data=target_data,
                        context=context
                    )

                    # Convert results to dicts
                    result_dicts = [r.dict() for r in results]
                    all_results.extend(result_dicts)

                    # Extract discrepancies
                    for result in results:
                        if not result.passed and not result.auto_fixed:
                            from ...core.base import Discrepancy
                            discrepancy = Discrepancy(
                                field_name=result.field_name or "unknown",
                                source_document=result.source_document,
                                target_document=result.target_document,
                                source_value=result.source_value,
                                target_value=result.target_value,
                                difference=result.discrepancy,
                                severity=result.severity,
                                confidence=result.confidence
                            )
                            all_discrepancies.append(discrepancy.dict())

                    logger.info(
                        f"Validator '{validator_name}' completed: "
                        f"{len(results)} results"
                    )

                except Exception as e:
                    logger.error(f"Validator '{validator_name}' failed: {str(e)}")
                    # Continue with other validators

        # Calculate summary stats
        passed = sum(1 for r in all_results if r["passed"])
        all_passed = passed == len(all_results)

        # Separate critical discrepancies
        critical = [d for d in all_discrepancies if d["severity"] == Severity.CRITICAL]

        return {
            "current_step": "validate",
            "completed_steps": ["validate"],
            "workflow_status": WorkflowStatus.VALIDATING,
            "validation_results": all_results,
            "all_validations_passed": all_passed,
            "discrepancies": all_discrepancies,
            "critical_discrepancies": critical,
            "messages": [
                f"Validation completed: {passed}/{len(all_results)} passed, "
                f"{len(all_discrepancies)} discrepancies found "
                f"({len(critical)} critical)"
            ],
            "updated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Validation failed: {str(e)}")
        return {
            "current_step": "validate",
            "failed_steps": ["validate"],
            "workflow_status": WorkflowStatus.FAILED,
            "error": str(e),
            "messages": [f"Validation failed: {str(e)}"],
            "updated_at": datetime.utcnow().isoformat()
        }


async def analyze_discrepancies_node(state: ValidationWorkflowState) -> Dict[str, Any]:
    """
    Analyze detected discrepancies

    Args:
        state: Current workflow state

    Returns:
        Updated state dict
    """
    logger.info(f"Analyzing discrepancies for session {state['session_id']}")

    discrepancies = state.get("discrepancies", [])

    if not discrepancies:
        return {
            "current_step": "analyze_discrepancies",
            "completed_steps": ["analyze_discrepancies"],
            "workflow_status": WorkflowStatus.ANALYZING,
            "messages": ["No discrepancies to analyze"],
            "updated_at": datetime.utcnow().isoformat()
        }

    # Count by severity
    critical = sum(1 for d in discrepancies if d["severity"] == Severity.CRITICAL)
    major = sum(1 for d in discrepancies if d["severity"] == Severity.MAJOR)
    minor = sum(1 for d in discrepancies if d["severity"] == Severity.MINOR)

    # Determine if user confirmation required
    requires_user = critical > 0 or major > 0

    return {
        "current_step": "analyze_discrepancies",
        "completed_steps": ["analyze_discrepancies"],
        "workflow_status": WorkflowStatus.ANALYZING,
        "requires_user_confirmation": requires_user,
        "messages": [
            f"Analyzed {len(discrepancies)} discrepancies: "
            f"{critical} critical, {major} major, {minor} minor"
        ],
        "updated_at": datetime.utcnow().isoformat()
    }


async def require_user_confirmation_node(state: ValidationWorkflowState) -> Dict[str, Any]:
    """
    Set state to await user confirmation

    Args:
        state: Current workflow state

    Returns:
        Updated state dict
    """
    logger.info(f"Requiring user confirmation for session {state['session_id']}")

    return {
        "current_step": "require_user_confirmation",
        "completed_steps": ["require_user_confirmation"],
        "workflow_status": WorkflowStatus.AWAITING_USER,
        "awaiting_user": True,
        "messages": ["Awaiting user confirmation of discrepancies"],
        "updated_at": datetime.utcnow().isoformat()
    }


async def generate_report_node(state: ValidationWorkflowState) -> Dict[str, Any]:
    """
    Generate final validation report

    Args:
        state: Current workflow state

    Returns:
        Updated state dict
    """
    logger.info(f"Generating report for session {state['session_id']}")

    # Determine final status, accounting for user confirmations on discrepancies.
    # A critical discrepancy that was explicitly confirmed by the user no longer
    # blocks the overall result — treat it as resolved.
    user_confirmations: Dict[str, Any] = state.get("user_confirmations", {})
    confirmed_ids = {
        disc_id
        for disc_id, conf in user_confirmations.items()
        if isinstance(conf, dict) and conf.get("confirmed") is True
    }

    unresolved_critical = [
        d for d in (state.get("critical_discrepancies") or [])
        if d.get("id") not in confirmed_ids
    ]

    if state.get("all_validations_passed") and not unresolved_critical:
        final_status = "passed"
    elif unresolved_critical:
        final_status = "failed"
    else:
        final_status = "requires_attention"

    return {
        "current_step": "generate_report",
        "completed_steps": ["generate_report"],
        "workflow_status": WorkflowStatus.COMPLETED,
        "final_status": final_status,
        "messages": [f"Report generated. Final status: {final_status}"],
        "updated_at": datetime.utcnow().isoformat()
    }
