"""
Authentication Dependencies

This module provides FastAPI dependency functions for authentication and user retrieval.
"""

from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader

from .jwt import JWTAuth, TokenPayload
from .api_key import APIKeyAuth

# Security schemes
bearer_scheme = HTTPBearer()
api_key_scheme = APIKeyHeader(name="X-API-Key")


async def get_token_payload(
    auth: JWTAuth,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> TokenPayload:
    """
    Get the payload from a JWT token.
    
    Args:
        auth: The JWT authentication service.
        credentials: The HTTP Bearer credentials.
        
    Returns:
        The token payload.
        
    Raises:
        HTTPException: If authentication fails.
    """
    try:
        return auth.decode_token(credentials.credentials)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=f"Invalid authentication credentials: {str(e)}"
        )


async def get_api_key_user(
    api_key_auth: APIKeyAuth,
    api_key: str = Security(api_key_scheme)
) -> Dict[str, Any]:
    """
    Get user information from an API key.
    
    Args:
        api_key_auth: The API key authentication service.
        api_key: The API key.
        
    Returns:
        User information associated with the API key.
        
    Raises:
        HTTPException: If authentication fails.
    """
    try:
        return api_key_auth.authenticate(api_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail=f"Invalid API key: {str(e)}"
        )


async def get_current_user(
    token_payload: Optional[TokenPayload] = Depends(get_token_payload),
    api_key_user: Optional[Dict[str, Any]] = Depends(get_api_key_user)
) -> Dict[str, Any]:
    """
    Get the current authenticated user.
    
    This dependency function tries to authenticate using both JWT and API key.
    It succeeds if either authentication method succeeds.
    
    Args:
        token_payload: The JWT token payload.
        api_key_user: The user information from the API key.
        
    Returns:
        User information.
        
    Raises:
        HTTPException: If authentication fails.
    """
    # For the placeholder implementation, we'll just return the first non-None value
    # In a real implementation, we would validate the user against a database
    
    if token_payload is not None:
        # Convert TokenPayload to a dict
        return {
            "user_id": token_payload.sub,
            "email": token_payload.email,
            "role": token_payload.role,
            "auth_method": "jwt"
        }
    
    if api_key_user is not None:
        return {**api_key_user, "auth_method": "api_key"}
    
    # If both are None, that means both authentication methods failed
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    ) 