"""
LLM Reasoning Layer for Insights.

Uses LLM to generate rich, contextual reasoning while following rule-based calculations.
The rules provide structure and auditability, the LLM provides nuanced insights.
"""

from typing import Dict, Any, List
from shared.utils.logger import setup_logger
from shared.utils.llm_config import get_llm_config_manager

logger = setup_logger(__name__)


class LLMReasoningEngine:
    """
    Generates LLM-powered reasoning following rule-based calculations.

    The rules calculate scores, the LLM explains why and provides insights.
    """

    def __init__(self, use_case_id: str, criteria_config: Dict[str, Any]):
        """
        Initialize LLM reasoning engine.

        Args:
            use_case_id: Use case identifier
            criteria_config: Criteria configuration (business rules)
        """
        self.use_case_id = use_case_id
        self.criteria_config = criteria_config

        # Get LLM for insights
        llm_manager = get_llm_config_manager()
        self.llm = llm_manager.get_llm("insights_service")

    def generate_risk_reasoning(
        self,
        profile: Dict[str, Any],
        risk_assessment: Dict[str, Any],
        criteria_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate detailed risk reasoning using LLM.

        Args:
            profile: Customer profile
            risk_assessment: Calculated risk scores (from rule engine)
            criteria_config: Business rules and criteria

        Returns:
            Enhanced risk assessment with LLM reasoning
        """
        prompt = self._build_risk_reasoning_prompt(profile, risk_assessment, criteria_config)

        try:
            # Use LLM to generate reasoning
            response = self.llm.invoke(prompt)
            reasoning = response.content if hasattr(response, 'content') else str(response)

            # Enhance risk assessment with LLM reasoning
            enhanced = risk_assessment.copy()
            enhanced['detailed_reasoning'] = reasoning
            enhanced['reasoning_source'] = 'llm_enhanced'

            return enhanced

        except Exception as e:
            logger.error(f"LLM reasoning failed: {e}")
            # Fallback to rule-based reasoning
            return risk_assessment

    def generate_recommendations(
        self,
        profile: Dict[str, Any],
        risk_assessment: Dict[str, Any],
        product_eligibility: Dict[str, Any],
        criteria_config: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate personalized recommendations using LLM.

        Args:
            profile: Customer profile
            risk_assessment: Risk assessment results
            product_eligibility: Product eligibility (from rule engine)
            criteria_config: Business rules

        Returns:
            Recommendations with LLM-generated insights
        """
        prompt = self._build_recommendations_prompt(
            profile,
            risk_assessment,
            product_eligibility,
            criteria_config
        )

        try:
            response = self.llm.invoke(prompt)
            reasoning = response.content if hasattr(response, 'content') else str(response)

            # Parse LLM response into structured recommendations
            recommendations = self._parse_recommendations(reasoning)

            return recommendations

        except Exception as e:
            logger.error(f"LLM recommendations failed: {e}")
            # Fallback to empty recommendations
            return {
                "next_steps": [],
                "improvement_areas": [],
                "opportunities": []
            }

    def _build_risk_reasoning_prompt(
        self,
        profile: Dict[str, Any],
        risk_assessment: Dict[str, Any],
        criteria_config: Dict[str, Any]
    ) -> str:
        """Build prompt for risk reasoning."""

        # Get risk score ranges from config
        risk_levels = criteria_config.get('risk_assessment', {}).get('risk_levels', [])

        prompt = f"""You are an expert credit risk analyst. Based on the rule-based risk assessment below, provide detailed reasoning and insights.

**CUSTOMER PROFILE:**
"""

        for key, value in profile.items():
            if value is not None:
                prompt += f"  - {key.replace('_', ' ').title()}: {value}\n"

        prompt += f"""

**CALCULATED RISK ASSESSMENT (Rule-Based):**
  - Risk Score: {risk_assessment['risk_score']}/100
  - Risk Level: {risk_assessment['risk_level']}
  - Creditworthiness: {risk_assessment['creditworthiness']}

**SCORING BREAKDOWN:**
"""

        for factor in risk_assessment['scoring_breakdown']:
            prompt += f"""  - {factor['factor_name'].replace('_', ' ').title()}: {factor['score']} × {factor['weight']} = {factor['weighted_score']}
    Reasoning: {factor['reasoning']}
"""

        prompt += f"""

**YOUR TASK:**
Provide a 2-3 paragraph analysis that:
1. Explains the risk assessment in plain language
2. Highlights the key factors driving the score
3. Provides context on the customer's creditworthiness
4. Discusses any concerns or positive indicators
5. Offers insights that would help a loan officer make a decision

**IMPORTANT:**
- Base your reasoning on the calculated scores above
- Reference specific factors from the scoring breakdown
- Keep it professional but accessible
- Focus on actionable insights

**RISK REASONING:**
"""

        return prompt

    def _build_recommendations_prompt(
        self,
        profile: Dict[str, Any],
        risk_assessment: Dict[str, Any],
        product_eligibility: Dict[str, Any],
        criteria_config: Dict[str, Any]
    ) -> str:
        """Build prompt for recommendations."""

        prompt = f"""You are a financial advisor providing personalized recommendations based on a customer's profile and eligibility.

**CUSTOMER PROFILE:**
"""

        for key, value in profile.items():
            if value is not None:
                prompt += f"  - {key.replace('_', ' ').title()}: {value}\n"

        prompt += f"""

**RISK ASSESSMENT:**
  - Risk Score: {risk_assessment['risk_score']}/100
  - Risk Level: {risk_assessment['risk_level']}
  - Creditworthiness: {risk_assessment['creditworthiness']}

**PRODUCT ELIGIBILITY:**
"""

        for product_id, details in product_eligibility.items():
            status = "✓ Eligible" if details['eligible'] else "✗ Not Eligible"
            prompt += f"  - {details.get('product_name', product_id)}: {status}\n"
            if details['eligible'] and details.get('max_amount'):
                prompt += f"    Max Amount: GHS {details['max_amount']:,}\n"

        prompt += """

**YOUR TASK:**
Provide 3-5 personalized recommendations in the following format:

NEXT STEPS:
1. [Immediate action the customer should take]
2. [Another specific next step]

IMPROVEMENT AREAS:
1. [How to improve creditworthiness]
2. [Financial habits to develop]

OPPORTUNITIES:
1. [Products or services they could benefit from]
2. [Financial goals to pursue]

**IMPORTANT:**
- Base recommendations on their actual eligibility and risk profile
- Be specific and actionable
- Consider their financial situation
- Prioritize practical steps

**RECOMMENDATIONS:**
"""

        return prompt

    def _parse_recommendations(self, llm_response: str) -> Dict[str, List[Dict[str, Any]]]:
        """Parse LLM response into structured recommendations."""

        # Simple parsing - extract sections
        recommendations = {
            "next_steps": [],
            "improvement_areas": [],
            "opportunities": []
        }

        try:
            # Split by sections
            if "NEXT STEPS:" in llm_response:
                next_steps_section = llm_response.split("NEXT STEPS:")[1].split("IMPROVEMENT AREAS:")[0]
                recommendations["next_steps"] = self._extract_bullet_points(next_steps_section)

            if "IMPROVEMENT AREAS:" in llm_response:
                improvement_section = llm_response.split("IMPROVEMENT AREAS:")[1].split("OPPORTUNITIES:")[0]
                recommendations["improvement_areas"] = self._extract_bullet_points(improvement_section)

            if "OPPORTUNITIES:" in llm_response:
                opportunities_section = llm_response.split("OPPORTUNITIES:")[1]
                recommendations["opportunities"] = self._extract_bullet_points(opportunities_section)

        except Exception as e:
            logger.debug(f"Failed to parse recommendations: {e}")

        return recommendations

    def _extract_bullet_points(self, text: str) -> List[Dict[str, Any]]:
        """Extract bullet points from text."""
        items = []
        lines = text.strip().split('\n')

        for line in lines:
            line = line.strip()
            # Match numbered or bullet points
            if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                # Remove number/bullet
                text = line.lstrip('0123456789.-•').strip()
                if text:
                    items.append({
                        "title": text[:100],  # First 100 chars as title
                        "description": text,
                        "priority": "medium",
                        "category": "recommendation"
                    })

        return items
