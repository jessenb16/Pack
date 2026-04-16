"""Email templates and helpers for notifications."""

from __future__ import annotations

from html import escape
from typing import Any, Dict, Optional, Tuple


def _fmt_label(label: Optional[str]) -> str:
    if not label:
        return "—"
    return escape(str(label))


def build_document_uploaded_email(
    *,
    uploader_name: str,
    dashboard_url: str,
    caption: str,
    doc_date: str,
    sender_label: Optional[str],
    event_label: Optional[str],
    recipient_label: Optional[str],
) -> Tuple[str, str, str]:
    """
    Returns (subject, html, text).
    """
    uploader_safe = uploader_name.strip() or "Someone"
    subject = f"{uploader_safe} uploaded a new document"

    cap = caption.strip()
    cap_html = escape(cap) if cap else ""
    dd = escape(doc_date or "")
    sender = _fmt_label(sender_label)
    event = _fmt_label(event_label)
    recipient = _fmt_label(recipient_label)
    cta = escape(dashboard_url)

    html = f"""\
<div style="margin:0; padding:24px; background:#7f1d1d; background: linear-gradient(90deg, #facc15 0%, #ca8a04 45%, #7f1d1d 100%); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; color:#111827;">
  <div style="max-width:560px; margin:0 auto;">
    <div style="margin-bottom:14px;">
      <div style="display:inline-block; font-size:12px; letter-spacing:0.12em; text-transform:uppercase; color:#ffffff; background: rgba(0,0,0,0.18); border:1px solid rgba(255,255,255,0.18); padding:6px 10px; border-radius:999px;">
        Pack
      </div>
      <div style="font-size:20px; font-weight:800; margin-top:10px; color:#ffffff; text-shadow: 0 2px 10px rgba(0,0,0,0.25);">
        New upload
      </div>
    </div>

    <div style="background:#ffffff; border:1px solid #e5e7eb; border-radius:14px; box-shadow: 0 2px 8px rgba(17,24,39,0.06); overflow:hidden;">
      <div style="padding:18px 18px 14px 18px;">
        <div style="font-size:14px; color:#374151;">
          <strong style="color:#111827;">{escape(uploader_safe)}</strong> uploaded a new document.
        </div>

        <div style="margin-top:14px; padding:12px 12px; border-radius:12px; background:#f9fafb; border:1px solid #eef2f7;">
          <div style="font-size:12px; color:#6b7280; margin-bottom:6px;">Caption</div>
          <div style="font-size:14px; line-height:1.45; color:#111827;">{cap_html or "—"}</div>
        </div>

        <table style="width:100%; border-collapse:separate; border-spacing:0 10px; margin-top:8px; font-size:14px;">
          <tr>
            <td style="width:40%; color:#6b7280;">Date</td>
            <td style="color:#111827; font-weight:600;">{dd or "—"}</td>
          </tr>
          <tr>
            <td style="width:40%; color:#6b7280;">Sender/Poster</td>
            <td style="color:#111827; font-weight:600;">{sender}</td>
          </tr>
          <tr>
            <td style="width:40%; color:#6b7280;">Event</td>
            <td style="color:#111827; font-weight:600;">{event}</td>
          </tr>
          <tr>
            <td style="width:40%; color:#6b7280;">Recipient</td>
            <td style="color:#111827; font-weight:600;">{recipient}</td>
          </tr>
        </table>

        <div style="margin-top:16px;">
          <a href="{cta}" style="display:inline-block; background:#7f1d1d; color:#ffffff; text-decoration:none; padding:11px 14px; border-radius:10px; font-weight:700; font-size:14px;">
            View in Pack
          </a>
        </div>
      </div>

      <div style="padding:12px 18px; background:#fcfcfd; border-top:1px solid #eef2f7; font-size:12px; color:#6b7280; line-height:1.4;">
        To stop these emails, open Pack and go to <strong>Settings</strong> → <strong>Notifications</strong>.
      </div>
    </div>
    <div style="margin-top:14px; font-size:12px; color:#9ca3af; text-align:center;">
      You’re receiving this because you’re a member of this pack.
    </div>
  </div>
</div>
"""

    text = (
        f"{uploader_safe} uploaded a new document\\n\\n"
        f"Caption: {cap}\\n"
        f"Date: {doc_date}\\n"
        f"Sender/Poster: {sender_label or '—'}\\n"
        f"Event: {event_label or '—'}\\n"
        f"Recipient: {recipient_label or '—'}\\n\\n"
        f"View in Pack: {dashboard_url}\\n\\n"
        f"To stop these emails, open Pack and go to Settings → Notifications."
    )

    return subject, html, text

