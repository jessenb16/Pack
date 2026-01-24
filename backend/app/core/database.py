"""MongoDB database connection."""
from pymongo import MongoClient
from pymongo.database import Database
from app.core.config import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

_client: Optional[MongoClient] = None
_db: Optional[Database] = None


def get_client() -> MongoClient:
    """Get MongoDB client (singleton)."""
    global _client
    if _client is None:
        try:
            _client = MongoClient(
                settings.MONGODB_URI,
                serverSelectionTimeoutMS=5000
            )
            _client.admin.command('ping')  # Test connection
            logger.info("MongoDB connection established successfully")
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            raise
    return _client


def get_db() -> Database:
    """Get MongoDB database (singleton)."""
    global _db
    if _db is None:
        _db = get_client()[settings.DATABASE_NAME]
        # Create indexes for performance
        _create_indexes(_db)
    return _db


def _create_indexes(db: Database):
    """Create database indexes for better query performance."""
    try:
        # Index on org_id for fast document queries
        db.documents.create_index("org_id")
        # Index on created_at for sorting
        db.documents.create_index("created_at")
        # Compound index for common queries
        db.documents.create_index([("org_id", 1), ("created_at", -1)])
        # Index on metadata fields for filtering
        db.documents.create_index("metadata.sender_name")
        db.documents.create_index("metadata.event_type")
        db.documents.create_index("metadata.doc_date")
        
        # Index on org_settings _id (already indexed as _id, but explicit is good)
        db.org_settings.create_index("_id")
        
        logger.info("Database indexes created successfully")
    except Exception as e:
        logger.warning(f"Could not create indexes (may already exist): {e}")


def get_family_filter(family_id: str) -> dict:
    """
    Returns a filter dictionary for family-specific queries.
    
    NOTE: This uses family_id (MongoDB _id). For new code, prefer get_org_filter()
    which uses org_id directly from Clerk token.
    """
    return {"family_id": family_id}


def get_org_filter(org_id: str) -> dict:
    """
    Returns a filter dictionary for organization-specific queries using org_id.
    
    This is the preferred method per OVERVIEW.md - uses org_id directly from Clerk token.
    All documents should be filtered by org_id for security.
    """
    return {"org_id": org_id}

