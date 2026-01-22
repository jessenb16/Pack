"""Clerk Organization management utilities."""
import os
import requests
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

CLERK_API_URL = "https://api.clerk.com/v1"


def get_clerk_secret_key() -> str:
    """Get Clerk secret key from environment."""
    key = os.getenv("CLERK_SECRET_KEY", "")
    if not key:
        raise ValueError("CLERK_SECRET_KEY environment variable is not set")
    return key


def create_clerk_organization(name: str, created_by_user_id: str) -> Optional[Dict]:
    """
    Create a new Clerk Organization.
    
    Args:
        name: Organization name
        created_by_user_id: Clerk user ID of the creator
        
    Returns:
        Organization data from Clerk, or None if creation failed
    """
    try:
        headers = {
            "Authorization": f"Bearer {get_clerk_secret_key()}",
            "Content-Type": "application/json"
        }
        
        data = {
            "name": name,
            "created_by": created_by_user_id,
            "max_allowed_memberships": 50
        }
        
        response = requests.post(
            f"{CLERK_API_URL}/organizations",
            headers=headers,
            json=data
        )
        
        if response.status_code in [200, 201]:
            return response.json()
        else:
            logger.error(f"Failed to create Clerk organization: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error creating Clerk organization: {e}")
        return None


def get_user_organizations(clerk_user_id: str) -> list:
    """Get all organizations a user belongs to."""
    try:
        headers = {
            "Authorization": f"Bearer {get_clerk_secret_key()}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{CLERK_API_URL}/users/{clerk_user_id}/organization_memberships",
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and 'data' in result:
                return result['data']
            return []
        else:
            logger.warning(f"Failed to get user organizations: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Error getting user organizations: {e}")
        return []


def send_clerk_organization_invitation(
    organization_id: str,
    email: str,
    inviter_user_id: str,
    role: str = "org:member"
) -> Optional[Dict]:
    """
    Send an invitation to join a Clerk organization.
    
    Args:
        organization_id: Clerk organization ID
        email: Email address of the invitee
        inviter_user_id: Clerk user ID of the person sending the invitation
        role: Role to assign (default: "org:member")
        
    Returns:
        Invitation data from Clerk, or None if failed
    """
    try:
        headers = {
            "Authorization": f"Bearer {get_clerk_secret_key()}",
            "Content-Type": "application/json"
        }
        
        data = {
            "email_address": email,
            "inviter_user_id": inviter_user_id,
            "role": role
        }
        
        response = requests.post(
            f"{CLERK_API_URL}/organizations/{organization_id}/invitations",
            headers=headers,
            json=data
        )
        
        if response.status_code in [200, 201]:
            return response.json()
        else:
            logger.error(f"Failed to send invitation: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error sending invitation: {e}")
        return None


def get_clerk_organization_invitations(
    organization_id: str,
    status: str = "pending"
) -> list:
    """
    Get invitations for a Clerk organization.
    
    Args:
        organization_id: Clerk organization ID
        status: Filter by status ("pending", "accepted", "revoked")
        
    Returns:
        List of invitation objects
    """
    try:
        headers = {
            "Authorization": f"Bearer {get_clerk_secret_key()}",
            "Content-Type": "application/json"
        }
        
        params = {"status": status} if status else {}
        
        response = requests.get(
            f"{CLERK_API_URL}/organizations/{organization_id}/invitations",
            headers=headers,
            params=params
        )
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and 'data' in result:
                return result['data']
            return []
        else:
            logger.warning(f"Failed to get invitations: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Error getting invitations: {e}")
        return []


def revoke_clerk_organization_invitation(
    organization_id: str,
    invitation_id: str
) -> bool:
    """
    Revoke a pending invitation.
    
    Args:
        organization_id: Clerk organization ID
        invitation_id: Invitation ID to revoke
        
    Returns:
        True if successful, False otherwise
    """
    try:
        headers = {
            "Authorization": f"Bearer {get_clerk_secret_key()}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{CLERK_API_URL}/organizations/{organization_id}/invitations/{invitation_id}/revoke",
            headers=headers
        )
        
        if response.status_code in [200, 201]:
            return True
        else:
            logger.error(f"Failed to revoke invitation: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error revoking invitation: {e}")
        return False

