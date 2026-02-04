"""
Validator registry system.

Provides decorator-based registration for validators and retrieval functions.
This allows for pluggable validators without modifying core code.
"""

from typing import Dict, Type, Optional
from modules.extraction.validation.core.base import BaseValidator
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)

# Global registry of all validators
VALIDATOR_REGISTRY: Dict[str, Type[BaseValidator]] = {}


def register_validator(name: str):
    """
    Decorator to register a validator in the global registry.
    
    Usage:
        @register_validator("required")
        class RequiredValidator(BaseValidator):
            async def validate(self, data, context=None):
                ...
    
    Args:
        name: Unique name for the validator (used in configuration)
    
    Returns:
        Decorator function
    """
    def decorator(cls: Type[BaseValidator]):
        if name in VALIDATOR_REGISTRY:
            logger.warning(
                f"Validator '{name}' is already registered. "
                f"Overwriting with {cls.__name__}"
            )
        
        VALIDATOR_REGISTRY[name] = cls
        logger.debug(f"Registered validator: {name} -> {cls.__name__}")
        return cls
    
    return decorator


def get_validator(name: str) -> Optional[Type[BaseValidator]]:
    """
    Get validator class by name from registry.
    
    Args:
        name: Validator name
    
    Returns:
        Validator class or None if not found
    """
    return VALIDATOR_REGISTRY.get(name)


def list_validators() -> Dict[str, str]:
    """
    List all registered validators.
    
    Returns:
        Dictionary mapping validator names to class names
    """
    return {
        name: cls.__name__
        for name, cls in VALIDATOR_REGISTRY.items()
    }


def is_registered(name: str) -> bool:
    """
    Check if a validator is registered.
    
    Args:
        name: Validator name
    
    Returns:
        True if registered, False otherwise
    """
    return name in VALIDATOR_REGISTRY
