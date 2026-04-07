"""Custom exceptions for validation engine"""


class ValidationEngineException(Exception):
    """Base exception for validation engine"""
    pass


class ValidatorNotFoundException(ValidationEngineException):
    """Raised when a validator is not found in registry"""
    pass


class ValidatorRegistrationException(ValidationEngineException):
    """Raised when validator registration fails"""
    pass


class ValidationConfigException(ValidationEngineException):
    """Raised when validation configuration is invalid"""
    pass


class UseCaseNotFoundException(ValidationEngineException):
    """Raised when a use case is not found"""
    pass


class SessionNotFoundException(ValidationEngineException):
    """Raised when a validation session is not found"""
    pass


class ValidationWorkflowException(ValidationEngineException):
    """Raised when validation workflow encounters an error"""
    pass


class NormalizationException(ValidationEngineException):
    """Raised when normalization fails"""
    pass


class DiscrepancyClassificationException(ValidationEngineException):
    """Raised when discrepancy classification fails"""
    pass


class VersionControlException(ValidationEngineException):
    """Raised when version control operations fail"""
    pass


class AutoFixException(ValidationEngineException):
    """Raised when auto-fix fails"""
    pass
