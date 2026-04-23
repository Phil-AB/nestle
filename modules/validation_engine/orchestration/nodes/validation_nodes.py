"""Workflow nodes for validation execution"""

from typing import Dict, Any, List
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


def _apply_use_case_synonyms(
    documents: Dict[str, Dict[str, Any]],
    synonyms: Dict[str, List[str]],
) -> Dict[str, Dict[str, Any]]:
    """
    Apply use-case-specific synonym mappings so that validators can find
    fields by their canonical names even when extraction used document-specific
    labels.

    For example, if the invoice has ``your_order_number`` but the validator
    looks for ``po_number``, this adds ``po_number`` pointing to the same value.

    Original field names are **preserved** so the UI still shows the document's
    actual labels.  Canonical names are added *in addition* to the originals.
    """
    # Build reverse lookup: alias (lowercased) → canonical name
    reverse: Dict[str, str] = {}
    for canonical, aliases in synonyms.items():
        for alias in aliases:
            reverse[alias.lower()] = canonical

    result: Dict[str, Dict[str, Any]] = {}
    for doc_type, doc_data in documents.items():
        remapped: Dict[str, Any] = {}

        for field_name, value in doc_data.items():
            key_lower = field_name.lower()
            canonical = reverse.get(key_lower)

            # If this field is an alias of a *different* canonical name, add
            # the canonical mapping (only if not already present — the field
            # whose own name IS the canonical always wins).
            if canonical and canonical.lower() != key_lower:
                if canonical not in remapped:
                    remapped[canonical] = value
                    logger.debug(
                        f"Use-case synonym: {doc_type}.{field_name} → {canonical}"
                    )

            # Always keep the original field name
            remapped[field_name] = value

        result[doc_type] = remapped

    return result


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

        # Normalize all documents (global synonyms, formats, units)
        normalized_docs = await norm_engine.normalize_documents(
            documents=state["documents"]
        )

        # Apply use-case-specific synonym mappings.
        # The global NormalizationEngine handles same-label variants
        # (e.g., "Order No" → "order_number") and format/unit normalization.
        # Cross-concept mappings like "your_order_number" → "po_number" come
        # from the use-case config and are applied here as a second pass.
        uc_config = state.get("config", {})
        if isinstance(uc_config, dict):
            uc_config = uc_config.get("use_case", uc_config)
        uc_synonyms = (
            (uc_config or {}).get("normalization", {}).get("synonyms", {})
            if isinstance(uc_config, dict) else {}
        )
        if uc_synonyms:
            normalized_docs = _apply_use_case_synonyms(normalized_docs, uc_synonyms)
            logger.info(
                f"Applied {len(uc_synonyms)} use-case synonym mappings to "
                f"{len(normalized_docs)} documents"
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

        # Even when global normalization fails, apply use-case synonyms so
        # validators can at least resolve field names on the raw documents.
        fallback_docs = state["documents"]
        uc_config = state.get("config", {})
        if isinstance(uc_config, dict):
            uc_config = uc_config.get("use_case", uc_config)
        uc_synonyms = (
            (uc_config or {}).get("normalization", {}).get("synonyms", {})
            if isinstance(uc_config, dict) else {}
        )
        if uc_synonyms:
            fallback_docs = _apply_use_case_synonyms(fallback_docs, uc_synonyms)

        return {
            "current_step": "normalize",
            "failed_steps": ["normalize"],
            "normalized": False,
            "normalized_documents": fallback_docs,
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
            step_severity = Severity.ERROR

            logger.info(f"Executing step: {step_name}")

            # Execute validators in this step
            for validator_name in validators:
                try:
                    # Merge step-level severity into validator config so validators
                    # inherit the correct default instead of always falling back to MINOR.
                    validator_config = {
                        **step_config.get("config", {}),
                        "severity": step_severity,
                    }

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

                    # Extract discrepancies and run them through the classifier
                    for result in results:
                        if not result.passed and not result.auto_fixed:
                            from ...core.base import Discrepancy
                            from ...discrepancy import get_discrepancy_classifier
                            discrepancy = Discrepancy(
                                field_name=result.field_name or "unknown",
                                source_document=result.source_document,
                                target_document=result.target_document,
                                source_value=result.source_value,
                                target_value=result.target_value,
                                difference=result.discrepancy,
                                severity=result.severity,
                                confidence=result.confidence,
                                message=result.message,
                            )
                            # Classify type first, then severity (type must be set
                            # before severity rules check discrepancy_type)
                            discrepancy = await get_discrepancy_classifier().classify(
                                discrepancy, context
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

        return {
            "current_step": "validate",
            "completed_steps": ["validate"],
            "workflow_status": WorkflowStatus.VALIDATING,
            "validation_results": all_results,
            "all_validations_passed": all_passed,
            "discrepancies": all_discrepancies,
            "messages": [
                f"Validation completed: {passed}/{len(all_results)} passed, "
                f"{len(all_discrepancies)} discrepancies found"
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

    # No severity tiers — every discrepancy requires attention.
    # Any failure triggers user confirmation before the shipment can proceed.
    requires_user = len(discrepancies) > 0

    return {
        "current_step": "analyze_discrepancies",
        "completed_steps": ["analyze_discrepancies"],
        "workflow_status": WorkflowStatus.ANALYZING,
        "requires_user_confirmation": requires_user,
        "messages": [
            f"Analyzed {len(discrepancies)} discrepancies: "
            f"{len(discrepancies)} requiring attention"
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

    # No severity tiers — any unresolved discrepancy blocks the shipment.
    # A discrepancy confirmed by the user is treated as reviewed/accepted.
    user_confirmations: Dict[str, Any] = state.get("user_confirmations", {})
    confirmed_ids = {
        disc_id
        for disc_id, conf in user_confirmations.items()
        if isinstance(conf, dict) and conf.get("confirmed") is True
    }

    all_discrepancies = state.get("discrepancies") or []
    # str() normalises uuid.UUID objects and plain strings to the same type
    unresolved = [d for d in all_discrepancies if str(d.get("id", "")) not in confirmed_ids]

    if state.get("all_validations_passed") and not all_discrepancies:
        final_status = "passed"
    elif unresolved:
        final_status = "failed"
    else:
        # All discrepancies were reviewed and confirmed by the user
        final_status = "requires_attention"

    return {
        "current_step": "generate_report",
        "completed_steps": ["generate_report"],
        "workflow_status": WorkflowStatus.COMPLETED,
        "final_status": final_status,
        "messages": [f"Report generated. Final status: {final_status}"],
        "updated_at": datetime.utcnow().isoformat()
    }
