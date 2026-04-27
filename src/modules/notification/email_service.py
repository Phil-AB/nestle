"""
Email notification service.

Sends validation result alerts to configured recipients.
Supports SendGrid (via HTTP API) with SMTP fallback.
All configuration is driven by environment variables — nothing is hardcoded.
"""

from __future__ import annotations

import asyncio
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import lru_cache
from typing import Any, Dict, List, Optional

import httpx

from shared.utils.logger import get_logger

logger = get_logger(__name__)


class EmailConfig:
    """Email settings loaded from environment / APISettings at call time."""

    def __init__(
        self,
        enabled: bool,
        provider: str,
        sendgrid_api_key: Optional[str],
        smtp_host: Optional[str],
        smtp_port: int,
        smtp_username: Optional[str],
        smtp_password: Optional[str],
        smtp_use_tls: bool,
        sender_email: str,
        sender_name: str,
        recipients: List[str],
        notify_on_failure: bool,
        notify_on_success: bool,
        notify_on_review: bool,
        app_base_url: str,
    ):
        self.enabled = enabled
        self.provider = provider  # "sendgrid" or "smtp"
        self.sendgrid_api_key = sendgrid_api_key
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.smtp_use_tls = smtp_use_tls
        self.sender_email = sender_email
        self.sender_name = sender_name
        self.recipients = recipients
        self.notify_on_failure = notify_on_failure
        self.notify_on_success = notify_on_success
        self.notify_on_review = notify_on_review
        self.app_base_url = app_base_url


