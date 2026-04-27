"""Configuration loader for validation engine"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from functools import lru_cache

from ..utils.exceptions import (
    ValidationConfigException,
    UseCaseNotFoundException
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class ValidationConfigLoader:
    """
    Load and validate configuration for validation engine

    Loads use case configs from /config/validation/use_cases/
    Loads validator configs from /config/validation/validators/
    Loads normalization configs from /config/validation/normalization.yaml
    """

    def __init__(self, config_base_path: Optional[Path] = None):
        """
        Initialize config loader

        Args:
            config_base_path: Base path for config directory
                            Defaults to /config/validation/
        """
        if config_base_path is None:
            # Default to project root /config/validation/
            project_root = Path(__file__).parent.parent.parent.parent
            config_base_path = project_root / "config" / "validation"

        self.config_base_path = Path(config_base_path)
        self.use_cases_path = self.config_base_path / "use_cases"
        self.validators_path = self.config_base_path / "validators"
        self.normalization_config_path = self.config_base_path / "normalization.yaml"

        # Ensure directories exist
        self.use_cases_path.mkdir(parents=True, exist_ok=True)
        self.validators_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"ValidationConfigLoader initialized with base path: {self.config_base_path}")

    @lru_cache(maxsize=32)
    def load_use_case(self, use_case_name: str) -> Dict[str, Any]:
        """
        Load use case configuration

        Args:
            use_case_name: Name of use case (e.g., "boe_validation")

        Returns:
            Use case configuration dictionary

        Raises:
            UseCaseNotFoundException: If use case file not found
            ValidationConfigException: If config is invalid
        """
        config_file = self.use_cases_path / f"{use_case_name}.yaml"

        if not config_file.exists():
            raise UseCaseNotFoundException(
                f"Use case '{use_case_name}' not found at {config_file}"
            )

        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)

            # Validate config structure
            self._validate_use_case_config(config, use_case_name)

            logger.info(f"Loaded use case config: {use_case_name}")
            return config

        except yaml.YAMLError as e:
            raise ValidationConfigException(
                f"Failed to parse use case config '{use_case_name}': {str(e)}"
            )
        except Exception as e:
            raise ValidationConfigException(
                f"Error loading use case config '{use_case_name}': {str(e)}"
            )

    def _validate_use_case_config(self, config: Dict[str, Any], use_case_name: str):
        """
        Validate use case configuration structure

        Args:
            config: Configuration dictionary
            use_case_name: Name of use case

        Raises:
            ValidationConfigException: If config is invalid
        """
        # Check required top-level keys
        if "use_case" not in config:
            raise ValidationConfigException(
                f"Use case config '{use_case_name}' missing 'use_case' key"
            )

        use_case_config = config["use_case"]

        # Check required use case fields
        required_fields = ["name", "documents", "workflow"]
        for field in required_fields:
            if field not in use_case_config:
                raise ValidationConfigException(
                    f"Use case config '{use_case_name}' missing required field: {field}"
                )

        # Validate documents section
        documents = use_case_config.get("documents", {})
        if "primary" not in documents:
            raise ValidationConfigException(
                f"Use case config '{use_case_name}' missing 'documents.primary'"
            )

        # Validate workflow section
        workflow = use_case_config.get("workflow", {})
        if "steps" not in workflow:
            raise ValidationConfigException(
                f"Use case config '{use_case_name}' missing 'workflow.steps'"
            )

        steps = workflow.get("steps", [])
        if not steps:
            raise ValidationConfigException(
                f"Use case config '{use_case_name}' has empty workflow steps"
            )

        # Validate each step
        for i, step in enumerate(steps):
            if "name" not in step:
                raise ValidationConfigException(
                    f"Use case config '{use_case_name}' step {i} missing 'name'"
                )
            if "validators" not in step:
                raise ValidationConfigException(
                    f"Use case config '{use_case_name}' step '{step['name']}' missing 'validators'"
                )

    @lru_cache(maxsize=32)
    def load_validator_config(self, validator_name: str) -> Dict[str, Any]:
        """
        Load validator configuration

        Args:
            validator_name: Name of validator

        Returns:
            Validator configuration dictionary
            Returns empty dict if config file doesn't exist (validator uses defaults)

        Raises:
            ValidationConfigException: If config is invalid
        """
        config_file = self.validators_path / f"{validator_name}.yaml"

        if not config_file.exists():
            logger.debug("No config file for validator '%s', using defaults", validator_name)
            return {}

        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)

            logger.debug("Loaded validator config: %s", validator_name)
            return config.get("validator", {})

        except yaml.YAMLError as e:
            raise ValidationConfigException(
                f"Failed to parse validator config '{validator_name}': {str(e)}"
            )
        except Exception as e:
            raise ValidationConfigException(
                f"Error loading validator config '{validator_name}': {str(e)}"
            )

    @lru_cache(maxsize=1)
    def load_normalization_config(self) -> Dict[str, Any]:
        """
        Load normalization configuration

        Returns:
            Normalization configuration dictionary
            Returns empty dict if config file doesn't exist

        Raises:
            ValidationConfigException: If config is invalid
        """
        if not self.normalization_config_path.exists():
            logger.warning(
                f"Normalization config not found at {self.normalization_config_path}, "
                "using defaults"
            )
            return {}

        try:
            with open(self.normalization_config_path, 'r') as f:
                config = yaml.safe_load(f)

            logger.info("Loaded normalization config")
            return config.get("normalization", {})

        except yaml.YAMLError as e:
            raise ValidationConfigException(
                f"Failed to parse normalization config: {str(e)}"
            )
        except Exception as e:
            raise ValidationConfigException(
                f"Error loading normalization config: {str(e)}"
            )

    def list_use_cases(self) -> List[str]:
        """
        List all available use cases

        Returns:
            List of use case names
        """
        if not self.use_cases_path.exists():
            return []

        use_cases = []
        for config_file in self.use_cases_path.glob("*.yaml"):
            use_case_name = config_file.stem
            use_cases.append(use_case_name)

        return sorted(use_cases)

    def list_validators(self) -> List[str]:
        """
        List all validators with config files

        Returns:
            List of validator names
        """
        if not self.validators_path.exists():
            return []

        validators = []
        for config_file in self.validators_path.glob("*.yaml"):
            validator_name = config_file.stem
            validators.append(validator_name)

        return sorted(validators)

    def validate_all_at_startup(self) -> None:
        """
        Eagerly load and validate every use-case config file.

        Called once at application startup so malformed or missing configs
        raise immediately — before any request is served — rather than failing
        on the first user request.

        Raises:
            RuntimeError: Wraps any ValidationConfigException, causing the
                          application to abort startup cleanly.
        """
        use_cases = self.list_use_cases()
        if not use_cases:
            logger.warning(
                "No use-case config files found in %s — "
                "validation endpoints will reject all requests.",
                self.use_cases_path,
            )
            return

        errors: List[str] = []
        for use_case_name in use_cases:
            try:
                self.load_use_case(use_case_name)
                logger.info("Startup config check OK: %s", use_case_name)
            except Exception as e:
                errors.append(f"  • {use_case_name}: {e}")

        if errors:
            raise RuntimeError(
                "One or more use-case configs are invalid — aborting startup:\n"
                + "\n".join(errors)
            )

    def get_use_case_info(self, use_case_name: str) -> Dict[str, Any]:
        """
        Get metadata about a use case

        Args:
            use_case_name: Name of use case

        Returns:
            Dictionary with use case information

        Raises:
            UseCaseNotFoundException: If use case not found
        """
        config = self.load_use_case(use_case_name)
        use_case_config = config.get("use_case", {})

        return {
            "name": use_case_config.get("name"),
            "display_name": use_case_config.get("display_name"),
            "description": use_case_config.get("description"),
            "version": use_case_config.get("version", "1.0"),
            "documents": use_case_config.get("documents", {}),
            "workflow_steps": len(use_case_config.get("workflow", {}).get("steps", []))
        }

    def get_all_use_cases_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all available use cases

        Returns:
            List of use case information dictionaries
        """
        use_cases = self.list_use_cases()
        return [
            self.get_use_case_info(use_case)
            for use_case in use_cases
        ]

    def reload_config(self):
        """Clear cached configs to force reload"""
        self.load_use_case.cache_clear()
        self.load_validator_config.cache_clear()
        self.load_normalization_config.cache_clear()
        logger.info("Cleared config cache")


# Singleton instance
_config_loader_instance: Optional[ValidationConfigLoader] = None


def get_config_loader(config_base_path: Optional[Path] = None) -> ValidationConfigLoader:
    """
    Get singleton config loader instance

    Args:
        config_base_path: Base path for config directory (only used on first call)

    Returns:
        ValidationConfigLoader instance
    """
    global _config_loader_instance
    if _config_loader_instance is None:
        _config_loader_instance = ValidationConfigLoader(config_base_path)
    return _config_loader_instance
