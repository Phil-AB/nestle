"""Validator registry with auto-registration"""

from typing import Dict, Type, List, Optional
from ..core.base import IValidator
from ..utils.exceptions import (
    ValidatorNotFoundException,
    ValidatorRegistrationException
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class ValidatorRegistry:
    """
    Registry for auto-registration of validators

    Validators self-register using the @ValidatorRegistry.register decorator
    No factory code changes needed when adding new validators
    """

    _validators: Dict[str, Type[IValidator]] = {}

    @classmethod
    def register(cls, validator_name: str):
        """
        Decorator for auto-registering validators

        Usage:
            @ValidatorRegistry.register("exact_match_validator")
            class ExactMatchValidator(IValidator):
                ...

        Args:
            validator_name: Unique name for the validator

        Returns:
            Decorator function

        Raises:
            ValidatorRegistrationException: If validator name already registered
        """
        def decorator(validator_class: Type[IValidator]):
            if validator_name in cls._validators:
                logger.warning(
                    f"Validator '{validator_name}' already registered. Overwriting..."
                )

            # Validate that class implements IValidator interface
            if not issubclass(validator_class, IValidator):
                raise ValidatorRegistrationException(
                    f"Validator '{validator_name}' must implement IValidator interface"
                )

            cls._validators[validator_name] = validator_class
            logger.info(f"Registered validator: {validator_name}")

            return validator_class

        return decorator

    @classmethod
    def get_validator(
        cls,
        validator_name: str,
        config: Optional[Dict] = None
    ) -> IValidator:
        """
        Get validator instance by name

        Args:
            validator_name: Name of registered validator
            config: Configuration for validator

        Returns:
            Validator instance

        Raises:
            ValidatorNotFoundException: If validator not registered
        """
        if validator_name not in cls._validators:
            available = ", ".join(cls._validators.keys())
            raise ValidatorNotFoundException(
                f"Validator '{validator_name}' not found. "
                f"Available validators: {available}"
            )

        validator_class = cls._validators[validator_name]
        return validator_class(config or {})

    @classmethod
    def list_validators(cls) -> List[str]:
        """
        List all registered validators

        Returns:
            List of validator names
        """
        return list(cls._validators.keys())

    @classmethod
    def get_validator_info(cls, validator_name: str) -> Dict:
        """
        Get information about a validator

        Args:
            validator_name: Name of validator

        Returns:
            Dictionary with validator information

        Raises:
            ValidatorNotFoundException: If validator not registered
        """
        if validator_name not in cls._validators:
            raise ValidatorNotFoundException(
                f"Validator '{validator_name}' not found"
            )

        validator_class = cls._validators[validator_name]

        return {
            "name": validator_name,
            "class": validator_class.__name__,
            "module": validator_class.__module__,
            "description": validator_class.__doc__ or "No description available",
        }

    @classmethod
    def get_all_validators_info(cls) -> List[Dict]:
        """
        Get information about all registered validators

        Returns:
            List of validator information dictionaries
        """
        return [
            cls.get_validator_info(name)
            for name in cls._validators.keys()
        ]

    @classmethod
    def unregister(cls, validator_name: str) -> bool:
        """
        Unregister a validator (useful for testing)

        Args:
            validator_name: Name of validator to unregister

        Returns:
            True if unregistered, False if not found
        """
        if validator_name in cls._validators:
            del cls._validators[validator_name]
            logger.info(f"Unregistered validator: {validator_name}")
            return True
        return False

    @classmethod
    def clear(cls):
        """Clear all registered validators (useful for testing)"""
        cls._validators.clear()
        logger.info("Cleared all registered validators")

    @classmethod
    def is_registered(cls, validator_name: str) -> bool:
        """
        Check if validator is registered

        Args:
            validator_name: Name of validator

        Returns:
            True if registered, False otherwise
        """
        return validator_name in cls._validators


# Singleton pattern - validators register on module import
_registry_instance = ValidatorRegistry()


def get_validator_registry() -> ValidatorRegistry:
    """
    Get the singleton validator registry instance

    Returns:
        ValidatorRegistry instance
    """
    return _registry_instance
