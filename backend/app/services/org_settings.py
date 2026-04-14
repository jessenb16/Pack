"""Organization settings service for managing org_settings collection."""
from typing import Optional, List, Dict, Any
from pymongo.database import Database
import logging

from app.services.label_catalog import migrate_org_settings_document_shape, catalog_lists

logger = logging.getLogger(__name__)


def get_org_settings(org_id: str, db: Database) -> Dict[str, Any]:
    """
    Get organization settings for a given org_id.
    Creates default settings if they don't exist.
    Migrates legacy string lists to [{id, label}] catalogs when present.
    """
    try:
        settings = db.org_settings.find_one({"_id": org_id})

        if not settings:
            default_settings = {
                "_id": org_id,
                "senders": [],
                "event_types": [],
                "recipients": [],
            }
            db.org_settings.insert_one(default_settings)
            return default_settings

        migrate_org_settings_document_shape(org_id, db)
        return db.org_settings.find_one({"_id": org_id}) or settings
    except Exception as e:
        logger.error(f"Error getting org settings: {e}")
        return {
            "_id": org_id,
            "senders": [],
            "event_types": [],
            "recipients": [],
        }


def update_org_settings(
    org_id: str,
    db: Database,
    senders: Optional[List[Dict[str, str]]] = None,
    event_types: Optional[List[Dict[str, str]]] = None,
    recipients: Optional[List[Dict[str, str]]] = None,
) -> bool:
    """Replace full catalog arrays (advanced; prefer label_catalog.ensure_label for v1)."""
    try:
        update_data: Dict[str, Any] = {}
        if senders is not None:
            update_data["senders"] = senders
        if event_types is not None:
            update_data["event_types"] = event_types
        if recipients is not None:
            update_data["recipients"] = recipients

        if not update_data:
            return True

        db.org_settings.update_one(
            {"_id": org_id},
            {"$set": update_data},
            upsert=True,
        )

        return True
    except Exception as e:
        logger.error(f"Error updating org settings: {e}")
        return False


def get_catalog_for_org(org_id: str, db: Database):
    """Return (senders, event_types, recipients) as normalized [{id, label}, ...]."""
    doc = get_org_settings(org_id, db)
    return catalog_lists(doc)
