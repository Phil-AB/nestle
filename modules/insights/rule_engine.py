"""
Rule Engine - Rule-based scoring and decision-making.

Executes business rules from criteria.yaml config.
100% rule-based, no LLM.
"""

from typing import Dict, Any, List, Optional
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class RuleEngine:
    """
    Executes business rules for risk scoring, eligibility, and decisions.

    Uses criteria.yaml config to:
    1. Calculate risk scores using weighted factors
    2. Classify risk levels
    3. Determine product eligibility
    4. Make automated decisions
    """

    def __init__(self, criteria_config: Dict[str, Any]):
        """
        Initialize rule engine with criteria config.

        Args:
            criteria_config: Criteria configuration from YAML
        """
        self.config = criteria_config
        self.risk_config = criteria_config.get("risk_assessment", {})
        self.product_config = criteria_config.get("product_eligibility", {})
        self.decision_config = criteria_config.get("automated_decisions", {})

    def calculate_risk_score(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate risk score using weighted factors.

        Args:
            profile: Normalized customer profile

        Returns:
            Risk assessment with score, level, breakdown

        Example:
            >>> profile = {"employment_status": "employed", "monthly_income": 6800, "age": 42}
            >>> assessment = engine.calculate_risk_score(profile)
            >>> assessment["risk_score"]
            72
            >>> assessment["risk_level"]
            "Low Risk"
        """
        weights = self.risk_config.get("weights", {})
        scoring_breakdown = []
        total_score = 0.0

        # Evaluate each risk factor
        for factor_name, weight in weights.items():
            factor_config = self.risk_config.get(factor_name, {})

            # Calculate factor score
            factor_score, reasoning, data_points = self._evaluate_factor(
                factor_name,
                factor_config,
                profile
            )

            # Apply weight
            weighted_score = factor_score * weight

            # Add to breakdown
            scoring_breakdown.append({
                "factor_name": factor_name,
                "score": factor_score,
                "weight": weight,
                "weighted_score": round(weighted_score, 2),
                "confidence": 1.0,  # Rule-based = 100% confidence
                "reasoning": reasoning,
                "data_points": data_points
            })

            total_score += weighted_score

        # Round total score
        risk_score = round(total_score)

        # Classify risk level
        risk_level_info = self._classify_risk_level(risk_score)

        # Identify positive factors and concerns
        factors = self._identify_factors(scoring_breakdown)

        return {
            "risk_score": risk_score,
            "risk_level": risk_level_info["label"],
            "creditworthiness": risk_level_info["creditworthiness"],
            "scoring_breakdown": scoring_breakdown,
            "factors": factors,
            "reasoning": self._generate_risk_reasoning(scoring_breakdown, risk_level_info),
            "calculation_summary": self._generate_calculation_summary(scoring_breakdown, risk_score)
        }

    def _evaluate_factor(
        self,
        factor_name: str,
        factor_config: Dict[str, Any],
        profile: Dict[str, Any]
    ) -> tuple[float, str, List[str]]:
        """
        Evaluate a single risk factor.

        Args:
            factor_name: Factor name (e.g., "employment_stability")
            factor_config: Factor configuration
            profile: Customer profile

        Returns:
            Tuple of (score, reasoning, data_points)
        """
        # Handle computed fields
        computed_fields = factor_config.get("computed_fields", {})
        enriched_profile = self._compute_fields(profile, computed_fields)

        # Get rules
        rules = factor_config.get("rules", [])

        # Evaluate rules in order
        for rule in rules:
            conditions = rule.get("conditions", [])

            # Empty conditions = default/fallback rule
            if not conditions:
                score = rule.get("score", 0)
                return score, rule.get("name", "default"), []

            # Evaluate all conditions
            if self._evaluate_conditions(conditions, enriched_profile):
                score = rule.get("score", 0)
                reasoning = rule.get("name", "")
                data_points = self._extract_data_points(conditions, enriched_profile)
                return score, reasoning, data_points

        # No matching rule - return 0
        logger.warning(f"No matching rule for factor: {factor_name}")
        return 0, "no_match", []

    def _compute_fields(
        self,
        profile: Dict[str, Any],
        computed_fields: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compute derived fields using formulas.

        Args:
            profile: Customer profile
            computed_fields: Computed field definitions

        Returns:
            Profile with computed fields added
        """
        enriched = profile.copy()

        for field_name, field_config in computed_fields.items():
            formula = field_config.get("formula")
            fallback = field_config.get("fallback")

            if not formula:
                continue

            try:
                # Evaluate formula
                # Simple formula evaluation - can be extended
                result = self._evaluate_formula(formula, profile)
                enriched[field_name] = result
            except Exception as e:
                logger.debug(f"Failed to compute {field_name}: {e}")
                enriched[field_name] = fallback

        return enriched

    def _evaluate_formula(self, formula: str, profile: Dict[str, Any]) -> Optional[float]:
        """
        Evaluate a simple formula.

        Args:
            formula: Formula string (e.g., "monthly_income * 6")
            profile: Customer profile

        Returns:
            Computed value or None
        """
        # Replace field names with values
        expression = formula
        for field_name, value in profile.items():
            if value is not None:
                # Replace field name with value in formula
                expression = expression.replace(field_name, str(value))

        # Evaluate expression (safe for simple arithmetic)
        try:
            # Only allow safe operations
            allowed_chars = set("0123456789.+-*/ ()")
            if all(c in allowed_chars for c in expression.replace(" ", "")):
                result = eval(expression)
                return float(result) if result is not None else None
        except Exception as e:
            logger.debug(f"Formula evaluation failed: {e}")

        return None

    def _evaluate_conditions(
        self,
        conditions: List[Dict[str, Any]],
        profile: Dict[str, Any]
    ) -> bool:
        """
        Evaluate all conditions (AND logic).

        Args:
            conditions: List of condition dictionaries
            profile: Customer profile

        Returns:
            True if all conditions met
        """
        for condition in conditions:
            field = condition.get("field")
            operator = condition.get("operator")
            value = condition.get("value")

            if field is None or operator is None:
                continue

            profile_value = profile.get(field)

            # Evaluate condition
            if not self._evaluate_condition(profile_value, operator, value):
                return False

        return True

    def _evaluate_condition(
        self,
        profile_value: Any,
        operator: str,
        expected_value: Any
    ) -> bool:
        """
        Evaluate a single condition.

        Args:
            profile_value: Actual value from profile
            operator: Comparison operator
            expected_value: Expected value

        Returns:
            True if condition met
        """
        if operator == "equals":
            return profile_value == expected_value

        elif operator == "not_equals":
            return profile_value != expected_value

        elif operator == "in":
            return profile_value in expected_value

        elif operator == "not_in":
            return profile_value not in expected_value

        elif operator == "contains":
            return expected_value in str(profile_value) if profile_value else False

        elif operator == "contains_any":
            if not profile_value:
                return False
            profile_str = str(profile_value).lower()
            return any(str(term).lower() in profile_str for term in expected_value)

        elif operator == "gt":
            try:
                return float(profile_value) > float(expected_value)
            except (ValueError, TypeError):
                return False

        elif operator == "gte":
            try:
                return float(profile_value) >= float(expected_value)
            except (ValueError, TypeError):
                return False

        elif operator == "lt":
            try:
                return float(profile_value) < float(expected_value)
            except (ValueError, TypeError):
                return False

        elif operator == "lte":
            try:
                return float(profile_value) <= float(expected_value)
            except (ValueError, TypeError):
                return False

        elif operator == "is_null":
            return profile_value is None

        elif operator == "is_not_null":
            return profile_value is not None

        else:
            logger.warning(f"Unknown operator: {operator}")
            return False

    def _extract_data_points(
        self,
        conditions: List[Dict[str, Any]],
        profile: Dict[str, Any]
    ) -> List[str]:
        """Extract relevant data points from profile."""
        data_points = []

        for condition in conditions:
            field = condition.get("field")
            if field and field in profile:
                value = profile[field]
                if value is not None:
                    data_points.append(f"{field}: {value}")

        return data_points

    def _classify_risk_level(self, risk_score: int) -> Dict[str, Any]:
        """
        Classify risk level based on score.

        Args:
            risk_score: Total risk score

        Returns:
            Risk level info dictionary
        """
        risk_levels = self.risk_config.get("risk_levels", [])

        for level in risk_levels:
            min_score = level.get("min_score", 0)
            max_score = level.get("max_score", 100)

            if min_score <= risk_score <= max_score:
                return level

        # Default fallback
        return {
            "name": "unknown",
            "label": "Unknown",
            "creditworthiness": "Unknown"
        }

    def _identify_factors(
        self,
        scoring_breakdown: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """
        Identify positive factors and concerns.

        Args:
            scoring_breakdown: Scoring breakdown list

        Returns:
            Dictionary with positive and concerns lists
        """
        positive = []
        concerns = []

        for factor in scoring_breakdown:
            factor_name = factor["factor_name"]
            score = factor["score"]
            weighted = factor["weighted_score"]

            # High weighted score = positive factor
            if weighted >= (factor["weight"] * 20):  # > 20% of max
                positive.append(f"{factor_name}: {factor['reasoning']}")
            # Low weighted score = concern
            elif weighted < (factor["weight"] * 10):  # < 10% of max
                concerns.append(f"{factor_name}: {factor['reasoning']}")

        return {
            "positive": positive,
            "concerns": concerns
        }

    def _generate_risk_reasoning(
        self,
        scoring_breakdown: List[Dict[str, Any]],
        risk_level_info: Dict[str, Any]
    ) -> str:
        """Generate human-readable risk reasoning."""
        parts = [
            f"Risk classified as {risk_level_info['label']} with creditworthiness rated as {risk_level_info['creditworthiness']}."
        ]

        # Add top contributing factors
        top_factors = sorted(scoring_breakdown, key=lambda x: x["weighted_score"], reverse=True)[:3]
        factor_names = [f["factor_name"].replace("_", " ") for f in top_factors]
        parts.append(f"Key factors: {', '.join(factor_names)}.")

        return " ".join(parts)

    def _generate_calculation_summary(
        self,
        scoring_breakdown: List[Dict[str, Any]],
        risk_score: int
    ) -> str:
        """Generate calculation summary."""
        lines = ["Risk score calculation:"]

        for factor in scoring_breakdown:
            name = factor["factor_name"].replace("_", " ").title()
            score = factor["score"]
            weight = factor["weight"]
            weighted = factor["weighted_score"]
            lines.append(f"  {name}: {score} × {weight} = {weighted}")

        lines.append(f"Total Risk Score: {risk_score}")

        return "\n".join(lines)

    def determine_product_eligibility(
        self,
        profile: Dict[str, Any],
        risk_assessment: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Determine product eligibility.

        Args:
            profile: Customer profile
            risk_assessment: Risk assessment results

        Returns:
            Dictionary of products with eligibility details
        """
        enriched_profile = {**profile, **risk_assessment}
        products = {}

        for product_id, product_config in self.product_config.items():
            eligibility = self._check_product_eligibility(
                product_id,
                product_config,
                enriched_profile
            )
            products[product_id] = eligibility

        return products

    def _check_product_eligibility(
        self,
        product_id: str,
        product_config: Dict[str, Any],
        enriched_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check eligibility for a single product."""
        eligibility_rules = product_config.get("eligibility_rules", [])

        # Check all rules
        eligible = self._evaluate_conditions(eligibility_rules, enriched_profile)

        if not eligible:
            return {
                "eligible": False,
                "product_name": product_config.get("product_name", product_id),
                "reason": "Does not meet eligibility criteria"
            }

        # Calculate loan amount
        loan_config = product_config.get("loan_amount", {})
        max_amount = self._calculate_amount(loan_config, enriched_profile)

        # Determine interest rate
        interest_rate = self._determine_interest_rate(
            product_config.get("interest_rate", {}),
            enriched_profile
        )

        # Get tenor
        tenor_config = product_config.get("tenor", {})

        return {
            "eligible": True,
            "product_name": product_config.get("product_name", product_id),
            "max_amount": max_amount,
            "recommended_amount": max_amount * 0.8,  # 80% of max
            "interest_rate": interest_rate,
            "term_months": tenor_config.get("default_months", 24),
            "reason": "Meets all eligibility criteria"
        }

    def _calculate_amount(
        self,
        loan_config: Dict[str, Any],
        profile: Dict[str, Any]
    ) -> float:
        """Calculate max loan amount using formula."""
        formula = loan_config.get("formula")
        cap = loan_config.get("max_amount", 999999)
        min_amount = loan_config.get("min_amount", 0)

        if formula:
            calculated = self._evaluate_formula(formula, profile)
            if calculated:
                return min(max(calculated, min_amount), cap)

        return cap

    def _determine_interest_rate(
        self,
        rate_config: Dict[str, Any],
        profile: Dict[str, Any]
    ) -> float:
        """Determine interest rate based on risk."""
        if rate_config.get("fixed"):
            return rate_config.get("rate", 30.0)

        if rate_config.get("risk_based"):
            rates = rate_config.get("rates", [])
            risk_score = profile.get("risk_score", 0)

            for rate_tier in rates:
                min_score = rate_tier.get("risk_score_min", 0)
                max_score = rate_tier.get("risk_score_max", 100)

                if min_score <= risk_score <= max_score:
                    return rate_tier.get("rate", 30.0)

        return rate_config.get("rate", 30.0)

    def make_automated_decisions(
        self,
        profile: Dict[str, Any],
        risk_assessment: Dict[str, Any],
        product_eligibility: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Make automated decisions.

        Args:
            profile: Customer profile
            risk_assessment: Risk assessment results
            product_eligibility: Product eligibility results

        Returns:
            Dictionary of automated decisions
        """
        enriched_profile = {**profile, **risk_assessment}
        decisions = {}

        for decision_id, decision_config in self.decision_config.items():
            decision = self._make_decision(
                decision_id,
                decision_config,
                enriched_profile
            )
            decisions[decision_id] = decision

        return decisions

    def _make_decision(
        self,
        decision_id: str,
        decision_config: Dict[str, Any],
        enriched_profile: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make a single automated decision."""
        # Handle computed fields for this decision
        computed_fields = decision_config.get("computed_fields", {})
        profile_with_computed = self._compute_fields(enriched_profile, computed_fields)

        # Evaluate rules in order
        rules = decision_config.get("rules", [])

        for rule in rules:
            conditions = rule.get("conditions", [])

            if self._evaluate_conditions(conditions, profile_with_computed):
                # Handle decision or formula
                if "decision" in rule:
                    return {
                        "decision": rule["decision"],
                        "rule_name": rule.get("name"),
                        "message": rule.get("message", ""),
                        "confidence": 1.0
                    }
                elif "formula" in rule:
                    value = self._evaluate_formula(rule["formula"], profile_with_computed)
                    return {
                        "value": value,
                        "rule_name": rule.get("name"),
                        "confidence": 1.0
                    }

        # No matching rule
        return {
            "decision": "UNKNOWN",
            "message": "No matching rule found",
            "confidence": 0.0
        }
