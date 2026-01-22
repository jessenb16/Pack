"""Sync Clerk users and organizations to MongoDB."""
from typing import Optional, Dict
from bson import ObjectId
from datetime import datetime
from app.core.database import get_db
from app.core.clerk_auth import get_clerk_user, get_clerk_organization
from pymongo.database import Database
import logging

logger = logging.getLogger(__name__)


def sync_clerk_user_to_mongodb(clerk_user_id: str, db: Database) -> Optional[Dict]:
    """
    Sync a Clerk user to MongoDB.
    Creates or updates the user document.
    
    Returns:
        MongoDB user document
    """
    try:
        # Get user from Clerk
        clerk_user = get_clerk_user(clerk_user_id)
        if not clerk_user:
            logger.warning(f"Could not fetch Clerk user: {clerk_user_id}")
            return None
        
        # Extract user data
        email = None
        if clerk_user.get('email_addresses'):
            email = clerk_user['email_addresses'][0].get('email_address', '')
        
        first_name = clerk_user.get('first_name', '')
        last_name = clerk_user.get('last_name', '')
        name = f"{first_name} {last_name}".strip() or email or 'User'
        
        # Check if user exists in MongoDB
        existing_user = db.users.find_one({"clerk_user_id": clerk_user_id})
        
        user_data = {
            "clerk_user_id": clerk_user_id,
            "email": email.lower() if email else None,
            "name": name,
            "updated_at": datetime.utcnow()
        }
        
        if existing_user:
            # Update existing user
            db.users.update_one(
                {"_id": existing_user["_id"]},
                {"$set": user_data}
            )
            user_data["_id"] = existing_user["_id"]
            logger.info(f"Updated user in MongoDB: {clerk_user_id}")
        else:
            # Create new user
            user_data.update({
                "family_id": None,
                "role": "member",
                "created_at": datetime.utcnow()
            })
            result = db.users.insert_one(user_data)
            user_data["_id"] = result.inserted_id
            logger.info(f"Created user in MongoDB: {clerk_user_id}")
        
        return user_data
        
    except Exception as e:
        logger.error(f"Error syncing Clerk user to MongoDB: {e}")
        return None


def sync_clerk_organization_to_mongodb(clerk_org_id: str, db: Database) -> Optional[Dict]:
    """
    Sync a Clerk organization to MongoDB as a Family.
    
    Returns:
        MongoDB family document
    """
    try:
        # Get organization from Clerk
        clerk_org = get_clerk_organization(clerk_org_id)
        if not clerk_org:
            logger.warning(f"Could not fetch Clerk organization: {clerk_org_id}")
            return None
        
        org_name = clerk_org.get('name', 'Family')
        
        # Check if family exists
        existing_family = db.families.find_one({"clerk_org_id": clerk_org_id})
        
        family_data = {
            "clerk_org_id": clerk_org_id,
            "name": org_name,
            "updated_at": datetime.utcnow()
        }
        
        if existing_family:
            # Update existing family
            db.families.update_one(
                {"_id": existing_family["_id"]},
                {"$set": family_data}
            )
            family_data["_id"] = existing_family["_id"]
            logger.info(f"Updated family in MongoDB: {clerk_org_id}")
        else:
            # Create new family
            family_data.update({
                "members": [],
                "event_types": [],
                "created_at": datetime.utcnow()
            })
            result = db.families.insert_one(family_data)
            family_data["_id"] = result.inserted_id
            logger.info(f"Created family in MongoDB: {clerk_org_id}")
        
        return family_data
        
    except Exception as e:
        logger.error(f"Error syncing Clerk organization to MongoDB: {e}")
        return None


def link_user_to_family(user_id: str, family_id: str, db: Database, role: str = "member") -> bool:
    """Link a user to a family."""
    try:
        # Update user
        db.users.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "family_id": family_id,
                    "role": role
                }
            }
        )
        
        # Add user to family members if not already there
        db.families.update_one(
            {"_id": ObjectId(family_id)},
            {
                "$addToSet": {"members": user_id}
            }
        )
        
        logger.info(f"Linked user {user_id} to family {family_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error linking user to family: {e}")
        return False

