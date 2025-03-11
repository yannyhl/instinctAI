"""
Authentication Router

This module provides API endpoints for user authentication and management.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from pydantic import BaseModel, Field, EmailStr

from ...auth.jwt import JWTAuth
from ...auth.api_key import APIKeyAuth

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)


# --- Models ---

class LoginRequest(BaseModel):
    """Login request model."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    scopes: List[str] = Field(..., description="Permission scopes")


class CreateUserRequest(BaseModel):
    """Create user request model."""
    username: str = Field(..., description="Username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., description="Password")
    scopes: Optional[List[str]] = Field(default=["read"], description="Permission scopes")


class UserResponse(BaseModel):
    """User response model."""
    id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: EmailStr = Field(..., description="Email address")
    scopes: List[str] = Field(..., description="Permission scopes")
    is_active: bool = Field(..., description="Whether the user is active")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class ApiKeyResponse(BaseModel):
    """API key response model."""
    api_key: str = Field(..., description="API key")
    user_id: str = Field(..., description="User ID")


# --- Endpoints ---

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, jwt_auth: JWTAuth = Depends()):
    """
    Authenticate a user and issue a JWT token.
    
    This endpoint authenticates a user with username/email and password
    and returns a JWT token for subsequent authenticated requests.
    """
    # Placeholder implementation
    # In a real implementation, this would validate credentials against a database
    # and return a JWT token for the authenticated user
    
    # Mock authentication - in production, this would check credentials in a database
    if request.username == "test" and request.password == "password":
        # Create a token
        token = jwt_auth.create_token(
            subject="user-123",
            email="test@example.com",
            role="user",
            additional_claims={
                "username": "test",
                "scopes": ["read", "write"]
            }
        )
        
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=jwt_auth.token_expiration,
            user_id="user-123",
            username="test",
            scopes=["read", "write"]
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(request: CreateUserRequest):
    """
    Create a new user.
    
    This endpoint creates a new user with the provided details.
    In a production system, this would often be restricted to administrators.
    """
    # Placeholder implementation
    # In a real implementation, this would create a user in the database
    
    import uuid
    from datetime import datetime
    
    # Check if username or email already exists
    if request.username == "test":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists"
        )
    
    # Create a new user
    user_id = str(uuid.uuid4())
    now = datetime.now()
    
    # In a real implementation, the password would be hashed
    
    # Return the created user
    return UserResponse(
        id=user_id,
        username=request.username,
        email=request.email,
        scopes=request.scopes,
        is_active=True,
        created_at=now,
        updated_at=now
    )


@router.post("/api-keys", response_model=ApiKeyResponse)
async def create_api_key(api_key_auth: APIKeyAuth = Depends(), user_id: str = Body(..., embed=True)):
    """
    Generate a new API key for a user.
    
    This endpoint creates a new API key for the specified user.
    """
    # Placeholder implementation
    # In a real implementation, this would generate and store an API key for the user
    
    # Generate a new API key
    api_key = api_key_auth.generate_key(
        user_id=user_id,
        description="Generated via API",
        permissions=["read", "write"]
    )
    
    return ApiKeyResponse(
        api_key=api_key,
        user_id=user_id
    )


@router.delete("/api-keys/{api_key}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(api_key: str, api_key_auth: APIKeyAuth = Depends()):
    """
    Revoke an API key.
    
    This endpoint revokes (deletes) an existing API key.
    """
    # Placeholder implementation
    # In a real implementation, this would revoke the API key in the database
    
    result = api_key_auth.revoke_key(api_key)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    # No content response
    return None


@router.get("/me", response_model=UserResponse)
async def get_current_user(user: Dict[str, Any] = Depends()):
    """
    Get information about the currently authenticated user.
    
    This endpoint returns information about the user making the request,
    based on their authentication credentials.
    """
    # Placeholder implementation
    # In a real implementation, this would return the authenticated user from the database
    
    # Create a mock user based on authentication
    return UserResponse(
        id=user.get("user_id", "user-123"),
        username=user.get("username", "test"),
        email=user.get("email", "test@example.com"),
        scopes=user.get("scopes", ["read", "write"]),
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now()
    ) 