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
    return _db


def get_family_filter(family_id: str) -> dict:
    """Returns a filter dictionary for family-specific queries."""
    return {"family_id": family_id}

