"""User settings service for per-pack per-user preferences."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pymongo.database import Database


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_document_uploaded_email_disabled(
    *,
    org_id: str,
    clerk_user_id: str,
    db: Database,
) -> bool:
    """
    Returns whether the user has disabled 'document uploaded' emails for this org.

    Default is False (emails enabled) if no user_settings doc exists.
    """
    doc = db.user_settings.find_one(
        {"org_id": org_id, "clerk_user_id": clerk_user_id},
        projection={"notifications.document_uploaded_email_disabled": 1},
    )
    if not doc:
        return False
    notifications = doc.get("notifications") or {}
    return bool(notifications.get("document_uploaded_email_disabled", False))


def set_document_uploaded_email_disabled(
    *,
    org_id: str,
    clerk_user_id: str,
    disabled: bool,
    db: Database,
) -> None:
    """
    Upserts the opt-out flag for this user+org.
    """
    update: Dict[str, Any] = {
        "$set": {
            "notifications.document_uploaded_email_disabled": bool(disabled),
            "updated_at": _now_utc(),
        },
        "$setOnInsert": {
            "org_id": org_id,
            "clerk_user_id": clerk_user_id,
            "created_at": _now_utc(),
        },
    }
    db.user_settings.update_one(
        {"org_id": org_id, "clerk_user_id": clerk_user_id},
        update,
        upsert=True,
    )


def get_user_settings_doc(
    *,
    org_id: str,
    clerk_user_id: str,
    db: Database,
) -> Optional[Dict[str, Any]]:
    """Convenience getter (primarily for debugging/admin usage)."""
    return db.user_settings.find_one({"org_id": org_id, "clerk_user_id": clerk_user_id})

