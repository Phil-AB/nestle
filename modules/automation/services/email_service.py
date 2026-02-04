"""
Email Notification Service.

Handles sending emails for automated approvals and customer notifications.
Configurable SMTP settings with template support.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import smtplib
import logging
from pathlib import Path

from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class EmailConfig:
    """Email service configuration."""
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    from_email: str
    from_name: str
    use_tls: bool = True


@dataclass
class EmailAttachment:
    """Email attachment."""
    filename: str
    content: bytes
    content_type: str = "application/pdf"


@dataclass
class EmailTemplate:
    """Email template with subject and body."""
    subject: str
    body_html: str
    body_text: str


class EmailService:
    """
    Service for sending emails with SMTP.

    Supports:
    - Plain text and HTML emails
    - Attachments (PDF approval letters)
    - Template-based emails
    - Batch sending
    """

    def __init__(self, config: Optional[EmailConfig] = None):
        """
        Initialize email service.

        Args:
            config: Email configuration. If None, uses environment variables.
        """
        if config is None:
            config = self._load_config_from_env()

        self.config = config
        self._templates: Dict[str, EmailTemplate] = {}

        # Load default templates
        self._load_default_templates()

        logger.info(f"EmailService initialized: {self.config.from_email}")

    def _load_config_from_env(self) -> EmailConfig:
        """Load email configuration from environment variables."""
        import os

        return EmailConfig(
            smtp_host=os.getenv("SMTP_HOST", "localhost"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            from_email=os.getenv("FROM_EMAIL", "noreply@formscapital.com"),
            from_name=os.getenv("FROM_NAME", "Forms Capital"),
            use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        )

    def _load_default_templates(self):
        """Load default email templates."""
        # Loan Approval Template
        self.register_template(
            "loan_approval",
            EmailTemplate(
                subject="Your Loan Application Has Been Approved! 🎉",
                body_html="""<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #10b981; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }
        .content { background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }
        .approval-box { background: #ecfdf5; border-left: 4px solid #10b981; padding: 20px; margin: 20px 0; }
        .details { margin: 20px 0; }
        .details table { width: 100%; border-collapse: collapse; }
        .details td { padding: 10px; border-bottom: 1px solid #e5e7eb; }
        .cta { background: #10b981; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block; margin: 20px 0; }
        .footer { text-align: center; margin-top: 30px; color: #6b7280; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Congratulations, {{customer_name}}!</h1>
        </div>
        <div class="content">
            <p>We're pleased to inform you that your loan application has been <strong>APPROVED</strong>.</p>

            <div class="approval-box">
                <h3>🎉 Application Approved</h3>
                <p>Your application has been reviewed and automatically approved based on our eligibility criteria.</p>
            </div>

            <div class="details">
                <h3>Application Details:</h3>
                <table>
                    <tr><td><strong>Application ID:</strong></td><td>{{document_id}}</td></tr>
                    <tr><td><strong>Risk Score:</strong></td><td>{{risk_score}}/100 (Low Risk)</td></tr>
                    <tr><td><strong>Approved Amount:</strong></td><td>GHS {{approved_amount}}</td></tr>
                    <tr><td><strong>Interest Rate:</strong></td><td>{{interest_rate}}%</td></tr>
                    <tr><td><strong>Account Number:</strong></td><td>{{account_number}}</td></tr>
                </table>
            </div>

            <p>Your approval letter is attached to this email. Please review it carefully and let us know if you have any questions.</p>

            <p>If you have any questions or need assistance, please don't hesitate to contact us.</p>

            <div class="footer">
                <p>This is an automated message. Please do not reply to this email.</p>
                <p>&copy; 2026 Forms Capital. All rights reserved.</p>
            </div>
        </div>
    </div>
</body>
</html>""",
                body_text="""Congratulations, {customer_name}!

We're pleased to inform you that your loan application has been APPROVED.

Application Details:
- Application ID: {document_id}
- Risk Score: {risk_score}/100 (Low Risk)
- Approved Amount: GHS {approved_amount}
- Interest Rate: {interest_rate}%
- Account Number: {account_number}

Your approval letter is attached to this email. Please review it carefully.

If you have any questions, please don't hesitate to contact us.

© 2026 Forms Capital. All rights reserved.
"""
            )
        )

        # Manual Review Required Template
        self.register_template(
            "manual_review",
            EmailTemplate(
                subject="Your Loan Application is Under Review",
                body_html="""<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #f59e0b; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }
        .content { background: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }
        .info-box { background: #fffbeb; border-left: 4px solid #f59e0b; padding: 20px; margin: 20px 0; }
        .footer { text-align: center; margin-top: 30px; color: #6b7280; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Application Under Review</h1>
        </div>
        <div class="content">
            <p>Dear {{customer_name}},</p>
            <p>Thank you for your loan application. We're currently reviewing your application and will get back to you shortly.</p>

            <div class="info-box">
                <h3>📋 What Happens Next?</h3>
                <p>Our team will carefully review your application and contact you within 1-2 business days with a decision.</p>
            </div>

            <p>If you have any questions in the meantime, please don't hesitate to reach out.</p>

            <div class="footer">
                <p>&copy; 2026 Forms Capital. All rights reserved.</p>
            </div>
        </div>
    </div>
</body>
</html>""",
                body_text="""Dear {customer_name},

Thank you for your loan application. We're currently reviewing your application and will get back to you shortly.

What Happens Next?
Our team will carefully review your application and contact you within 1-2 business days with a decision.

If you have any questions in the meantime, please don't hesitate to reach out.

© 2026 Forms Capital. All rights reserved.
"""
            )
        )

    def register_template(self, name: str, template: EmailTemplate):
        """Register a custom email template."""
        self._templates[name] = template
        logger.info(f"Registered email template: {name}")

    def _render_template(self, template_name: str, variables: Dict[str, Any]) -> EmailTemplate:
        """Render template with variables."""
        template = self._templates.get(template_name)
        if not template:
            raise ValueError(f"Template not found: {template_name}")

        subject = template.subject
        body_html = template.body_html
        body_text = template.body_text

        # Replace variables
        for key, value in variables.items():
            placeholder_html = f"{{{{{key}}}}}"
            placeholder_text = f"{{{key}}}"
            subject = subject.replace(placeholder_html, str(value))
            body_html = body_html.replace(placeholder_html, str(value))
            body_text = body_text.replace(placeholder_text, str(value))

        return EmailTemplate(subject=subject, body_html=body_html, body_text=body_text)

    async def send_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        body_html: str,
        body_text: str,
        attachments: Optional[List[EmailAttachment]] = None
    ) -> Dict[str, Any]:
        """
        Send an email via SMTP.

        Args:
            to_email: Recipient email address
            to_name: Recipient name
            subject: Email subject
            body_html: HTML body
            body_text: Plain text body
            attachments: Optional list of attachments

        Returns:
            Dict with success status and message
        """
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.config.from_name} <{self.config.from_email}>"
            msg["To"] = f"{to_name} <{to_email}>"

            # Add text and HTML parts
            msg.attach(MIMEText(body_text, "plain"))
            msg.attach(MIMEText(body_html, "html"))

            # Add attachments
            if attachments:
                for attachment in attachments:
                    part = MIMEApplication(attachment.content)
                    part.add_header(
                        "Content-Disposition",
                        "attachment",
                        filename=attachment.filename
                    )
                    msg.attach(part)

            # Send email
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.use_tls:
                    server.starttls()
                if self.config.smtp_user:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email}")
            return {
                "success": True,
                "message": "Email sent successfully",
                "to": to_email
            }

        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"Failed to send email: {str(e)}",
                "to": to_email
            }

    async def send_template_email(
        self,
        template_name: str,
        to_email: str,
        to_name: str,
        variables: Dict[str, Any],
        attachments: Optional[List[EmailAttachment]] = None
    ) -> Dict[str, Any]:
        """
        Send an email using a registered template.

        Args:
            template_name: Name of registered template
            to_email: Recipient email
            to_name: Recipient name
            variables: Variables for template rendering
            attachments: Optional attachments

        Returns:
            Dict with success status
        """
        template = self._render_template(template_name, variables)

        return await self.send_email(
            to_email=to_email,
            to_name=to_name,
            subject=template.subject,
            body_html=template.body_html,
            body_text=template.body_text,
            attachments=attachments
        )

    async def send_approval_email(
        self,
        customer_name: str,
        customer_email: str,
        document_id: str,
        risk_score: int,
        approved_amount: float,
        interest_rate: float,
        account_number: str,
        approval_letter_pdf: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Send loan approval email with optional attachment.

        Args:
            customer_name: Customer name
            customer_email: Customer email
            document_id: Document/application ID
            risk_score: Risk assessment score
            approved_amount: Approved loan amount
            interest_rate: Interest rate
            account_number: Account number
            approval_letter_pdf: Optional PDF attachment

        Returns:
            Dict with success status
        """
        attachments = []
        if approval_letter_pdf:
            attachments.append(EmailAttachment(
                filename=f"approval_letter_{document_id}.pdf",
                content=approval_letter_pdf,
                content_type="application/pdf"
            ))

        variables = {
            "customer_name": customer_name,
            "document_id": document_id,
            "risk_score": risk_score,
            "approved_amount": f"{approved_amount:,.2f}",
            "interest_rate": interest_rate,
            "account_number": account_number
        }

        return await self.send_template_email(
            template_name="loan_approval",
            to_email=customer_email,
            to_name=customer_name,
            variables=variables,
            attachments=attachments
        )

    async def send_review_required_email(
        self,
        customer_name: str,
        customer_email: str,
        document_id: str
    ) -> Dict[str, Any]:
        """
        Send manual review required notification.

        Args:
            customer_name: Customer name
            customer_email: Customer email
            document_id: Document/application ID

        Returns:
            Dict with success status
        """
        variables = {
            "customer_name": customer_name,
            "document_id": document_id
        }

        return await self.send_template_email(
            template_name="manual_review",
            to_email=customer_email,
            to_name=customer_name,
            variables=variables
        )


# Singleton instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get singleton email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
