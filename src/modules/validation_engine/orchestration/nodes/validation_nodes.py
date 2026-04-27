"""Workflow nodes for validation execution"""

import asyncio
from typing import Dict, Any, List, Tuple
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

        from ...core.base import ValidationContext, Discrepancy
        from ...discrepancy import get_discrepancy_classifier

        def _has_dot_paths(cfg: dict) -> bool:
            for val in cfg.get("validations", []):
                if isinstance(val, dict) and (
                    "." in str(val.get("source", ""))
                    or "." in str(val.get("target", ""))
                ):
                    return True
            return False

        async def _run_validator(
            validator_name: str,
            validator_config: dict,
            context: ValidationContext,
            source_data: Any,
            target_data: Any,
        ) -> Tuple[List[dict], List[dict]]:
            """Run a single validator and return (result_dicts, discrepancy_dicts)."""
            try:
                validator = validator_registry.get_validator(validator_name, validator_config)
                results = await validator.validate(
                    source_data=source_data,
                    target_data=target_data,
                    context=context,
                )
                result_dicts = [r.dict() for r in results]
                disc_dicts = []
                classifier = get_discrepancy_classifier()
                for result in results:
                    if not result.passed and not result.auto_fixed:
                        disc = Discrepancy(
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
                        disc = await classifier.classify(disc, context)
                        disc_dicts.append(disc.dict())
                logger.info("Validator '%s' completed: %d results", validator_name, len(results))
                return result_dicts, disc_dicts
            except Exception as e:
                logger.error("Validator '%s' failed: %s", validator_name, e)
                return [], []

        # Execute each workflow step sequentially (steps may depend on prior results).
        # Validators *within* a step are independent and run in parallel.
        for step_config in steps:
            step_name = step_config.get("name")
            validators = step_config.get("validators", [])
            step_severity = Severity.ERROR

            logger.info("Executing step: %s", step_name)

            base_validator_config = {
                **step_config.get("config", {}),
                "severity": step_severity,
            }
            is_cross_doc = (
                any(key in base_validator_config for key in ("calculations", "documents", "parties"))
                or _has_dot_paths(base_validator_config)
            )
            source_data = documents_to_validate if is_cross_doc else documents_to_validate.get(state["primary_document"], {})
            target_data = documents_to_validate if is_cross_doc else None

            context = ValidationContext(
                session_id=state["session_id"],
                use_case=state["use_case"],
                version=state["version"],
                documents=documents_to_validate,
                primary_document=state["primary_document"],
                supporting_documents=state["supporting_documents"],
                config=state["config"],
                tolerance_overrides=state["tolerance_overrides"],
            )

            # All validators in this step run concurrently.
            gather_results = await asyncio.gather(
                *[
                    _run_validator(name, base_validator_config, context, source_data, target_data)
                    for name in validators
                ]
            )
            for result_dicts, disc_dicts in gather_results:
                all_results.extend(result_dicts)
                all_discrepancies.extend(disc_dicts)

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
