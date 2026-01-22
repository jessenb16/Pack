"""Clerk webhook endpoints for user/organization sync."""
from fastapi import APIRouter, Request, HTTPException, status, Header
from app.core.database import get_db
from app.core.clerk_user_sync import sync_clerk_user_to_mongodb, sync_clerk_organization_to_mongodb, link_user_to_family
from app.core.clerk_auth import get_clerk_secret_key
from pymongo.database import Database
import hmac
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify Clerk webhook signature."""
    try:
        secret = get_clerk_secret_key()
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Clerk sends signature as "v1,<signature>"
        if signature.startswith("v1,"):
            received_signature = signature.split(",")[1]
            return hmac.compare_digest(expected_signature, received_signature)
        
        return False
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        return False


@router.post("/clerk")
async def clerk_webhook(request: Request):
    """
    Handle Clerk webhook events.
    
    This endpoint receives events from Clerk when:
    - Users sign up or update their profile
    - Users join or leave organizations
    - Organizations are created or updated
    """
    try:
        # Get webhook signature
        svix_id = request.headers.get("svix-id")
        svix_timestamp = request.headers.get("svix-timestamp")
        svix_signature = request.headers.get("svix-signature")
        
        # Get raw body for signature verification
        body = await request.body()
        
        # Verify signature (optional but recommended)
        if svix_signature:
            # Note: For production, use the svix-python library for proper verification
            # This is a simplified version
            if not verify_webhook_signature(body, svix_signature):
                logger.warning("Webhook signature verification failed")
                # In production, you might want to reject here
                # For now, we'll log and continue
        
        # Parse webhook event
        event = json.loads(body.decode('utf-8'))
        event_type = event.get("type")
        data = event.get("data", {})
        
        logger.info(f"Received Clerk webhook event: {event_type}")
        
        db = get_db()
        
        if event_type == "user.created" or event_type == "user.updated":
            # Sync user to MongoDB
            clerk_user_id = data.get("id")
            if clerk_user_id:
                sync_clerk_user_to_mongodb(clerk_user_id, db)
        
        elif event_type == "organization.created" or event_type == "organization.updated":
            # Sync organization to MongoDB
            clerk_org_id = data.get("id")
            if clerk_org_id:
                sync_clerk_organization_to_mongodb(clerk_org_id, db)
        
        elif event_type == "organizationMembership.created":
            # User joined an organization
            org_id = data.get("organization", {}).get("id") or data.get("organization_id")
            user_id = data.get("public_user_data", {}).get("user_id") or data.get("user_id")
            
            if org_id and user_id:
                # Sync both user and org first
                user = sync_clerk_user_to_mongodb(user_id, db)
                family = sync_clerk_organization_to_mongodb(org_id, db)
                
                if user and family:
                    # Link user to family
                    link_user_to_family(str(user["_id"]), str(family["_id"]), db)
        
        elif event_type == "organizationMembership.deleted":
            # User left an organization
            org_id = data.get("organization", {}).get("id") or data.get("organization_id")
            user_id = data.get("public_user_data", {}).get("user_id") or data.get("user_id")
            
            if org_id and user_id:
                # Find user and remove from family
                user = db.users.find_one({"clerk_user_id": user_id})
                family = db.families.find_one({"clerk_org_id": org_id})
                
                if user and family:
                    # Remove user from family
                    db.families.update_one(
                        {"_id": family["_id"]},
                        {"$pull": {"members": str(user["_id"])}}
                    )
                    
                    # Clear user's family_id if this was their only family
                    db.users.update_one(
                        {"_id": user["_id"]},
                        {"$set": {"family_id": None}}
                    )
        
        return {"received": True}
        
    except Exception as e:
        logger.error(f"Error processing Clerk webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing webhook"
        )

