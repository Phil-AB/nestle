"""Main validation engine"""

from typing import Dict, Any, List, Optional
from uuid import UUID

from .base import ValidationContext, ValidationResult, Discrepancy, ValidationResultSummary
from .session_manager import get_session_manager
from .config_loader import get_config_loader
from .result_aggregator import ResultAggregator
from ..validators.validator_registry import get_validator_registry
from ..utils.constants import WorkflowStep, ValidationStatus, Severity
from ..utils.exceptions import ValidationWorkflowException
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class ValidationEngine:
    """
    Main validation engine

    Orchestrates validation workflow:
    1. Session creation
    2. Configuration loading
    3. Validator execution
    4. Result aggregation
    5. Discrepancy detection
    """

    def __init__(self):
        """Initialize validation engine"""
        self.session_manager = get_session_manager()
        self.config_loader = get_config_loader()
        self.validator_registry = get_validator_registry()
        self.result_aggregator = ResultAggregator()

        logger.info("ValidationEngine initialized")

    async def create_validation_session(
        self,
        use_case: str,
        documents: Dict[str, Dict[str, Any]],
        tolerance_overrides: Optional[Dict[str, float]] = None,
        user_provided_data: Optional[Dict[str, Any]] = None
    ) -> ValidationContext:
        """
        Create a new validation session

        Args:
            use_case: Use case name (e.g., "boe_validation")
            documents: Extracted document data {doc_type: data}
            tolerance_overrides: Per-session tolerance overrides
            user_provided_data: User-provided data for missing fields

        Returns:
            ValidationContext

        Raises:
            UseCaseNotFoundException: If use case not found
            ValidationConfigException: If config is invalid
        """
        # Load config to validate use case exists
        config = self.config_loader.load_use_case(use_case)
        use_case_config = config.get("use_case", {})

        # Extract document structure from config
        documents_config = use_case_config.get("documents", {})

        # Determine primary and supporting documents
        primary_doc_config = documents_config.get("primary")
        if isinstance(primary_doc_config, dict):
            primary_document = primary_doc_config.get("type")
        else:
            primary_document = primary_doc_config

        supporting_docs_config = documents_config.get("supporting", [])
        supporting_documents = []
        for doc_config in supporting_docs_config:
            if isinstance(doc_config, dict):
                supporting_documents.append(doc_config.get("type"))
            else:
                supporting_documents.append(doc_config)

        # Create session
        context = await self.session_manager.create_session(
            use_case=use_case,
            documents=documents,
            primary_document=primary_document,
            supporting_documents=supporting_documents,
            tolerance_overrides=tolerance_overrides,
            user_provided_data=user_provided_data
        )

        logger.info(f"Created validation session {context.session_id} for use case '{use_case}'")

        return context

    async def run_validation_workflow(
        self,
        session_id: UUID,
        skip_steps: Optional[List[str]] = None
    ) -> ValidationResultSummary:
        """
        Run complete validation workflow

        Args:
            session_id: Validation session ID
            skip_steps: Optional list of steps to skip

        Returns:
            ValidationResultSummary

        Raises:
            SessionNotFoundException: If session not found
            ValidationWorkflowException: If workflow fails
        """
        context = await self.session_manager.get_session(session_id)
        skip_steps = skip_steps or []

        logger.info(f"Starting validation workflow for session {session_id}")

        try:
            # Get workflow configuration
            use_case_config = context.config.get("use_case", {})
            workflow_config = use_case_config.get("workflow", {})
            steps = workflow_config.get("steps", [])

            # Execute workflow steps
            for step_config in steps:
                step_name = step_config.get("name")

                if step_name in skip_steps:
                    logger.info(f"Skipping step: {step_name}")
                    continue

                logger.info(f"Executing step: {step_name}")

                # Update current step
                await self.session_manager.update_step(session_id, step_name)

                # Execute step
                await self._execute_validation_step(
                    context=context,
                    step_config=step_config
                )

            # Generate summary
            summary = await self.session_manager.get_summary(session_id)

            logger.info(
                f"Validation workflow completed for session {session_id}. "
                f"Status: {self.result_aggregator.determine_final_status(context, summary)}"
            )

            return summary

        except Exception as e:
            logger.error(f"Validation workflow failed for session {session_id}: {str(e)}")
            raise ValidationWorkflowException(
                f"Validation workflow failed: {str(e)}"
            ) from e

    async def _execute_validation_step(
        self,
        context: ValidationContext,
        step_config: Dict[str, Any]
    ):
        """
        Execute a single validation step

        Args:
            context: Validation context
            step_config: Step configuration from workflow

        Raises:
            ValidationWorkflowException: If step execution fails
        """
        step_name = step_config.get("name")
        validators = step_config.get("validators", [])
        step_severity = Severity.ERROR
        on_failure = step_config.get("on_failure", "continue")

        logger.debug(f"Step '{step_name}' using validators: {validators}")

        step_results: List[ValidationResult] = []
        step_discrepancies: List[Discrepancy] = []

        # Execute each validator in the step
        for validator_name in validators:
            try:
                # Get validator config (merge step config with validator defaults)
                validator_config = step_config.get("config", {})

                # Get validator instance
                validator = self.validator_registry.get_validator(
                    validator_name,
                    validator_config
                )

                # Determine source and target data for the validator.
                #
                # Cross-document validators (tolerance_validator, calculation_validator,
                # n_way_matcher, shipper_consignee_validator, incoterm_validator) resolve
                # document paths using dot-notation (e.g. "invoice.net_weight") — they need
                # the full documents dict.
                #
                # Single-document validators (required_fields_validator, range_validator,
                # regex_validator) use plain field names and expect the primary doc's flat
                # fields dict.
                #
                # Heuristic: a validator is cross-doc if its config uses dot-notation paths
                # OR if it explicitly lists multiple documents / parties.
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
                    source_data = context.documents
                    target_data = context.documents
                else:
                    source_data = context.documents.get(context.primary_document, {})
                    target_data = None

                # Execute validation
                results = await validator.validate(
                    source_data=source_data,
                    target_data=target_data,
                    context=context
                )

                # Apply step severity to results
                for result in results:
                    if not result.passed and result.severity == "info":
                        result.severity = step_severity

                step_results.extend(results)

                # Convert failed validations to discrepancies
                for result in results:
                    if not result.passed and not result.auto_fixed:
                        discrepancy = self._result_to_discrepancy(result)
                        step_discrepancies.append(discrepancy)

                logger.debug(
                    f"Validator '{validator_name}' completed: "
                    f"{len(results)} results, "
                    f"{sum(1 for r in results if r.passed)} passed"
                )

            except Exception as e:
                logger.error(
                    f"Validator '{validator_name}' failed in step '{step_name}': {str(e)}"
                )

                if on_failure == "stop":
                    raise ValidationWorkflowException(
                        f"Step '{step_name}' failed with validator '{validator_name}': {str(e)}"
                    ) from e
                elif on_failure == "flag_and_continue":
                    # Create a failed result
                    failed_result = ValidationResult(
                        validator_name=validator_name,
                        validator_type="unknown",
                        passed=False,
                        confidence=0.0,
                        severity=step_severity,
                        message=f"Validator execution failed: {str(e)}"
                    )
                    step_results.append(failed_result)

        # Add results to session
        await self.session_manager.add_validation_results(context.session_id, step_results)
        await self.session_manager.add_discrepancies(context.session_id, step_discrepancies)

        # Update context reference
        context = await self.session_manager.get_session(context.session_id)

    def _result_to_discrepancy(self, result: ValidationResult) -> Discrepancy:
        """
        Convert ValidationResult to Discrepancy

        Args:
            result: Validation result

        Returns:
            Discrepancy
        """
        return Discrepancy(
            field_name=result.field_name or "unknown",
            source_document=result.source_document,
            target_document=result.target_document,
            source_value=result.source_value,
            target_value=result.target_value,
            difference=result.discrepancy,
            severity=result.severity,
            confidence=result.confidence,
            auto_fixed=result.auto_fixed,
            metadata=result.metadata
        )

    async def get_validation_report(
        self,
        session_id: UUID,
        format: str = "json"
    ) -> Dict[str, Any]:
        """
        Get validation report

        Args:
            session_id: Validation session ID
            format: Report format (json, pdf, csv)

        Returns:
            Validation report

        Raises:
            SessionNotFoundException: If session not found
        """
        context = await self.session_manager.get_session(session_id)
        summary = await self.session_manager.get_summary(session_id)

        report = self.result_aggregator.generate_validation_report(
            context=context,
            summary=summary
        )

        logger.info(f"Generated validation report for session {session_id}")

        return report

    async def add_user_confirmation(
        self,
        session_id: UUID,
        discrepancy_id: str,
        confirmed: bool,
        comment: Optional[str] = None
    ):
        """
        Add user confirmation for discrepancy

        Args:
            session_id: Validation session ID
            discrepancy_id: Discrepancy UUID
            confirmed: Whether user confirmed discrepancy
            comment: Optional user comment
        """
        await self.session_manager.add_user_confirmation(
            session_id=session_id,
            discrepancy_id=discrepancy_id,
            confirmed=confirmed,
            comment=comment
        )

        logger.info(
            f"User {'confirmed' if confirmed else 'rejected'} "
            f"discrepancy {discrepancy_id} in session {session_id}"
        )

    async def add_user_data(
        self,
        session_id: UUID,
        field_name: str,
        value: Any
    ):
        """
        Add user-provided data for missing field

        Args:
            session_id: Validation session ID
            field_name: Field name
            value: Field value
        """
        await self.session_manager.add_user_data(
            session_id=session_id,
            field_name=field_name,
            value=value
        )

        logger.info(f"Added user data for field '{field_name}' in session {session_id}")

    async def get_session_status(self, session_id: UUID) -> Dict[str, Any]:
        """
        Get validation session status

        Args:
            session_id: Validation session ID

        Returns:
            Dictionary with session status

        Raises:
            SessionNotFoundException: If session not found
        """
        context = await self.session_manager.get_session(session_id)
        summary = await self.session_manager.get_summary(session_id)
        final_status = self.result_aggregator.determine_final_status(context, summary)

        return {
            "session_id": str(session_id),
            "use_case": context.use_case,
            "version": context.version,
            "current_step": context.current_step,
            "is_revalidation": context.is_revalidation,
            "final_status": final_status,
            "summary": summary.dict(),
            "created_at": context.created_at.isoformat(),
            "updated_at": context.updated_at.isoformat()
        }

    def list_use_cases(self) -> List[Dict[str, Any]]:
        """
        List all available use cases

        Returns:
            List of use case information
        """
        return self.config_loader.get_all_use_cases_info()

    def list_validators(self) -> List[Dict[str, Any]]:
        """
        List all registered validators

        Returns:
            List of validator information
        """
        return self.validator_registry.get_all_validators_info()


# Singleton instance
_validation_engine_instance: Optional[ValidationEngine] = None


def get_validation_engine() -> ValidationEngine:
    """
    Get singleton validation engine instance

    Returns:
        ValidationEngine instance
    """
    global _validation_engine_instance
    if _validation_engine_instance is None:
        _validation_engine_instance = ValidationEngine()
    return _validation_engine_instance
