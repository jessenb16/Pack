"""Authentication API endpoints using Clerk."""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from bson import ObjectId
from typing import Optional

from app.core.database import get_db
from app.core.clerk_auth import verify_clerk_token
from app.core.clerk_user_sync import sync_clerk_user_to_mongodb, sync_clerk_organization_to_mongodb, link_user_to_family
from app.models.user import UserResponse
from pymongo.database import Database
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Database = Depends(get_db)
) -> dict:
    """
    Get current authenticated user from Clerk token.
    
    Verifies the Clerk JWT token and syncs user to MongoDB if needed.
    """
    if not authorization:
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
    
    # Verify token with Clerk
    clerk_session = verify_clerk_token(token)
    if not clerk_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user ID from Clerk session
    # Clerk session can have user_id directly or in nested structure
    clerk_user_id = clerk_session.get("user_id") or clerk_session.get("sub")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token",
        )
    
    # Sync user to MongoDB
    user = sync_clerk_user_to_mongodb(clerk_user_id, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync user",
        )
    
    # Check if user has an organization (family) in Clerk
    clerk_org_id = clerk_session.get("org_id") or clerk_session.get("organization_id")
    if clerk_org_id:
        # Sync organization to MongoDB
        family = sync_clerk_organization_to_mongodb(clerk_org_id, db)
        if family:
            # Link user to family if not already linked
            if not user.get("family_id") or user.get("family_id") != str(family["_id"]):
                link_user_to_family(str(user["_id"]), str(family["_id"]), db)
                # Refresh user data
                user = db.users.find_one({"_id": user["_id"]})
    
    return user


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(
        id=str(current_user["_id"]),
        email=current_user.get("email", ""),
        name=current_user.get("name", "User"),
        family_id=current_user.get("family_id"),
        role=current_user.get("role", "member"),
        created_at=current_user.get("created_at")
    )
