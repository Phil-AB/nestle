"""Automation Services."""

from modules.automation.services.email_service import EmailService, get_email_service
from modules.automation.services.approval_letter_service import ApprovalLetterService, get_approval_letter_service

__all__ = [
    "EmailService",
    "get_email_service",
    "ApprovalLetterService",
    "get_approval_letter_service",
]
