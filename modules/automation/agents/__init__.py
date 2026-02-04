"""Automation Agents."""

from modules.automation.agents.base_automation_agent import BaseAutomationAgent, AutomationTask, AutomationResult
from modules.automation.agents.automated_approval_agent import AutomatedApprovalAgent

__all__ = [
    "BaseAutomationAgent",
    "AutomationTask",
    "AutomationResult",
    "AutomatedApprovalAgent",
]