class EmailService:
    """
    Sends validation alert emails via SendGrid or SMTP.

    Usage:
        svc = EmailService(config)
        await svc.send_validation_alert(
            shipment_id="...",
            step="vendor_validation",
            final_status="failed",
            discrepancies=[...],
            summary={...},
        )
    """

    def __init__(self, config: EmailConfig):
        self._cfg = config

    # ── Public API ────────────────────────────────────────────────────────────

    async def send_validation_alert(
        self,
        shipment_id: str,
        step: str,
        final_status: str,
        discrepancies: List[Dict[str, Any]],
        summary: Optional[Dict[str, Any]] = None,
        shipment_number: Optional[str] = None,
    ) -> bool:
        """
        Send a validation result alert email.

        Returns True if sent successfully, False otherwise (never raises).
        """
        cfg = self._cfg

        if not cfg.enabled:
            return False

        should_send = (
            (final_status == "failed" and cfg.notify_on_failure)
            or (final_status == "passed" and cfg.notify_on_success)
            or (final_status == "requires_attention" and cfg.notify_on_review)
        )
        if not should_send:
            return False

        if not cfg.recipients:
            logger.warning("No email recipients configured — skipping notification")
            return False

        subject = self._build_subject(step, final_status, shipment_number or shipment_id)
        html_body = self._build_html(step, final_status, shipment_id, shipment_number, discrepancies, summary)
        text_body = self._build_text(step, final_status, shipment_id, shipment_number, discrepancies, summary)

        try:
            if cfg.provider == "sendgrid" and cfg.sendgrid_api_key:
                return await self._send_sendgrid(subject, html_body, text_body)
            else:
                return await asyncio.get_event_loop().run_in_executor(
                    None, self._send_smtp_sync, subject, html_body, text_body
                )
        except Exception as exc:
            logger.error(f"Failed to send validation alert email: {exc}")
            return False

    # ── Sending backends ─────────────────────────────────────────────────────

    async def _send_sendgrid(self, subject: str, html_body: str, text_body: str) -> bool:
        cfg = self._cfg
        payload = {
            "personalizations": [
                {"to": [{"email": r} for r in cfg.recipients]}
            ],
            "from": {"email": cfg.sender_email, "name": cfg.sender_name},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text_body},
                {"type": "text/html", "value": html_body},
            ],
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {cfg.sendgrid_api_key}"},
                json=payload,
            )
        if resp.status_code in (200, 202):
            logger.info(f"Validation alert sent via SendGrid to {cfg.recipients}")
            return True
        logger.error(f"SendGrid returned {resp.status_code}: {resp.text[:200]}")
        return False

    def _send_smtp_sync(self, subject: str, html_body: str, text_body: str) -> bool:
        cfg = self._cfg
        if not cfg.smtp_host:
            logger.warning("SMTP host not configured")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{cfg.sender_name} <{cfg.sender_email}>"
        msg["To"] = ", ".join(cfg.recipients)
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()
        if cfg.smtp_use_tls:
            with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=context) as server:
                if cfg.smtp_username and cfg.smtp_password:
                    server.login(cfg.smtp_username, cfg.smtp_password)
                server.sendmail(cfg.sender_email, cfg.recipients, msg.as_string())
        else:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as server:
                server.ehlo()
                server.starttls(context=context)
                if cfg.smtp_username and cfg.smtp_password:
                    server.login(cfg.smtp_username, cfg.smtp_password)
                server.sendmail(cfg.sender_email, cfg.recipients, msg.as_string())

        logger.info(f"Validation alert sent via SMTP to {cfg.recipients}")
        return True

    # ── Template builders ────────────────────────────────────────────────────

    @staticmethod
    def _step_label(step: str) -> str:
        """Returns the display name for a use-case step, read from config."""
        try:
            from modules.validation_engine.core.config_loader import get_config_loader
            info = get_config_loader().get_use_case_info(step)
            label = info.get("display_name")
            if label:
                return label
        except Exception:
            pass
        return step.replace("_", " ").title()

    @staticmethod
    def _status_label(status: str) -> tuple[str, str]:
        """Returns (label, color_hex)."""
        if status == "passed":
            return "PASSED", "#16a34a"
        if status == "failed":
            return "FAILED", "#dc2626"
        return "REQUIRES ATTENTION", "#d97706"

    def _build_subject(self, step: str, final_status: str, ref: str) -> str:
        label, _ = self._status_label(final_status)
        step_label = self._step_label(step)
        return f"[{label}] {step_label} — {ref}"

    def _build_html(
        self,
        step: str,
        final_status: str,
        shipment_id: str,
        shipment_number: Optional[str],
        discrepancies: List[Dict[str, Any]],
        summary: Optional[Dict[str, Any]],
    ) -> str:
        cfg = self._cfg
        status_label, status_color = self._status_label(final_status)
        step_label = self._step_label(step)
        ref = shipment_number or shipment_id

        url_path = "validation/boe" if step == "boe_validation" else "validation/vendor-docs"
        detail_url = f"{cfg.app_base_url}/{url_path}?shipment_id={shipment_id}"

        critical = [d for d in discrepancies if d.get("severity") == "critical"]
        major = [d for d in discrepancies if d.get("severity") == "major"]

        disc_rows = ""
        for d in (critical + major)[:20]:
            sev = d.get("severity", "info").upper()
            sev_color = "#dc2626" if sev == "CRITICAL" else "#d97706"
            field = d.get("field_name") or d.get("field") or "—"
            msg = d.get("message") or d.get("description") or "—"
            disc_rows += f"""
            <tr>
              <td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;">
                <span style="background:{sev_color};color:#fff;font-size:10px;font-weight:700;
                  padding:2px 6px;border-radius:3px;text-transform:uppercase;">{sev}</span>
              </td>
              <td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;font-family:monospace;
                font-size:12px;color:#374151;">{field}</td>
              <td style="padding:6px 8px;border-bottom:1px solid #e5e7eb;font-size:12px;
                color:#6b7280;">{msg}</td>
            </tr>"""

        if not disc_rows:
            disc_rows = '<tr><td colspan="3" style="padding:12px;text-align:center;color:#9ca3af;">No discrepancies</td></tr>'

        stats_html = ""
        if summary:
            stats_html = f"""
            <div style="display:flex;gap:16px;margin:16px 0;">
              <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;
                padding:12px 20px;text-align:center;">
                <div style="font-size:22px;font-weight:700;color:#111827;">{summary.get("total_checks", 0)}</div>
                <div style="font-size:11px;color:#6b7280;">Total Checks</div>
              </div>
              <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px;
                padding:12px 20px;text-align:center;">
                <div style="font-size:22px;font-weight:700;color:#16a34a;">{summary.get("passed_checks", 0)}</div>
                <div style="font-size:11px;color:#6b7280;">Passed</div>
              </div>
              <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:6px;
                padding:12px 20px;text-align:center;">
                <div style="font-size:22px;font-weight:700;color:#dc2626;">{summary.get("failed_checks", 0)}</div>
                <div style="font-size:11px;color:#6b7280;">Failed</div>
              </div>
            </div>"""

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:24px;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="max-width:680px;margin:0 auto;background:#fff;border-radius:8px;
    border:1px solid #e5e7eb;overflow:hidden;">

    <!-- Header -->
    <div style="background:#1e3a5f;padding:24px 32px;">
      <div style="color:#fff;font-size:13px;font-weight:600;letter-spacing:0.05em;
        text-transform:uppercase;opacity:0.7;">Nestle Ghana · Customs Validation</div>
      <div style="color:#fff;font-size:22px;font-weight:700;margin-top:4px;">{step_label}</div>
    </div>

    <!-- Status banner -->
    <div style="background:{status_color};padding:14px 32px;">
      <span style="color:#fff;font-size:16px;font-weight:700;letter-spacing:0.05em;">
        {status_label}
      </span>
      <span style="color:rgba(255,255,255,0.85);font-size:13px;margin-left:12px;">
        Shipment: {ref}
      </span>
    </div>

    <!-- Body -->
    <div style="padding:24px 32px;">
      {stats_html}

      <h3 style="margin:20px 0 12px;font-size:14px;font-weight:600;color:#111827;">
        Discrepancies ({len(discrepancies)} total)
      </h3>
      <table style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;
        border-radius:6px;overflow:hidden;font-size:13px;">
        <thead>
          <tr style="background:#f9fafb;">
            <th style="text-align:left;padding:8px;font-size:11px;font-weight:600;
              text-transform:uppercase;color:#6b7280;border-bottom:1px solid #e5e7eb;">Severity</th>
            <th style="text-align:left;padding:8px;font-size:11px;font-weight:600;
              text-transform:uppercase;color:#6b7280;border-bottom:1px solid #e5e7eb;">Field</th>
            <th style="text-align:left;padding:8px;font-size:11px;font-weight:600;
              text-transform:uppercase;color:#6b7280;border-bottom:1px solid #e5e7eb;">Issue</th>
          </tr>
        </thead>
        <tbody>{disc_rows}</tbody>
      </table>

      <div style="margin-top:24px;">
        <a href="{detail_url}"
          style="display:inline-block;background:#1e3a5f;color:#fff;text-decoration:none;
          padding:10px 20px;border-radius:6px;font-size:13px;font-weight:600;">
          Review in Dashboard →
        </a>
      </div>
    </div>

    <!-- Footer -->
    <div style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:16px 32px;
      font-size:11px;color:#9ca3af;">
      This alert was sent by the Nestle Ghana Customs Validation System.
      Shipment ID: {shipment_id}
    </div>
  </div>
