"""
Authentication Client

This module provides a client for the authentication API.
"""

from typing import Dict, Any, Optional, List


class AuthClient:
    """Authentication API client."""
    
    def __init__(self, api_client):
        """
        Initialize authentication client.
        
        Args:
            api_client: API client.
        """
        self.api_client = api_client
    
    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Log in with username and password.
        
        Args:
            username: Username or email.
            password: Password.
        
        Returns:
            Authentication response with token and user information.
        """
        data = {
            "username": username,
            "password": password
        }
        
        response = self.api_client.post("auth/login", data=data)
        
        # Update API client token
        if "access_token" in response:
            self.api_client.token = response["access_token"]
        
        return response
    
    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        scopes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a new user.
        
        Args:
            username: Username.
            email: Email address.
            password: Password.
            scopes: Permission scopes.
        
        Returns:
            Created user information.
        """
        data = {
            "username": username,
            "email": email,
            "password": password,
            "scopes": scopes or ["read"]
        }
        
        return self.api_client.post("auth/users", data=data)
    
    def get_current_user(self) -> Dict[str, Any]:
        """
        Get information about the currently authenticated user.
        
        Returns:
            Current user information.
        """
        return self.api_client.get("auth/me")
    
    def create_api_key(self, user_id: str) -> Dict[str, Any]:
        """
        Create a new API key.
        
        Args:
            user_id: User ID to create an API key for.
        
        Returns:
            Created API key.
        """
        data = {"user_id": user_id}
        
        response = self.api_client.post("auth/api-keys", data=data)
        
        # Update API client API key if requested for current user
        current_user = self.get_current_user()
        if "api_key" in response and current_user.get("id") == user_id:
            self.api_client.api_key = response["api_key"]
        
        return response
    
    def revoke_api_key(self, api_key: str) -> None:
        """
        Revoke an API key.
        
        Args:
            api_key: API key to revoke.
        """
        self.api_client.delete(f"auth/api-keys/{api_key}")
        
        # Clear API client API key if it matches the revoked key
        if self.api_client.api_key == api_key:
            self.api_client.api_key = None 