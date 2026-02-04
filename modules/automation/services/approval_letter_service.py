"""
Approval Letter Generation Service.

Generates PDF approval letters for automatically approved loans.
Uses reportlab for PDF generation with professional templates.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from io import BytesIO
import logging

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image
)
from reportlab.lib import colors

from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class ApprovalLetterService:
    """
    Service for generating professional approval letters.

    Features:
    - Professional banking letter template
    - Customer and application details
    - Loan terms and conditions
    - PDF output for email attachment
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize approval letter service.

        Args:
            config: Service configuration dict
        """
        self.config = config or {}
        self.company_name = self.config.get("company_name", "Forms Capital Bank")
        self.company_address = self.config.get("company_address", "Accra, Ghana")
        self.company_phone = self.config.get("company_phone", "+233 XX XXX XXXX")
        self.company_email = self.config.get("company_email", "info@formscapital.com")

        logger.info(f"ApprovalLetterService initialized for {self.company_name}")

    def _create_styles(self):
        """Create PDF paragraph styles."""
        styles = getSampleStyleSheet()

        # Custom styles
        styles.add(ParagraphStyle(
            name='CompanyHeader',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#059669'),
            spaceAfter=12,
            alignment=TA_CENTER,
        ))

        styles.add(ParagraphStyle(
            name='LetterDate',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.gray,
            alignment=TA_RIGHT,
        ))

        styles.add(ParagraphStyle(
            name='Greeting',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=12,
        ))

        styles.add(ParagraphStyle(
            name='BodyText',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=12,
            leading=16,
        ))

        styles.add(ParagraphStyle(
            name='ApprovalHeader',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#059669'),
            spaceAfter=12,
        ))

        styles.add(ParagraphStyle(
            name='Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.gray,
            alignment=TA_CENTER,
        ))

        return styles

    async def generate_approval_letter(
        self,
        customer_name: str,
        customer_address: str,
        document_id: str,
        risk_score: int,
        approved_amount: float,
        interest_rate: float,
        term_months: int,
        account_number: str,
        application_date: Optional[str] = None
    ) -> bytes:
        """
        Generate PDF approval letter.

        Args:
            customer_name: Customer full name
            customer_address: Customer address
            document_id: Application/document ID
            risk_score: Risk assessment score
            approved_amount: Approved loan amount
            interest_rate: Annual interest rate
            term_months: Loan term in months
            account_number: Account number
            application_date: Application date (ISO format)

        Returns:
            PDF content as bytes
        """
        try:
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                leftMargin=0.75 * inch,
                rightMargin=0.75 * inch,
                topMargin=0.75 * inch,
                bottomMargin=0.75 * inch
            )

            styles = self._create_styles()
            story = []
            letter_date = application_date or datetime.now().strftime("%B %d, %Y")

            # Company Header
            story.append(Paragraph(self.company_name, styles['CompanyHeader']))
            story.append(Paragraph(self.company_address, styles['Footer']))
            story.append(Spacer(1, 0.2 * inch))

            # Letter Date
            story.append(Paragraph(f"Date: {letter_date}", styles['LetterDate']))
            story.append(Spacer(1, 0.3 * inch))

            # Reference
            story.append(Paragraph(f"Reference: {document_id}", styles['BodyText']))
            story.append(Spacer(1, 0.3 * inch))

            # Customer Address
            story.append(Paragraph(customer_name, styles['BodyText']))
            story.append(Paragraph(customer_address, styles['BodyText']))
            story.append(Spacer(1, 0.4 * inch))

            # Greeting
            story.append(Paragraph(f"Dear {customer_name.split()[0] if customer_name else 'Valued Customer'},", styles['Greeting']))

            # Approval Header
            story.append(Paragraph("LOAN APPROVAL NOTIFICATION", styles['ApprovalHeader']))

            # Body
            body_text = f"""
            We are pleased to inform you that your loan application has been
            <b>APPROVED</b>. Your application was carefully reviewed, and based on
            our assessment, you meet our eligibility criteria for the loan facility.
            """

            story.append(Paragraph(body_text, styles['BodyText']))

            # Loan Details Table
            story.append(Paragraph("Loan Details:", styles['ApprovalHeader']))

            loan_data = [
                ["Application Reference:", document_id],
                ["Account Number:", account_number],
                ["Approved Amount:", f"GHS {approved_amount:,.2f}"],
                ["Interest Rate:", f"{interest_rate}% per annum"],
                ["Loan Term:", f"{term_months} months"],
                ["Risk Assessment Score:", f"{risk_score}/100 (Low Risk)"],
                ["Approval Date:", letter_date],
            ]

            loan_table = Table(loan_data, colWidths=[2.5 * inch, 2.5 * inch])
            loan_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0fdf4')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.gray),
            ]))
            story.append(loan_table)
            story.append(Spacer(1, 0.3 * inch))

            # Terms and Conditions
            story.append(Paragraph("Important Information:", styles['ApprovalHeader']))

            terms = """
            <ul>
            <li>This approval is valid for 30 days from the date of this letter.</li>
            <li>Final loan disbursement is subject to verification of provided documents.</li>
            <li>Interest rate is fixed for the entire loan term.</li>
            <li>Monthly repayments will commence one month after loan disbursement.</li>
            <li>Please contact us if you have any questions or require clarification.</li>
            </ul>
            """
            story.append(Paragraph(terms, styles['BodyText']))
            story.append(Spacer(1, 0.3 * inch))

            # Closing
            closing = """
            We congratulate you on your loan approval and look forward to a
            successful banking relationship with you.
            """
            story.append(Paragraph(closing, styles['BodyText']))
            story.append(Spacer(1, 0.3 * inch))

            # Sign-off
            story.append(Paragraph("Yours sincerely,", styles['BodyText']))
            story.append(Spacer(1, 0.1 * inch))
            story.append(Paragraph("<b>Automated Approval System</b>", styles['BodyText']))
            story.append(Paragraph("Credit Department", styles['BodyText']))
            story.append(Spacer(1, 0.5 * inch))

            # Footer
            footer = f"""
            {self.company_name} | {self.company_address} | {self.company_phone}
            {self.company_email}
            """
            story.append(Paragraph(footer, styles['Footer']))

            # Build PDF
            doc.build(story)

            pdf_content = buffer.getvalue()
            buffer.close()

            logger.info(f"Generated approval letter for {document_id}")
            return pdf_content

        except Exception as e:
            logger.error(f"Failed to generate approval letter: {e}", exc_info=True)
            raise

    async def generate_denial_letter(
        self,
        customer_name: str,
        customer_address: str,
        document_id: str,
        denial_reason: str,
        application_date: Optional[str] = None
    ) -> bytes:
        """
        Generate PDF denial letter.

        Args:
            customer_name: Customer full name
            customer_address: Customer address
            document_id: Application/document ID
            denial_reason: Reason for denial
            application_date: Application date

        Returns:
            PDF content as bytes
        """
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            topMargin=0.75 * inch,
            bottomMargin=0.75 * inch
        )

        styles = self._create_styles()
        story = []
        letter_date = application_date or datetime.now().strftime("%B %d, %Y")

        # Company Header
        story.append(Paragraph(self.company_name, styles['CompanyHeader']))
        story.append(Spacer(1, 0.2 * inch))

        # Letter Date
        story.append(Paragraph(f"Date: {letter_date}", styles['LetterDate']))
        story.append(Spacer(1, 0.3 * inch))

        # Reference
        story.append(Paragraph(f"Reference: {document_id}", styles['BodyText']))
        story.append(Spacer(1, 0.3 * inch))

        # Customer Address
        story.append(Paragraph(customer_name, styles['BodyText']))
        story.append(Paragraph(customer_address, styles['BodyText']))
        story.append(Spacer(1, 0.4 * inch))

        # Greeting
        story.append(Paragraph(f"Dear {customer_name.split()[0] if customer_name else 'Valued Customer'},", styles['Greeting']))

        # Denial Header
        denial_style = ParagraphStyle(
            'DenialHeader',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#dc2626'),
            spaceAfter=12,
        )
        story.append(Paragraph("APPLICATION DECISION", denial_style))

        # Body
        body_text = f"""
        We regret to inform you that your loan application could not be
        approved at this time.
        """

        story.append(Paragraph(body_text, styles['BodyText']))

        # Reason
        story.append(Paragraph("Reason:", styles['ApprovalHeader']))
        story.append(Paragraph(denial_reason, styles['BodyText']))
        story.append(Spacer(1, 0.3 * inch))

        # Next steps
        next_steps = """
        You may reapply after 90 days. For questions about this decision,
        please contact our customer service team.
        """
        story.append(Paragraph(next_steps, styles['BodyText']))
        story.append(Spacer(1, 0.3 * inch))

        # Sign-off
        story.append(Paragraph("Yours sincerely,", styles['BodyText']))
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph("<b>Credit Department</b>", styles['BodyText']))
        story.append(Spacer(1, 0.5 * inch))

        # Build PDF
        doc.build(story)

        pdf_content = buffer.getvalue()
        buffer.close()

        logger.info(f"Generated denial letter for {document_id}")
        return pdf_content


# Singleton instance
_approval_letter_service: Optional[ApprovalLetterService] = None


def get_approval_letter_service() -> ApprovalLetterService:
    """Get singleton approval letter service instance."""
    global _approval_letter_service
    if _approval_letter_service is None:
        _approval_letter_service = ApprovalLetterService()
    return _approval_letter_service