</body>
</html>"""

    def _build_text(
        self,
        step: str,
        final_status: str,
        shipment_id: str,
        shipment_number: Optional[str],
        discrepancies: List[Dict[str, Any]],
        summary: Optional[Dict[str, Any]],
    ) -> str:
        status_label, _ = self._status_label(final_status)
        step_label = self._step_label(step)
        ref = shipment_number or shipment_id

        lines = [
            f"Nestle Ghana — Customs Validation Alert",
            f"{'=' * 50}",
            f"Step:     {step_label}",
            f"Status:   {status_label}",
            f"Shipment: {ref}",
            "",
        ]
        if summary:
            lines += [
                f"Checks:   {summary.get('total_checks', 0)} total, "
                f"{summary.get('passed_checks', 0)} passed, "
                f"{summary.get('failed_checks', 0)} failed",
                "",
            ]
        if discrepancies:
            lines.append(f"Discrepancies ({len(discrepancies)}):")
            for d in discrepancies[:20]:
                sev = (d.get("severity") or "").upper()
                field = d.get("field_name") or d.get("field") or "unknown"
                msg = d.get("message") or d.get("description") or ""
                lines.append(f"  [{sev}] {field}: {msg}")

        url_path = "validation/boe" if step == "boe_validation" else "validation/vendor-docs"
        detail_url = f"{self._cfg.app_base_url}/{url_path}?shipment_id={shipment_id}"
        lines += ["", f"Review: {detail_url}"]
        return "\n".join(lines)


# ── Singleton factory ─────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_email_service() -> EmailService:
    """Return cached EmailService built from APISettings."""
    from src.api.config import get_api_settings

    s = get_api_settings()
    cfg = EmailConfig(
        enabled=getattr(s, "EMAIL_ENABLED", False),
        provider=getattr(s, "EMAIL_PROVIDER", "smtp"),
        sendgrid_api_key=getattr(s, "SENDGRID_API_KEY", None),
        smtp_host=getattr(s, "SMTP_HOST", None),
        smtp_port=getattr(s, "SMTP_PORT", 587),
        smtp_username=getattr(s, "SMTP_USERNAME", None),
        smtp_password=getattr(s, "SMTP_PASSWORD", None),
        smtp_use_tls=getattr(s, "SMTP_USE_TLS", False),
        sender_email=getattr(s, "EMAIL_SENDER", "noreply@nestle.com"),
        sender_name=getattr(s, "EMAIL_SENDER_NAME", "Nestle Validation System"),
        recipients=getattr(s, "EMAIL_RECIPIENTS", []),
        notify_on_failure=getattr(s, "EMAIL_NOTIFY_ON_FAILURE", True),
        notify_on_success=getattr(s, "EMAIL_NOTIFY_ON_SUCCESS", False),
        notify_on_review=getattr(s, "EMAIL_NOTIFY_ON_REVIEW", True),
        app_base_url=getattr(s, "APP_BASE_URL", "http://localhost:3000"),
    )
    return EmailService(cfg)
