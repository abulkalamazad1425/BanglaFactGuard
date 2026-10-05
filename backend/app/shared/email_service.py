from __future__ import annotations

import asyncio
import smtplib
from email.mime.text import MIMEText

import structlog

from app.core.config import get_settings
from app.core.exceptions import EmailDeliveryError

logger = structlog.get_logger(__name__)


class EmailService:
    """
    Thin SMTP wrapper for transactional email (currently: password-reset OTPs).

    When `EMAIL_SMTP_HOST` is unset, no real email is sent — the OTP is
    logged instead so the flow stays testable in local/dev environments
    without SMTP credentials.
    """

    def __init__(self) -> None:
        self._settings = get_settings().email

    async def send_otp_email(
        self, *, to_email: str, otp: str, purpose: str = "password_reset"
    ) -> None:
        subject = "Your BanglaFactGuard verification code"
        body = (
            f"Your one-time password (OTP) is: {otp}\n\n"
            f"This code expires in {self._settings.otp_ttl_minutes} minutes. "
            "If you did not request this, you can safely ignore this email."
        )

        if not self._settings.is_configured:
            logger.info(
                "otp_email_dev_fallback",
                purpose=purpose,
                to=to_email,
                otp=otp,
                hint="EMAIL_SMTP_HOST is not configured — logging OTP instead of sending email.",
            )
            return

        try:
            await asyncio.to_thread(self._send_sync, to_email, subject, body)
        except Exception as exc:
            # Never let an SMTP-layer failure (bad credentials, network
            # timeout, provider outage) bubble up as an unhandled 500 —
            # surface it as a clean, typed domain error instead. Log the OTP
            # here too so it's still recoverable from the console even
            # though delivery failed.
            logger.error(
                "otp_email_send_failed", to=to_email, otp=otp, error=str(exc)
            )
            raise EmailDeliveryError() from exc

    async def send_result_email(self, *, to_email: str, submission_id: str, headline: str, verdict: str) -> None:
        if not self._settings.is_configured:
            raise EmailDeliveryError()
        link = f"{self._settings.website_url.rstrip('/')}/verify/{submission_id}"
        body = f"Expert review is complete.\n\nFinal verdict: {verdict}\nClaim: {headline}\n\nView the evidence: {link}\n\nBanglaFactGuard"
        await asyncio.to_thread(self._send_sync, to_email, "Your BanglaFactGuard final result is ready", body)

    def _send_sync(self, to_email: str, subject: str, body: str) -> None:
        settings = self._settings
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = f"{settings.from_name} <{settings.from_address}>"
        msg["To"] = to_email

        # Gmail (and other providers) display app passwords grouped with
        # spaces for readability — strip stray whitespace defensively so a
        # copy-pasted credential doesn't silently fail SMTP AUTH.
        smtp_user = settings.smtp_user.strip()
        smtp_password = settings.smtp_password.replace(" ", "").strip()

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            if settings.use_tls:
                server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.sendmail(settings.from_address, [to_email], msg.as_string())
        logger.info("transactional_email_sent")
