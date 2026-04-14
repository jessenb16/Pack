"""MongoDB database connection."""
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, OperationFailure
from motor.motor_asyncio import AsyncIOMotorClient
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

_client: Optional[MongoClient] = None
_db: Optional[Database] = None

# Async clients for agent service
_async_client: Optional[AsyncIOMotorClient] = None
_async_db: Optional[AsyncIOMotorDatabase] = None


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
        # Index on metadata fields for filtering (label strings deprecated on documents)
        db.documents.create_index("metadata.doc_date")
        db.documents.create_index("metadata.sender_id")
        db.documents.create_index("metadata.event_type_id")
        db.documents.create_index("metadata.recipient_id")
        
        # Enforce catalog uniqueness (no duplicate label_cf within a catalog array).
        # These should fail loudly if there are duplicates, permissions issues, etc.
        # (silently continuing would remove the uniqueness guarantee).
        for name, keys in [
            ("org_settings_senders_label_cf_unique", [("_id", 1), ("senders.label_cf", 1)]),
            ("org_settings_event_types_label_cf_unique", [("_id", 1), ("event_types.label_cf", 1)]),
            ("org_settings_recipients_label_cf_unique", [("_id", 1), ("recipients.label_cf", 1)]),
        ]:
            try:
                db.org_settings.create_index(keys, name=name, unique=True, sparse=True)
            except (DuplicateKeyError, OperationFailure) as e:
                msg = str(e)
                # Treat "already exists" as non-fatal; everything else should surface.
                if "already exists" in msg or "Index with name" in msg:
                    logger.info(f"Index {name} already exists")
                else:
                    raise
        
        logger.info("Database indexes created successfully")
    except Exception as e:
        logger.error(f"Database index creation failed: {e}")
        raise


def get_org_filter(org_id: str) -> dict:
    """
    Returns a filter dictionary for organization-specific queries using org_id.
    
    This is the preferred method per OVERVIEW.md - uses org_id directly from Clerk token.
    All documents should be filtered by org_id for security.
    """
    return {"org_id": org_id}


def get_async_client() -> AsyncIOMotorClient:
    """Get async MongoDB client (singleton) for agent service."""
    global _async_client
    if _async_client is None:
        try:
            _async_client = AsyncIOMotorClient(
                settings.MONGODB_URI,
                serverSelectionTimeoutMS=5000
            )
            logger.info("Async MongoDB connection established successfully")
        except Exception as e:
            logger.error(f"Async MongoDB connection failed: {e}")
            raise
    return _async_client


async def get_database() -> AsyncIOMotorDatabase:
    """Get async MongoDB database (singleton) for agent service."""
    global _async_db
    if _async_db is None:
        _async_db = get_async_client()[settings.DATABASE_NAME]
    return _async_db

