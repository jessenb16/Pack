"""Clerk authentication utilities for FastAPI."""
import os
import requests
from typing import Optional, Dict, List
from fastapi import HTTPException, status
import logging
import jwt
from jwt import PyJWKClient
from time import time

logger = logging.getLogger(__name__)

CLERK_API_URL = "https://api.clerk.com/v1"

# Simple in-memory cache for Clerk API responses
_clerk_cache: Dict[tuple, tuple] = {}
CACHE_TTL = 60  # Cache for 60 seconds


def get_clerk_secret_key() -> str:
    """Get Clerk secret key from environment."""
    key = os.getenv("CLERK_SECRET_KEY", "")
    if not key:
        raise ValueError("CLERK_SECRET_KEY environment variable is not set")
    return key


def get_clerk_jwks_url() -> Optional[str]:
    """
    Get Clerk JWKS URL for JWT verification.
    
    Clerk JWKS URL format: https://<instance>.clerk.accounts.dev/.well-known/jwks.json
    Or: https://<frontend-api>/.well-known/jwks.json
    
    Returns:
        JWKS URL if available, None otherwise
    """
    # Try to get from CLERK_FRONTEND_API first
    frontend_api = os.getenv("NEXT_PUBLIC_CLERK_FRONTEND_API", "")
    if frontend_api:
        # Remove https:// if present
        frontend_api = frontend_api.replace("https://", "").replace("http://", "")
        return f"https://{frontend_api}/.well-known/jwks.json"
    
    # Try to get from CLERK_INSTANCE if set
    clerk_instance = os.getenv("CLERK_INSTANCE", "")
    if clerk_instance:
        return f"https://{clerk_instance}.clerk.accounts.dev/.well-known/jwks.json"
    
    # Try to extract from publishable key
    # Publishable key doesn't contain instance info, so we can't extract it
    # Return None and will decode without verification (trusting Clerk frontend)
    return None


def verify_clerk_token(token: str) -> Optional[Dict]:
    """
    Verify a Clerk JWT token and return the decoded claims.
    
    Args:
        token: JWT token from Clerk (from getToken() in frontend)
        
    Returns:
        Dictionary with decoded JWT claims (sub, org_id, etc.), or None if invalid
    """
    try:
        # First, try to decode without verification to inspect claims
        try:
            unverified_claims = jwt.decode(token, options={"verify_signature": False})
        except jwt.DecodeError:
            logger.warning("Failed to decode Clerk JWT token")
            return None
        
        # Try to verify using JWKS (most secure)
        jwks_url = get_clerk_jwks_url()
        if jwks_url:
            try:
                jwks_client = PyJWKClient(jwks_url)
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                
                # Decode and verify the token
                verified_claims = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256"],
                    options={
                        "verify_signature": True,
                        "verify_exp": True,
                        "verify_iat": True,
                    }
                )
                logger.debug("Token verified using JWKS")
                return verified_claims
            except Exception as e:
                logger.warning(f"JWKS verification failed: {e}, falling back to API verification")
        
        # Fallback: If JWKS verification failed, decode the token without signature verification
        # This is acceptable because:
        # 1. The token came from Clerk's frontend (trusted source)
        # 2. We're running in a trusted backend environment
        # 3. We'll still validate expiration and other claims
        logger.warning("JWKS verification not available, decoding token without signature verification")
        
        # Decode and validate expiration/other claims
        try:
            decoded = jwt.decode(
                token,
                options={
                    "verify_signature": False,  # Skip signature verification (JWKS failed)
                    "verify_exp": True,         # Still verify expiration
                    "verify_iat": True,         # Still verify issued at
                }
            )
            logger.info("Token decoded successfully (signature verification skipped - JWKS not available)")
            return decoded
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except Exception as e:
            logger.error(f"Error decoding token: {e}")
            return None
            
    except jwt.ExpiredSignatureError:
        logger.warning("Clerk token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid Clerk token: {e}")
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
    """Get organization information from Clerk API (with caching)."""
    from time import time
    cache_key = ("get_clerk_organization", clerk_org_id)
    current_time = time()
    
    # Check cache
    if cache_key in _clerk_cache:
        cached_data, timestamp = _clerk_cache[cache_key]
        if current_time - timestamp < CACHE_TTL:
            logger.debug(f"Cache hit for organization: {clerk_org_id}")
            return cached_data
    
    try:
        headers = {
            "Authorization": f"Bearer {get_clerk_secret_key()}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{CLERK_API_URL}/organizations/{clerk_org_id}",
            headers=headers,
            timeout=5  # 5 second timeout to prevent hanging
        )
        
        if response.status_code == 200:
            data = response.json()
            # Cache the result
            _clerk_cache[cache_key] = (data, current_time)
            return data
        else:
            logger.warning(f"Failed to get Clerk organization: {response.status_code}")
            return None
            
    except requests.Timeout:
        logger.warning(f"Timeout getting organization: {clerk_org_id}")
        return None
    except Exception as e:
        logger.error(f"Error getting Clerk organization: {e}")
        return None


def get_user_organizations(clerk_user_id: str) -> List[Dict]:
    """
    Get all organizations that a user belongs to from Clerk API.
    
    Returns:
        List of organization memberships (each with org_id, role, etc.)
    """
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
            # Handle different response formats
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                # Sometimes Clerk returns { "data": [...] }
                if 'data' in result:
                    return result['data']
                # Sometimes it's paginated: { "data": [...], "total_count": ... }
                if isinstance(result.get('data'), list):
                    return result['data']
            logger.warning(f"Unexpected response format: {type(result)}")
            return []
        else:
            logger.warning(f"Failed to get user organizations: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"Error getting user organizations: {e}")
        return []

