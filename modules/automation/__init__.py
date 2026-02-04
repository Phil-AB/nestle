"""
Automation Module - Agentic AI Workflows.

Provides automated processing workflows using LangGraph agents:
- Automated approval for low-risk loan applications
- Email notifications
- Document generation
"""

from modules.automation.agents.base_automation_agent import (
    BaseAutomationAgent,
    AutomationTask,
    AutomationResult
)
from modules.automation.agents.automated_approval_agent import AutomatedApprovalAgent
from modules.automation.services.email_service import EmailService, get_email_service
from modules.automation.services.approval_letter_service import ApprovalLetterService, get_approval_letter_service

__all__ = [
    "BaseAutomationAgent",
    "AutomationTask",
    "AutomationResult",
    "AutomatedApprovalAgent",
    "EmailService",
    "get_email_service",
    "ApprovalLetterService",
    "get_approval_letter_service",
]
