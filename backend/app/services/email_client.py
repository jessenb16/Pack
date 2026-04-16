"""Email sending abstraction and Resend implementation."""

from __future__ import annotations

import logging
from typing import Optional, Sequence

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailSendError(RuntimeError):
    pass


def send_email(
    *,
    to: Sequence[str],
    subject: str,
    html: str,
    text: Optional[str] = None,
) -> None:
    """
    Send an email using Resend.

    Raises EmailSendError on failures.
    """
    if not settings.RESEND_API_KEY:
        raise EmailSendError("RESEND_API_KEY is not set")
    if not settings.EMAIL_FROM:
        raise EmailSendError("EMAIL_FROM is not set")
    if not to:
        return

    payload = {
        "from": settings.EMAIL_FROM,
        "to": list(to),
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )
    except Exception as e:
        raise EmailSendError(f"Resend request failed: {e}") from e

    if resp.status_code >= 300:
        logger.error("Resend error %s: %s", resp.status_code, resp.text)
        raise EmailSendError(f"Resend returned {resp.status_code}")

