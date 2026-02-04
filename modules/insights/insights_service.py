"""
Universal Insights Service.

100% config-driven, rule-based insights generation for any use case.
"""

from typing import Dict, Any
from datetime import datetime
from shared.utils.logger import setup_logger
from modules.insights.config_loader import InsightsConfigLoader
from modules.insights.profile_extractor import ProfileExtractor
from modules.insights.rule_engine import RuleEngine
from modules.insights.llm_reasoning import LLMReasoningEngine

logger = setup_logger(__name__)


class InsightsService:
    """
    Universal insights generation service.

    Provides risk assessment, product eligibility, and automated decisions
    for any use case using config-driven rules.

    Features:
    - 100% config-driven (no hardcoding)
    - Rule-based (no LLM dependency)
    - Universal (works for loans, insurance, recruitment, etc.)
    - Fast and deterministic

    Example:
        >>> service = InsightsService(use_case_id="forms-capital-loan")
        >>> insights = service.generate_insights(raw_extracted_data)
        >>> insights["risk_score"]
        72
        >>> insights["product_eligibility"]["personal_loan"]["eligible"]
        True
    """

    def __init__(self, use_case_id: str):
        """
        Initialize insights service for a specific use case.

        Args:
            use_case_id: Use case identifier (e.g., "forms-capital-loan")

        Raises:
            FileNotFoundError: If use case configs not found
        """
        self.use_case_id = use_case_id

        # Load configs
        logger.info(f"Initializing insights service for use case: {use_case_id}")
        self.config_loader = InsightsConfigLoader(use_case_id)

        try:
            configs = self.config_loader.load_all()
            self.field_mapping_config = configs["field_mapping"]
            self.criteria_config = configs["criteria"]
            self.products_config = configs.get("products", {})

            logger.info(
                f"Loaded configs: "
                f"field_mapping v{self.field_mapping_config.get('version')}, "
                f"criteria v{self.criteria_config.get('version')}"
            )

        except FileNotFoundError as e:
            logger.error(f"Failed to load use case configs: {e}")
            raise

        # Initialize components
        self.profile_extractor = ProfileExtractor(self.field_mapping_config)
        self.rule_engine = RuleEngine(self.criteria_config)
        self.llm_reasoning = LLMReasoningEngine(use_case_id, self.criteria_config)

    def generate_insights(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate complete insights from raw extracted data.

        Args:
            raw_data: Raw extracted data from OCR/database

        Returns:
            Complete insights dictionary with:
            - customer_profile: Normalized profile
            - risk_assessment: Risk score, level, breakdown
            - product_eligibility: Eligible products with details
            - automated_decisions: Auto-approval, amounts, etc.

        Example:
            >>> raw_data = {
            ...     "surname": {"value": "mensah"},
            ...     "age": {"value": "4 2"},
            ...     "net_salary": {"value": "GHS 6,800"}
            ... }
            >>> insights = service.generate_insights(raw_data)
        """
        logger.info(f"Generating insights using rule-based engine")
        start_time = datetime.utcnow()

        # Step 1: Extract normalized customer profile (RULE-BASED)
        logger.debug("Extracting normalized profile from database...")
        customer_profile = self.profile_extractor.extract_profile(raw_data)

        # Step 2: Calculate risk assessment using rules (RULE-BASED)
        logger.debug("Calculating risk scores using thresholds and criteria...")
        risk_assessment = self.rule_engine.calculate_risk_score(customer_profile)

        # Step 3: LLM generates reasoning following the calculated scores
        logger.debug("Generating LLM reasoning based on calculated scores...")
        risk_assessment = self.llm_reasoning.generate_risk_reasoning(
            profile=customer_profile,
            risk_assessment=risk_assessment,
            criteria_config=self.criteria_config
        )

        # Step 4: Determine product eligibility (RULE-BASED)
        logger.debug("Determining product eligibility using rules...")
        product_eligibility = self.rule_engine.determine_product_eligibility(
            customer_profile,
            risk_assessment
        )

        # Step 5: LLM generates recommendations following eligibility
        logger.debug("Generating LLM recommendations...")
        recommendations = self.llm_reasoning.generate_recommendations(
            profile=customer_profile,
            risk_assessment=risk_assessment,
            product_eligibility=product_eligibility,
            criteria_config=self.criteria_config
        )

        # Step 6: Make automated decisions (RULE-BASED)
        logger.debug("Making automated decisions using rules...")
        automated_decisions = self.rule_engine.make_automated_decisions(
            customer_profile,
            risk_assessment,
            product_eligibility
        )

        # Calculate processing time
        processing_time = (datetime.utcnow() - start_time).total_seconds()

        logger.info(
            f"Insights generated in {processing_time:.2f}s: "
            f"risk_score={risk_assessment['risk_score']}, "
            f"risk_level={risk_assessment['risk_level']}"
        )

        return {
            "use_case_id": self.use_case_id,
            "customer_profile": customer_profile,
            "risk_assessment": risk_assessment,
            "product_eligibility": product_eligibility,
            "recommendations": recommendations,
            "automated_decisions": automated_decisions,
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "processing_time_seconds": round(processing_time, 3),
                "engine": "hybrid",  # Rule-based + LLM reasoning
                "scoring": "rule-based",
                "reasoning": "llm-enhanced",
                "config_version": {
                    "field_mapping": self.field_mapping_config.get("version"),
                    "criteria": self.criteria_config.get("version")
                }
            }
        }

    def validate_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate that profile has required fields.

        Args:
            profile: Customer profile

        Returns:
            Validation result with missing fields

        Example:
            >>> result = service.validate_profile(profile)
            >>> result["valid"]
            True
        """
        validation_config = self.criteria_config.get("validation", {})
        required_fields = validation_config.get("required_fields", [])

        missing_fields = []
        for field in required_fields:
            if field not in profile or profile[field] is None:
                missing_fields.append(field)

        return {
            "valid": len(missing_fields) == 0,
            "missing_fields": missing_fields,
            "required_fields": required_fields
        }

    def reload_configs(self):
        """
        Reload all configurations.

        Useful for picking up config changes without restarting.
        """
        logger.info(f"Reloading configs for use case: {self.use_case_id}")
        self.config_loader.reload()

        # Reload configs
        configs = self.config_loader.load_all()
        self.field_mapping_config = configs["field_mapping"]
        self.criteria_config = configs["criteria"]
        self.products_config = configs.get("products", {})

        # Reinitialize components
        self.profile_extractor = ProfileExtractor(self.field_mapping_config)
        self.rule_engine = RuleEngine(self.criteria_config)
        self.llm_reasoning = LLMReasoningEngine(self.use_case_id, self.criteria_config)

        logger.info("Configs reloaded successfully")
