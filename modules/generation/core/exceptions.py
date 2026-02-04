"""
Custom exceptions for generation module.
"""


class GenerationException(Exception):
    """Base exception for generation module."""
    pass


class RendererException(GenerationException):
    """Exception raised by renderers."""
    pass


class DataProviderException(GenerationException):
    """Exception raised by data providers."""
    pass


class MappingException(GenerationException):
    """Exception raised by mappers."""
    pass


class TemplateNotFoundException(GenerationException):
    """Exception raised when template not found."""
    pass


class TemplateValidationException(GenerationException):
    """Exception raised when template validation fails."""
    pass


class ConfigurationException(GenerationException):
    """Exception raised for configuration errors."""
    pass


class JobNotFoundException(GenerationException):
    """Exception raised when generation job not found."""
    pass
