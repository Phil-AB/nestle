"""PDF report generator"""

from typing import Dict, Any
from datetime import datetime

from .base_generator import BaseReportGenerator
from ...core.base import ValidationContext
from ..report_models import ReportFormat
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class PDFReportGenerator(BaseReportGenerator):
    """
    Generates validation reports in PDF format

    Features:
    - Professional PDF layout
    - Tables for discrepancies and results
    - Charts and visualizations
    - Headers and footers
    - Page numbers

    Note: This is a simplified implementation. In production, use:
    - reportlab for advanced PDF generation
    - weasyprint for HTML-to-PDF conversion
    - pdfkit with wkhtmltopdf
    """

    def __init__(self):
        """Initialize PDF report generator"""
        super().__init__()
        self.supported_formats = [ReportFormat.PDF]

    async def _generate_pdf(
        self, data: Dict[str, Any], context: ValidationContext
    ) -> bytes:
        """
        Generate PDF report

        Args:
            data: Report data
            context: Validation context

        Returns:
            PDF bytes

        Note: This is a placeholder. In production, implement using reportlab or weasyprint.
        """
        # Generate HTML first
        html_content = await self._generate_html_for_pdf(data, context)

        # Convert HTML to PDF (placeholder - would use weasyprint/reportlab in production)
        pdf_bytes = self._html_to_pdf_placeholder(html_content)

        logger.info(f"Generated PDF report for session {data['session_id']}")

        return pdf_bytes

    async def _generate_html_for_pdf(
        self, data: Dict[str, Any], context: ValidationContext
    ) -> str:
        """
        Generate HTML content suitable for PDF conversion

        Args:
            data: Report data
            context: Validation context

        Returns:
            HTML string
        """
        # Status colors
        status_colors = {
            "passed": "#28a745",
            "warning": "#ffc107",
            "partial": "#fd7e14",
            "failed": "#dc3545"
        }
        status_color = status_colors.get(data["final_status"], "#6c757d")

        # Severity colors
        severity_colors = {
            "critical": "#dc3545",
            "major": "#fd7e14",
            "minor": "#ffc107",
            "info": "#17a2b8"
        }

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Validation Report - {data['session_id']}</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm;
        }}
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.6;
            color: #333;
        }}
        .header {{
            text-align: center;
            padding-bottom: 20px;
            border-bottom: 3px solid {status_color};
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: {status_color};
            margin-bottom: 5px;
        }}
        .header .session-id {{
            color: #666;
            font-size: 10pt;
        }}
        .summary-box {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }}
        .summary-item {{
            padding: 10px;
            background: white;
            border-radius: 4px;
        }}
        .summary-item .label {{
            font-weight: bold;
            color: #666;
            font-size: 9pt;
            text-transform: uppercase;
        }}
        .summary-item .value {{
            font-size: 18pt;
            font-weight: bold;
            color: #333;
        }}
        .status-badge {{
            display: inline-block;
            padding: 8px 16px;
            background: {status_color};
            color: white;
            border-radius: 20px;
            font-weight: bold;
            font-size: 12pt;
            text-transform: uppercase;
        }}
        .section {{
            margin-bottom: 30px;
            page-break-inside: avoid;
        }}
        .section h2 {{
            color: #333;
            border-bottom: 2px solid #ddd;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #f8f9fa;
            font-weight: bold;
            color: #333;
        }}
        tr:hover {{
            background: #f8f9fa;
        }}
        .severity-badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 9pt;
            font-weight: bold;
            color: white;
        }}
        .severity-critical {{ background: {severity_colors['critical']}; }}
        .severity-major {{ background: {severity_colors['major']}; }}
        .severity-minor {{ background: {severity_colors['minor']}; }}
        .severity-info {{ background: {severity_colors['info']}; }}
        .footer {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            text-align: center;
            font-size: 9pt;
            color: #666;
            padding: 10px;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Validation Report</h1>
        <div class="session-id">Session ID: {data['session_id']}</div>
        <div class="session-id">Use Case: {data['use_case']} | Version: {data['version']}</div>
        <div class="session-id">Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
    </div>

    <div class="summary-box">
        <div style="text-align: center; margin-bottom: 20px;">
            <span class="status-badge">{data['final_status']}</span>
        </div>
        <div class="summary-grid">
            <div class="summary-item">
                <div class="label">Accuracy</div>
                <div class="value" style="color: {status_color};">{data['accuracy_score']}%</div>
            </div>
            <div class="summary-item">
                <div class="label">Total Discrepancies</div>
                <div class="value">{data['total_discrepancies']}</div>
            </div>
            <div class="summary-item">
                <div class="label">Validations Passed</div>
                <div class="value" style="color: #28a745;">{data['passed_validations']}</div>
            </div>
            <div class="summary-item">
                <div class="label">Validations Failed</div>
                <div class="value" style="color: #dc3545;">{data['failed_validations']}</div>
            </div>
        </div>
    </div>

    <div class="section">
        <h2>Discrepancy Breakdown</h2>
        <table>
            <tr>
                <th>Severity</th>
                <th>Count</th>
                <th>Percentage</th>
            </tr>
            <tr>
                <td><span class="severity-badge severity-critical">Critical</span></td>
                <td>{data['critical_count']}</td>
                <td>{round((data['critical_count'] / max(data['total_discrepancies'], 1)) * 100, 1)}%</td>
            </tr>
            <tr>
                <td><span class="severity-badge severity-major">Major</span></td>
                <td>{data['major_count']}</td>
                <td>{round((data['major_count'] / max(data['total_discrepancies'], 1)) * 100, 1)}%</td>
            </tr>
            <tr>
                <td><span class="severity-badge severity-minor">Minor</span></td>
                <td>{data['minor_count']}</td>
                <td>{round((data['minor_count'] / max(data['total_discrepancies'], 1)) * 100, 1)}%</td>
            </tr>
            <tr>
                <td><span class="severity-badge severity-info">Info</span></td>
                <td>{data['info_count']}</td>
                <td>{round((data['info_count'] / max(data['total_discrepancies'], 1)) * 100, 1)}%</td>
            </tr>
        </table>
    </div>

    <div class="section">
        <h2>Top Discrepancies</h2>
        <table>
            <tr>
                <th>Field</th>
                <th>Severity</th>
                <th>Source Value</th>
                <th>Target Value</th>
                <th>Likely Cause</th>
            </tr>
"""

        # Add top discrepancies (limit to 10)
        for disc in data['top_discrepancies'][:10]:
            severity = disc.get('severity', '').lower()
            html += f"""
            <tr>
                <td>{disc.get('field_name', '')}</td>
                <td><span class="severity-badge severity-{severity}">{disc.get('severity', '')}</span></td>
                <td>{str(disc.get('source_value', ''))[:50]}</td>
                <td>{str(disc.get('target_value', ''))[:50]}</td>
                <td>{disc.get('likely_cause', '')}</td>
            </tr>
"""

        html += """
        </table>
    </div>

    <div class="section">
        <h2>Validation Results by Category</h2>
        <table>
            <tr>
                <th>Validator</th>
                <th>Total</th>
                <th>Passed</th>
                <th>Failed</th>
                <th>Pass Rate</th>
            </tr>
"""

        for validator, stats in data['results_by_category'].items():
            pass_rate = round((stats['passed'] / max(stats['total'], 1)) * 100, 1)
            html += f"""
            <tr>
                <td>{validator}</td>
                <td>{stats['total']}</td>
                <td style="color: #28a745;">{stats['passed']}</td>
                <td style="color: #dc3545;">{stats['failed']}</td>
                <td>{pass_rate}%</td>
            </tr>
"""

        html += f"""
        </table>
    </div>

    <div class="footer">
        <p>Validation Engine v1.0 | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        <p>Session: {data['session_id']} | Use Case: {data['use_case']}</p>
    </div>
</body>
</html>
"""

        return html

    def _html_to_pdf_placeholder(self, html: str) -> bytes:
        """
        Placeholder for HTML to PDF conversion

        In production, use:
        - weasyprint: HTML5String(html).write_pdf()
        - reportlab: Build PDF programmatically
        - pdfkit: pdfkit.from_string(html, False)

        Args:
            html: HTML string

        Returns:
            PDF bytes (placeholder returns HTML bytes for now)
        """
        # Placeholder: In production, implement actual PDF generation
        # For now, return HTML bytes with a note
        note = "<!-- PDF GENERATION PLACEHOLDER: Install weasyprint or reportlab for actual PDF generation -->\n"
        return (note + html).encode('utf-8')


# Singleton instance
_pdf_generator_instance = None


def get_pdf_generator() -> PDFReportGenerator:
    """
    Get singleton PDF report generator

    Returns:
        PDFReportGenerator instance
    """
    global _pdf_generator_instance
    if _pdf_generator_instance is None:
        _pdf_generator_instance = PDFReportGenerator()
    return _pdf_generator_instance
