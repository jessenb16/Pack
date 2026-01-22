"""Family API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from datetime import datetime

from app.core.database import get_db, get_family_filter
from app.api.auth import get_current_user
from app.core.clerk_auth import get_clerk_organization, verify_clerk_token
from app.core.clerk_org import (
    create_clerk_organization,
    send_clerk_organization_invitation,
    get_clerk_organization_invitations,
    revoke_clerk_organization_invitation
)
from app.core.clerk_user_sync import sync_clerk_organization_to_mongodb, link_user_to_family
from app.models.family import FamilyCreate, FamilyResponse
from pymongo.database import Database
from fastapi import Header
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/me", response_model=FamilyResponse)
async def get_my_family(
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Get current user's family."""
    if not current_user.get("family_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not part of a family"
        )
    
    family = db.families.find_one({"_id": ObjectId(current_user["family_id"])})
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found"
        )
    
    return FamilyResponse(
        id=str(family["_id"]),
        name=family["name"],
        members=family.get("members", []),
        event_types=family.get("event_types", []),
        created_at=family.get("created_at")
    )


@router.post("", response_model=FamilyResponse, status_code=status.HTTP_201_CREATED)
async def create_family(
    family_data: FamilyCreate,
    current_user: dict = Depends(get_current_user),
    authorization: Optional[str] = Header(None),
    db: Database = Depends(get_db)
):
    """
    Create a new family.
    
    NOTE: This endpoint is now primarily for backward compatibility.
    The recommended flow is:
    1. User creates organization via Clerk's <CreateOrganization> component (frontend)
    2. Organization is automatically synced to MongoDB on first API call (via get_current_user)
    
    This endpoint can still be used if you need to create a family programmatically.
    """
    # Check if user already has a family
    if current_user.get("family_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already part of a family"
        )
    
    # Get Clerk user ID from token to create organization
    clerk_user_id = current_user.get("clerk_user_id")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Clerk user ID not found"
        )
    
    # Create Clerk Organization first
    clerk_org = create_clerk_organization(family_data.name, clerk_user_id)
    if not clerk_org:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create Clerk organization"
        )
    
    clerk_org_id = clerk_org.get("id")
    if not clerk_org_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Clerk organization ID not returned"
        )
    
    # Sync organization to MongoDB as Family
    family = sync_clerk_organization_to_mongodb(clerk_org_id, db)
    if not family:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync organization to MongoDB"
        )
    
    family_id = str(family["_id"])
    
    # Link user to family and set as admin
    link_user_to_family(str(current_user["_id"]), family_id, db, role="admin")
    
    # Refresh user data
    current_user = db.users.find_one({"_id": current_user["_id"]})
    
    return FamilyResponse(
        id=family_id,
        name=family["name"],
        members=family.get("members", []),
        event_types=family.get("event_types", []),
        created_at=family.get("created_at")
    )


@router.get("/members", response_model=list)
async def get_family_members(
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Get all members of the current user's family."""
    if not current_user.get("family_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not part of a family"
        )
    
    family = db.families.find_one({"_id": ObjectId(current_user["family_id"])})
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found"
        )
    
    # Get user details for each member
    member_ids = [ObjectId(mid) for mid in family.get("members", [])]
    members = list(db.users.find({"_id": {"$in": member_ids}}))
    
    return [
        {
            "id": str(m["_id"]),
            "name": m["name"],
            "email": m.get("email", ""),
            "role": m.get("role", "member")
        }
        for m in members
    ]


class InvitationRequest(BaseModel):
    email: EmailStr


@router.post("/invitations")
async def send_invitation(
    invitation: InvitationRequest = Body(...),
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """
    Send an invitation to join the family organization.
    
    Requires:
    - User must be part of a family
    - User must be an admin (or we can allow all members to invite)
    """
    if not current_user.get("family_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not part of a family"
        )
    
    family = db.families.find_one({"_id": ObjectId(current_user["family_id"])})
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found"
        )
    
    clerk_org_id = family.get("clerk_org_id")
    if not clerk_org_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Family organization not found in Clerk"
        )
    
    clerk_user_id = current_user.get("clerk_user_id")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Clerk user ID not found"
        )
    
    # Send invitation via Clerk
    invitation = send_clerk_organization_invitation(
        organization_id=clerk_org_id,
        email=invitation.email,
        inviter_user_id=clerk_user_id
    )
    
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send invitation"
        )
    
    return {
        "message": "Invitation sent successfully",
        "invitation_id": invitation.get("id"),
        "email": invitation.email
    }


@router.get("/invitations")
async def get_invitations(
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Get pending invitations for the family."""
    if not current_user.get("family_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not part of a family"
        )
    
    family = db.families.find_one({"_id": ObjectId(current_user["family_id"])})
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found"
        )
    
    clerk_org_id = family.get("clerk_org_id")
    if not clerk_org_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Family organization not found in Clerk"
        )
    
    # Get pending invitations from Clerk
    invitations = get_clerk_organization_invitations(
        organization_id=clerk_org_id,
        status="pending"
    )
    
    return [
        {
            "id": inv.get("id"),
            "email": inv.get("email_address"),
            "status": inv.get("status"),
            "created_at": inv.get("created_at"),
            "updated_at": inv.get("updated_at")
        }
        for inv in invitations
    ]


@router.post("/invitations/{invitation_id}/revoke")
async def revoke_invitation(
    invitation_id: str,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Revoke a pending invitation."""
    if not current_user.get("family_id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not part of a family"
        )
    
    family = db.families.find_one({"_id": ObjectId(current_user["family_id"])})
    if not family:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Family not found"
        )
    
    clerk_org_id = family.get("clerk_org_id")
    if not clerk_org_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Family organization not found in Clerk"
        )
    
    success = revoke_clerk_organization_invitation(
        organization_id=clerk_org_id,
        invitation_id=invitation_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke invitation"
        )
    
    return {"message": "Invitation revoked successfully"}
