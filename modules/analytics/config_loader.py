"""
Analytics Config Loader.

Loads use-case specific analytics configurations from YAML files.
"""

import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)

# Default config paths
CONFIG_BASE_PATH = Path(__file__).parent.parent.parent / "config" / "analytics"
USE_CASES_PATH = CONFIG_BASE_PATH / "use_cases"


class AnalyticsConfigLoader:
    """
    Loads analytics configuration for a specific use case.

    Config structure:
        config/analytics/use_cases/{use_case_id}/
        ├── metrics.yaml       # Metric definitions
        └── dimensions.yaml    # Dimension/breakdown definitions
    """

    def __init__(self, use_case_id: str, config_path: Optional[Path] = None):
        """
        Initialize config loader for a use case.

        Args:
            use_case_id: Use case identifier (e.g., "forms-capital-loan")
            config_path: Optional custom config path
        """
        self.use_case_id = use_case_id
        self.config_path = config_path or USE_CASES_PATH / use_case_id

        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Analytics config not found for use case: {use_case_id}. "
                f"Expected path: {self.config_path}"
            )

        self._cache: Dict[str, Any] = {}

    def load_all(self) -> Dict[str, Any]:
        """
        Load all configurations for the use case.

        Returns:
            Dictionary with all configs: metrics, dimensions
        """
        return {
            "metrics": self.load_metrics(),
            "dimensions": self.load_dimensions(),
        }

    def load_metrics(self) -> Dict[str, Any]:
        """Load metrics configuration."""
        return self._load_yaml("metrics.yaml")

    def load_dimensions(self) -> Dict[str, Any]:
        """Load dimensions configuration."""
        return self._load_yaml("dimensions.yaml")

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """
        Load a YAML config file.

        Args:
            filename: Config filename

        Returns:
            Parsed config dictionary
        """
        if filename in self._cache:
            return self._cache[filename]

        file_path = self.config_path / filename

        if not file_path.exists():
            logger.warning(f"Config file not found: {file_path}, using defaults")
            return {}

        try:
            with open(file_path, "r") as f:
                config = yaml.safe_load(f) or {}
            self._cache[filename] = config
            logger.debug(f"Loaded config: {filename}")
            return config

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse {filename}: {e}")
            raise ValueError(f"Invalid YAML in {filename}: {e}")

    def reload(self):
        """Clear cache and reload configs."""
        self._cache.clear()
        logger.info(f"Config cache cleared for use case: {self.use_case_id}")


def load_analytics_config(use_case_id: str) -> Dict[str, Any]:
    """
    Convenience function to load all analytics config for a use case.

    Args:
        use_case_id: Use case identifier

    Returns:
        Complete config dictionary
    """
    loader = AnalyticsConfigLoader(use_case_id)
    return loader.load_all()


def list_available_use_cases() -> list:
    """
    List all available analytics use cases.

    Returns:
        List of use case IDs
    """
    if not USE_CASES_PATH.exists():
        return []

    return [
        d.name for d in USE_CASES_PATH.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ]
