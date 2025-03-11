"""
JWT Authentication

This module provides JWT-based authentication services.
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

import jwt


@dataclass
class TokenPayload:
    """JWT token payload."""
    sub: str  # Subject (usually user ID)
    exp: int  # Expiration time
    iat: int  # Issued at
    email: Optional[str] = None
    role: Optional[str] = None
    additional_claims: Dict[str, Any] = None


class JWTAuth:
    """JWT authentication service."""
    
    def __init__(
        self, 
        secret_key: str,
        algorithm: str = "HS256",
        token_expiration: int = 3600
    ):
        """
        Initialize JWT authentication service.
        
        Args:
            secret_key: Secret key for JWT token signing.
            algorithm: Algorithm to use for JWT token signing.
            token_expiration: Token expiration time in seconds.
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_expiration = token_expiration
    
    def create_token(
        self, 
        subject: str,
        email: Optional[str] = None,
        role: Optional[str] = None,
        additional_claims: Optional[Dict[str, Any]] = None,
        expires_delta: Optional[int] = None
    ) -> str:
        """
        Create a JWT token.
        
        Args:
            subject: Subject of the token (usually user ID).
            email: User's email.
            role: User's role.
            additional_claims: Additional claims to include in the token.
            expires_delta: Token expiration time in seconds. If None, uses default.
        
        Returns:
            JWT token string.
        """
        if expires_delta is None:
            expires_delta = self.token_expiration
        
        issued_at = int(time.time())
        expiration = issued_at + expires_delta
        
        payload = {
            "sub": subject,
            "iat": issued_at,
            "exp": expiration
        }
        
        if email is not None:
            payload["email"] = email
        
        if role is not None:
            payload["role"] = role
        
        if additional_claims is not None:
            payload.update(additional_claims)
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def decode_token(self, token: str) -> TokenPayload:
        """
        Decode and verify a JWT token.
        
        Args:
            token: JWT token string.
        
        Returns:
            Token payload.
        
        Raises:
            jwt.PyJWTError: If token is invalid or expired.
        """
        payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        
        return TokenPayload(
            sub=payload["sub"],
            exp=payload["exp"],
            iat=payload["iat"],
            email=payload.get("email"),
            role=payload.get("role"),
            additional_claims={
                k: v for k, v in payload.items() 
                if k not in ["sub", "exp", "iat", "email", "role"]
            }
        )
    
    def refresh_token(self, token: str) -> str:
        """
        Refresh an existing token.
        
        Args:
            token: Existing JWT token.
        
        Returns:
            New JWT token.
        
        Raises:
            jwt.PyJWTError: If token is invalid or expired.
        """
        payload = self.decode_token(token)
        
        return self.create_token(
            subject=payload.sub,
            email=payload.email,
            role=payload.role,
            additional_claims=payload.additional_claims
        ) 