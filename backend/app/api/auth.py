"""Authentication API endpoints using Clerk."""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from typing import Optional

from app.core.clerk_auth import verify_clerk_token, get_clerk_user, get_user_organizations
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def get_current_user(
    authorization: Optional[str] = Header(None)
) -> dict:
    """
    Get current authenticated user from Clerk token.
    
    Verifies the Clerk JWT token and extracts user/org info.
    Returns a dict with clerk_user_id and org_id - no MongoDB syncing needed.
    """
    if not authorization:
        logger.warning("Authorization header missing")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract token from "Bearer <token>"
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid authorization scheme")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify token with Clerk - this returns the decoded JWT claims
    clerk_claims = verify_clerk_token(token)
    if not clerk_claims:
        logger.error(f"Token verification failed. Token preview: {token[:30]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please check your Clerk configuration.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract user_id and org_id from JWT claims
    # Clerk uses 'sub' for user_id and 'org_id' for organization
    clerk_user_id = clerk_claims.get("sub")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token",
        )
    
    # Try to get org_id from token first (if present)
    clerk_org_id = (
        clerk_claims.get("org_id") or 
        clerk_claims.get("organization_id") or
        (clerk_claims.get("org") and isinstance(clerk_claims["org"], dict) and clerk_claims["org"].get("id")) or
        None
    )
    
    # If not in token, fetch from Clerk API (more reliable)
    if not clerk_org_id:
        memberships = get_user_organizations(clerk_user_id)
        if memberships:
            # Get the first organization (users typically have one)
            # In the future, we could support multiple orgs or let user select
            first_membership = memberships[0]
            
            # Try different ways the org_id might be nested in the response
            clerk_org_id = (
                first_membership.get("organization", {}).get("id") or
                first_membership.get("organization_id") or
                first_membership.get("org_id") or
                (isinstance(first_membership.get("organization"), str) and first_membership.get("organization")) or
                None
            )
            
            if clerk_org_id:
                logger.debug(f"Found org_id from API: {clerk_org_id}")
            else:
                logger.warning(f"Could not extract org_id from membership: {first_membership}")
    
    # Get user info from Clerk API for additional details
    clerk_user = get_clerk_user(clerk_user_id)
    email = None
    name = "User"
    if clerk_user:
        if clerk_user.get('email_addresses'):
            email = clerk_user['email_addresses'][0].get('email_address', '')
        first_name = clerk_user.get('first_name') or ''
        last_name = clerk_user.get('last_name') or ''
        name = f"{first_name} {last_name}".strip() or email or 'User'
    
    # Return a simple dict with user info - no MongoDB needed
    return {
        "clerk_user_id": clerk_user_id,
        "org_id": clerk_org_id,
        "email": email,
        "name": name
    }


def get_org_id(current_user: dict = Depends(get_current_user)) -> str:
    """
    Extract org_id from current user.
    Raises error if user is not part of an organization.
    
    Use this as a dependency in routes that require organization context.
    """
    org_id = current_user.get("org_id")
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not part of an organization"
        )
    return org_id


@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information from Clerk."""
    return {
        "clerk_user_id": current_user.get("clerk_user_id"),
        "org_id": current_user.get("org_id"),
        "email": current_user.get("email"),
        "name": current_user.get("name")
    }


@router.get("/test-org-id")
async def test_org_id(
    current_user: dict = Depends(get_current_user)
):
    """
    Test endpoint to verify org_id extraction from Clerk token.
    This endpoint helps verify that org_id is being properly extracted.
    """
    return {
        "user_id": current_user.get("clerk_user_id"),
        "org_id": current_user.get("org_id"),
        "has_org": bool(current_user.get("org_id")),
        "message": "Token verified successfully" if current_user.get("org_id") else "Token verified but no organization found"
    }
