"""Organization settings service for managing org_settings collection."""
from typing import Optional, List, Dict
from pymongo.database import Database
import logging

logger = logging.getLogger(__name__)


def get_org_settings(org_id: str, db: Database) -> Dict:
    """
    Get organization settings for a given org_id.
    Creates default settings if they don't exist.
    
    Returns:
        Dictionary with event_types, sender_names, recipient_names
    """
    try:
        settings = db.org_settings.find_one({"_id": org_id})
        
        if not settings:
            # Create default settings
            default_settings = {
                "_id": org_id,
                "event_types": [],
                "sender_names": [],
                "recipient_names": []
            }
            db.org_settings.insert_one(default_settings)
            return default_settings
        
        return settings
    except Exception as e:
        logger.error(f"Error getting org settings: {e}")
        return {
            "_id": org_id,
            "event_types": [],
            "sender_names": [],
            "recipient_names": []
        }


def update_org_settings(
    org_id: str,
    db: Database,
    event_types: Optional[List[str]] = None,
    sender_names: Optional[List[str]] = None,
    recipient_names: Optional[List[str]] = None
) -> bool:
    """
    Update organization settings.
    
    Args:
        org_id: Clerk organization ID
        db: Database instance
        event_types: List of event types to set
        sender_names: List of sender names to set
        recipient_names: List of recipient names to set
    
    Returns:
        True if successful, False otherwise
    """
    try:
        update_data = {}
        
        if event_types is not None:
            update_data["event_types"] = event_types
        if sender_names is not None:
            update_data["sender_names"] = sender_names
        if recipient_names is not None:
            update_data["recipient_names"] = recipient_names
        
        if not update_data:
            return True
        
        # Upsert settings
        db.org_settings.update_one(
            {"_id": org_id},
            {"$set": update_data},
            upsert=True
        )
        
        return True
    except Exception as e:
        logger.error(f"Error updating org settings: {e}")
        return False


def add_event_type(org_id: str, event_type: str, db: Database) -> bool:
    """Add an event type to org settings if it doesn't exist."""
    try:
        db.org_settings.update_one(
            {"_id": org_id},
            {"$addToSet": {"event_types": event_type}},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error adding event type: {e}")
        return False


def add_sender_name(org_id: str, sender_name: str, db: Database) -> bool:
    """Add a sender name to org settings if it doesn't exist."""
    try:
        db.org_settings.update_one(
            {"_id": org_id},
            {"$addToSet": {"sender_names": sender_name}},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error adding sender name: {e}")
        return False


def add_recipient_name(org_id: str, recipient_name: str, db: Database) -> bool:
    """Add a recipient name to org settings if it doesn't exist."""
    try:
        db.org_settings.update_one(
            {"_id": org_id},
            {"$addToSet": {"recipient_names": recipient_name}},
            upsert=True
        )
        return True
    except Exception as e:
        logger.error(f"Error adding recipient name: {e}")
        return False

