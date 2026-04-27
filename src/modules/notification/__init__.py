"""Notification module — email alerts for validation events."""

from .email_service import EmailService, get_email_service

__all__ = ["EmailService", "get_email_service"]
