"""
API Key Authentication

This module provides API key-based authentication services.
"""

import uuid
import hashlib
import time
from typing import Dict, Any, Optional, List


class APIKeyAuth:
    """API key authentication service."""
    
    def __init__(
        self, 
        header_name: str = "X-API-Key",
    ):
        """
        Initialize API key authentication service.
        
        Args:
            header_name: HTTP header name for API key.
        """
        self.header_name = header_name
        
        # In a real implementation, API keys would be stored in a database
        # For this prototype, we'll use an in-memory dictionary
        # In production, this would be replaced with a proper database backend
        self._keys: Dict[str, Dict[str, Any]] = {}
    
    def generate_key(
        self, 
        user_id: str,
        description: Optional[str] = None,
        permissions: Optional[List[str]] = None,
        expires_at: Optional[int] = None
    ) -> str:
        """
        Generate a new API key.
        
        Args:
            user_id: ID of the user the key belongs to.
            description: Optional description of the key.
            permissions: Optional list of permissions for the key.
            expires_at: Optional expiration time (Unix timestamp).
        
        Returns:
            Generated API key.
        """
        # Generate a random API key
        # In production, you would use a more secure method
        key = str(uuid.uuid4()).replace("-", "")
        
        # Store key information
        self._keys[key] = {
            "user_id": user_id,
            "created_at": int(time.time()),
            "description": description,
            "permissions": permissions or [],
            "expires_at": expires_at,
            "last_used_at": None
        }
        
        return key
    
    def revoke_key(self, key: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            key: API key to revoke.
        
        Returns:
            True if key was revoked, False if key was not found.
        """
        if key in self._keys:
            del self._keys[key]
            return True
        return False
    
    def authenticate(self, key: str) -> Dict[str, Any]:
        """
        Authenticate an API key.
        
        Args:
            key: API key to authenticate.
        
        Returns:
            User information associated with the key.
        
        Raises:
            ValueError: If key is invalid or expired.
        """
        if key not in self._keys:
            raise ValueError("Invalid API key")
        
        key_info = self._keys[key]
        
        # Check if key has expired
        if key_info.get("expires_at") and key_info["expires_at"] < time.time():
            raise ValueError("API key has expired")
        
        # Update last used timestamp
        key_info["last_used_at"] = int(time.time())
        
        # Return user information
        return {
            "user_id": key_info["user_id"],
            "permissions": key_info["permissions"],
            "key_description": key_info.get("description")
        }
    
    def get_user_keys(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all API keys for a user.
        
        Args:
            user_id: ID of the user.
        
        Returns:
            List of API key information.
        """
        return [
            {
                "key": key,
                "created_at": info["created_at"],
                "description": info.get("description"),
                "permissions": info.get("permissions", []),
                "expires_at": info.get("expires_at"),
                "last_used_at": info.get("last_used_at")
            }
            for key, info in self._keys.items()
            if info["user_id"] == user_id
        ] 