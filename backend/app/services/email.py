"""Minimal SMTP email sender.

Best-effort: returns ``True`` when an email is sent, ``False`` when SMTP is not
configured or the send fails — it NEVER raises, so callers (e.g. the support
form) can persist their record regardless of email delivery. Run it via
``fastapi.concurrency.run_in_threadpool`` from async endpoints so the blocking
SMTP call doesn't stall the event loop.
"""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger("extracare.email")


def email_configured() -> bool:
    settings = get_settings()
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def send_email(to: str, subject: str, body: str, reply_to: str | None = None) -> bool:
    """Send a plain-text email. Returns True on success, False otherwise. Never raises."""
    settings = get_settings()
    if not email_configured():
        logger.warning("email.skipped reason=smtp_not_configured to=%s subject=%s", to, subject)
        return False
    try:
        msg = EmailMessage()
        msg["From"] = settings.FROM_EMAIL
        msg["To"] = to
        msg["Subject"] = subject
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.set_content(body)

        context = ssl.create_default_context()
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.ehlo()
            try:
                server.starttls(context=context)
                server.ehlo()
            except smtplib.SMTPNotSupportedError:
                pass  # server without STARTTLS (rare); proceed
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("email.sent to=%s subject=%s", to, subject)
        return True
    except Exception as exc:  # noqa: BLE001 — delivery must never break the request
        logger.error("email.failed to=%s subject=%s error=%s", to, subject, exc)
        return False
