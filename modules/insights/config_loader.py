"""
Insights Configuration Loader.

Loads use-case specific configs (field_mapping, criteria, products).
100% config-driven, no hardcoding.
"""

import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class InsightsConfigLoader:
    """
    Loads use-case specific configuration for insights generation.

    Each use case has its own directory with:
    - field_mapping.yaml: Maps extracted fields → normalized profile
    - criteria.yaml: Scoring rules, eligibility, decisions
    - products.yaml: Product-specific configurations (optional)
    """

    def __init__(self, use_case_id: str, config_base_path: Optional[Path] = None):
        """
        Initialize config loader for a specific use case.

        Args:
            use_case_id: Use case identifier (e.g., "forms-capital-loan")
            config_base_path: Base path for configs (defaults to config/insights/use_cases/)
        """
        self.use_case_id = use_case_id

        if config_base_path is None:
            # Default: config/insights/use_cases/
            project_root = Path(__file__).parent.parent.parent
            config_base_path = project_root / "config" / "insights" / "use_cases"

        self.config_base_path = Path(config_base_path)
        self.use_case_path = self.config_base_path / use_case_id

        # Cached configs
        self._field_mapping: Optional[Dict[str, Any]] = None
        self._criteria: Optional[Dict[str, Any]] = None
        self._products: Optional[Dict[str, Any]] = None

    def load_field_mapping(self) -> Dict[str, Any]:
        """
        Load field mapping configuration.

        Returns:
            Field mapping config dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
        """
        if self._field_mapping is not None:
            return self._field_mapping

        config_path = self.use_case_path / "field_mapping.yaml"

        if not config_path.exists():
            raise FileNotFoundError(
                f"Field mapping config not found: {config_path}. "
                f"Create config/insights/use_cases/{self.use_case_id}/field_mapping.yaml"
            )

        try:
            with open(config_path, 'r') as f:
                self._field_mapping = yaml.safe_load(f)

            logger.info(f"Loaded field mapping for use case: {self.use_case_id}")
            return self._field_mapping

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse field mapping config: {e}")
            raise

    def load_criteria(self) -> Dict[str, Any]:
        """
        Load criteria configuration (scoring rules, eligibility).

        Returns:
            Criteria config dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
        """
        if self._criteria is not None:
            return self._criteria

        config_path = self.use_case_path / "criteria.yaml"

        if not config_path.exists():
            raise FileNotFoundError(
                f"Criteria config not found: {config_path}. "
                f"Create config/insights/use_cases/{self.use_case_id}/criteria.yaml"
            )

        try:
            with open(config_path, 'r') as f:
                self._criteria = yaml.safe_load(f)

            logger.info(f"Loaded criteria for use case: {self.use_case_id}")
            return self._criteria

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse criteria config: {e}")
            raise

    def load_products(self) -> Dict[str, Any]:
        """
        Load products configuration (optional).

        Returns:
            Products config dictionary or empty dict if not found
        """
        if self._products is not None:
            return self._products

        config_path = self.use_case_path / "products.yaml"

        if not config_path.exists():
            logger.debug(f"Products config not found (optional): {config_path}")
            self._products = {}
            return self._products

        try:
            with open(config_path, 'r') as f:
                self._products = yaml.safe_load(f)

            logger.info(f"Loaded products for use case: {self.use_case_id}")
            return self._products

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse products config: {e}")
            self._products = {}
            return self._products

    def load_all(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all configs for this use case.

        Returns:
            Dictionary with field_mapping, criteria, and products
        """
        return {
            "field_mapping": self.load_field_mapping(),
            "criteria": self.load_criteria(),
            "products": self.load_products()
        }

    def reload(self):
        """Clear cached configs and force reload."""
        self._field_mapping = None
        self._criteria = None
        self._products = None


def load_use_case_config(use_case_id: str) -> Dict[str, Dict[str, Any]]:
    """
    Convenience function to load all configs for a use case.

    Args:
        use_case_id: Use case identifier

    Returns:
        Dictionary with all configs

    Example:
        >>> config = load_use_case_config("forms-capital-loan")
        >>> field_mapping = config["field_mapping"]
        >>> criteria = config["criteria"]
    """
    loader = InsightsConfigLoader(use_case_id)
    return loader.load_all()
