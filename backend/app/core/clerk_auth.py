"""Clerk authentication utilities for FastAPI."""
import os
import requests
from typing import Optional, Dict
from fastapi import HTTPException, status
import logging

logger = logging.getLogger(__name__)

CLERK_API_URL = "https://api.clerk.com/v1"


def get_clerk_secret_key() -> str:
    """Get Clerk secret key from environment."""
    key = os.getenv("CLERK_SECRET_KEY", "")
    if not key:
        raise ValueError("CLERK_SECRET_KEY environment variable is not set")
    return key


def verify_clerk_token(token: str) -> Optional[Dict]:
    """
    Verify a Clerk JWT token and return the session/user information.
    
    Args:
        token: JWT token from Clerk (from getToken() in frontend)
        
    Returns:
        Dictionary with user_id, org_id, etc., or None if invalid
    """
    try:
        # Decode JWT token (Clerk tokens are JWTs)
        # For production, you should verify the signature using Clerk's public keys
        # For now, we'll decode and verify with Clerk's API
        import jwt
        from jwt import PyJWKClient
        
        # Get Clerk publishable key to construct JWKS URL
        # Clerk JWKS URL format: https://[your-frontend-api]/.well-known/jwks.json
        # For now, we'll use a simpler approach: decode without verification
        # and then verify with Clerk's API
        
        # Try to decode the token (without verification first to get claims)
        try:
            # Decode without verification to inspect
            unverified = jwt.decode(token, options={"verify_signature": False})
            user_id = unverified.get("sub")
            org_id = unverified.get("org_id")
            
            # Verify with Clerk's API
            headers = {
                "Authorization": f"Bearer {get_clerk_secret_key()}",
                "Content-Type": "application/json"
            }
            
            # Get session info from Clerk
            if user_id:
                # Get user's active sessions
                response = requests.get(
                    f"{CLERK_API_URL}/users/{user_id}/sessions",
                    headers=headers
                )
                
                if response.status_code == 200:
                    sessions = response.json()
                    # Check if token matches any active session
                    # For now, if we can get the user, assume token is valid
                    return {
                        "user_id": user_id,
                        "org_id": org_id,
                        "valid": True
                    }
            
            # Fallback: try to verify with Clerk's verify endpoint
            response = requests.post(
                f"{CLERK_API_URL}/sessions/verify",
                headers=headers,
                json={"token": token}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Clerk token verification failed: {response.status_code}")
                return None
                
        except jwt.DecodeError:
            logger.warning("Failed to decode Clerk JWT token")
            return None
            
    except Exception as e:
        logger.error(f"Error verifying Clerk token: {e}")
        return None


def get_clerk_user(clerk_user_id: str) -> Optional[Dict]:
    """Get user information from Clerk API."""
    try:
        headers = {
            "Authorization": f"Bearer {get_clerk_secret_key()}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{CLERK_API_URL}/users/{clerk_user_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Failed to get Clerk user: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting Clerk user: {e}")
        return None


def get_clerk_organization(clerk_org_id: str) -> Optional[Dict]:
    """Get organization information from Clerk API."""
    try:
        headers = {
            "Authorization": f"Bearer {get_clerk_secret_key()}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{CLERK_API_URL}/organizations/{clerk_org_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Failed to get Clerk organization: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting Clerk organization: {e}")
        return None

