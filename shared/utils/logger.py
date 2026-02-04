"""
Structured logging configuration for the application.
"""

import logging
import sys
from typing import Any
from pathlib import Path

from .config import settings


def setup_logger(name: str) -> logging.Logger:
    """
    Setup a logger with consistent formatting.

    Args:
        name: Logger name (usually __name__ of the module)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(settings.LOG_LEVEL)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(settings.LOG_LEVEL)

        # Formatter
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

        # Create logs directory if in production
        if not settings.DEBUG:
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)

            # File handler
            file_handler = logging.FileHandler(log_dir / "app.log")
            file_handler.setLevel(settings.LOG_LEVEL)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    return logger


def log_function_call(logger: logging.Logger, func_name: str, **kwargs: Any) -> None:
    """
    Log a function call with its arguments.

    Args:
        logger: Logger instance
        func_name: Function name
        **kwargs: Function arguments to log
    """
    args_str = ", ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.debug(f"Calling {func_name}({args_str})")


def log_error(logger: logging.Logger, error: Exception, context: str = "") -> None:
    """
    Log an error with context.

    Args:
        logger: Logger instance
        error: Exception that occurred
        context: Additional context about where the error occurred
    """
    if context:
        logger.error(f"{context}: {type(error).__name__}: {str(error)}")
    else:
        logger.error(f"{type(error).__name__}: {str(error)}")

    if settings.DEBUG:
        logger.exception("Full traceback:")
