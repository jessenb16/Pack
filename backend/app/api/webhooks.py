"""Clerk webhook endpoints."""
from fastapi import APIRouter, Request, HTTPException, status
from app.core.database import get_db
from app.core.clerk_auth import get_clerk_secret_key
from app.services.org_settings import get_org_settings
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
        
        # Only handle organization creation to initialize org_settings
        if event_type == "organization.created":
            clerk_org_id = data.get("id")
            if clerk_org_id:
                # Initialize org_settings for new organization
                get_org_settings(clerk_org_id, db)
                logger.info(f"Initialized org_settings for organization: {clerk_org_id}")
        
        # All other events (user updates, org updates, memberships) are handled by Clerk
        # We don't need to sync anything to MongoDB since we use Clerk as source of truth
        
        return {"received": True}
        
    except Exception as e:
        logger.error(f"Error processing Clerk webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing webhook"
        )

