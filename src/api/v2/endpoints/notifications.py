"""Notification management endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr
from typing import List, Optional

from shared.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/notifications", tags=["notifications"])


class TestEmailRequest(BaseModel):
    recipients: Optional[List[str]] = None
    shipment_id: str = "TEST-001"
    step: str = "vendor_validation"
    final_status: str = "failed"


class EmailStatusResponse(BaseModel):
    enabled: bool
    provider: str
    sender: str
    recipients: List[str]
    notify_on_failure: bool
    notify_on_success: bool
    notify_on_review: bool


@router.get("/email/status", response_model=EmailStatusResponse)
async def get_email_status():
    """Return current email notification configuration (no secrets)."""
    from modules.notification import get_email_service
    svc = get_email_service()
    cfg = svc._cfg
    return EmailStatusResponse(
        enabled=cfg.enabled,
        provider=cfg.provider,
        sender=f"{cfg.sender_name} <{cfg.sender_email}>",
        recipients=cfg.recipients,
        notify_on_failure=cfg.notify_on_failure,
        notify_on_success=cfg.notify_on_success,
        notify_on_review=cfg.notify_on_review,
    )


@router.post("/email/test")
async def send_test_email(request: TestEmailRequest):
    """
    Send a test validation alert email.

    Useful for verifying SMTP/SendGrid configuration without running a real validation.
    """
    from modules.notification import get_email_service
    svc = get_email_service()

    sample_discrepancies = [
        {
            "field_name": "hs_code",
            "severity": "critical",
            "message": "HS code mismatch — BOE declares 1901.90, invoice shows 1901.20",
            "source_value": "1901.90",
            "target_value": "1901.20",
        },
        {
            "field_name": "gross_weight",
            "severity": "major",
            "message": "Gross weight differs by 2.3%: BOE 45,000 kg vs packing list 44,000 kg",
            "source_value": "45000",
            "target_value": "44000",
        },
    ]
    sample_summary = {
        "total_checks": 21,
        "passed_checks": 18,
        "failed_checks": 3,
        "total_discrepancies": 2,
    }

    sent = await svc.send_validation_alert(
        shipment_id=request.shipment_id,
        step=request.step,
        final_status=request.final_status,
        discrepancies=sample_discrepancies,
        summary=sample_summary,
    )

    return {
        "sent": sent,
        "message": "Email sent successfully" if sent else (
            "Email not sent — check EMAIL_ENABLED and configuration"
        ),
    }
