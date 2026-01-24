"""Family/Organization API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status, Header, Body
from typing import Optional, List
from pydantic import BaseModel, EmailStr
from pymongo.database import Database
import logging
import requests
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.core.database import get_db
from app.api.auth import get_current_user, get_org_id
from app.core.clerk_auth import get_clerk_organization, get_clerk_secret_key
from app.core.clerk_org import (
    send_clerk_organization_invitation,
    get_clerk_organization_invitations,
    revoke_clerk_organization_invitation,
    get_organization_members
)
from app.services.org_settings import get_org_settings, update_org_settings

logger = logging.getLogger(__name__)

router = APIRouter()

CLERK_API_URL = "https://api.clerk.com/v1"


@router.get("/me")
async def get_my_family(
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(get_db)
):
    """Get current user's organization (family) from Clerk."""
    org_id = current_user.get("org_id")
    
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not part of an organization. Please create or join an organization first."
        )
    
    # Run Clerk API calls in parallel for better performance
    executor = ThreadPoolExecutor(max_workers=2)
    loop = asyncio.get_event_loop()
    
    # Parallelize Clerk API calls
    clerk_org_future = loop.run_in_executor(executor, get_clerk_organization, org_id)
    memberships_future = loop.run_in_executor(executor, get_organization_members, org_id)
    
    # Wait for both to complete
    clerk_org, memberships = await asyncio.gather(clerk_org_future, memberships_future)
    
    if not clerk_org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    
    # Process members
    members = []
    for membership in memberships:
        public_user_data = membership.get("public_user_data", {})
        first_name = public_user_data.get("first_name") or ""
        last_name = public_user_data.get("last_name") or ""
        # Combine names, handling None values
        name = f"{first_name} {last_name}".strip()
        if not name:
            # Fallback to email or user_id if no name
            name = public_user_data.get("identifier") or public_user_data.get("user_id", "Unknown")
        
        members.append({
            "id": public_user_data.get("user_id", ""),
            "name": name,
            "role": membership.get("role", "member")
        })
    
    # Get event types from org_settings (this is fast, MongoDB query)
    org_settings = get_org_settings(org_id, db)
    
    return {
        "id": org_id,
        "name": clerk_org.get("name", "Family"),
        "members": members,
        "event_types": org_settings.get("event_types", []),
        "sender_names": org_settings.get("sender_names", []),
        "recipient_names": org_settings.get("recipient_names", [])
    }


@router.get("/members")
async def get_family_members(
    current_user: dict = Depends(get_current_user)
):
    """Get all members of the current user's organization from Clerk."""
    org_id = current_user.get("org_id")
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not part of an organization"
        )
    """Get all members of the current user's organization from Clerk."""
    memberships = get_organization_members(org_id)
    
    members = []
    for membership in memberships:
        public_user_data = membership.get("public_user_data", {})
        first_name = public_user_data.get("first_name") or ""
        last_name = public_user_data.get("last_name") or ""
        name = f"{first_name} {last_name}".strip() or "User"
        
        members.append({
            "id": public_user_data.get("user_id", ""),
            "name": name,
            "email": public_user_data.get("identifier", ""),
            "role": membership.get("role", "member")
        })
    
    return members


class InvitationRequest(BaseModel):
    email: EmailStr


@router.post("/invitations")
async def send_invitation(
    invitation: InvitationRequest = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Send an invitation to join the organization.
    
    Requires:
    - User must be part of an organization
    """
    org_id = current_user.get("org_id")
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not part of an organization"
        )
    clerk_user_id = current_user.get("clerk_user_id")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Clerk user ID not found"
        )
    
    # Send invitation via Clerk
    invitation_result = send_clerk_organization_invitation(
        organization_id=org_id,
        email=invitation.email,
        inviter_user_id=clerk_user_id
    )
    
    if not invitation_result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send invitation"
        )
    
    return {
        "message": "Invitation sent successfully",
        "invitation_id": invitation_result.get("id"),
        "email": invitation.email
    }


@router.get("/invitations")
async def get_invitations(
    current_user: dict = Depends(get_current_user)
):
    """Get pending invitations for the organization."""
    org_id = current_user.get("org_id")
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not part of an organization"
        )
    """Get pending invitations for the organization."""
    # Get pending invitations from Clerk
    invitations = get_clerk_organization_invitations(
        organization_id=org_id,
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
    current_user: dict = Depends(get_current_user)
):
    """Revoke a pending invitation."""
    org_id = current_user.get("org_id")
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not part of an organization"
        )
    """Revoke a pending invitation."""
    success = revoke_clerk_organization_invitation(
        organization_id=org_id,
        invitation_id=invitation_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke invitation"
        )
    
    return {"message": "Invitation revoked successfully"}
