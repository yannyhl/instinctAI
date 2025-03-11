"""
User Management

This module provides user management functionality for the API.
"""

import uuid
import secrets
import hashlib
from typing import Dict, Any, List, Optional, Set

class User:
    """
    User model representing an API user.
    
    Attributes:
        id: Unique user identifier
        username: User's username
        email: User's email address
        password_hash: Hashed password
        scopes: List of permission scopes
        api_keys: List of API keys
        is_active: Whether the user is active
        metadata: Additional user metadata
    """
    
    def __init__(self, 
               username: str, 
               email: str, 
               password: str,
               scopes: Optional[List[str]] = None):
        """
        Initialize a new user.
        
        Args:
            username: User's username
            email: User's email address
            password: User's password (will be hashed)
            scopes: Permission scopes
        """
        self.id = str(uuid.uuid4())
        self.username = username
        self.email = email
        self.password_hash = self._hash_password(password)
        self.scopes = set(scopes or ["read"])
        self.api_keys: List[str] = []
        self.is_active = True
        self.metadata: Dict[str, Any] = {}
    
    def _hash_password(self, password: str) -> str:
        """
        Hash a password using SHA-256.
        
        In a production system, use a proper password hashing library like bcrypt or Argon2.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password: str) -> bool:
        """
        Verify a password against the stored hash.
        
        Args:
            password: Plain text password to verify
            
        Returns:
            True if password matches, False otherwise
        """
        return self._hash_password(password) == self.password_hash
    
    def change_password(self, new_password: str) -> None:
        """
        Change user's password.
        
        Args:
            new_password: New password to set
        """
        self.password_hash = self._hash_password(new_password)
    
    def generate_api_key(self) -> str:
        """
        Generate a new API key for the user.
        
        Returns:
            Newly generated API key
        """
        api_key = secrets.token_urlsafe(32)
        self.api_keys.append(api_key)
        return api_key
    
    def revoke_api_key(self, api_key: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            api_key: API key to revoke
            
        Returns:
            True if key was found and revoked, False otherwise
        """
        if api_key in self.api_keys:
            self.api_keys.remove(api_key)
            return True
        return False
    
    def to_dict(self, include_secrets: bool = False) -> Dict[str, Any]:
        """
        Convert user to dictionary representation.
        
        Args:
            include_secrets: Whether to include sensitive information
            
        Returns:
            Dictionary representation of user
        """
        user_dict = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "scopes": list(self.scopes),
            "is_active": self.is_active,
            "metadata": self.metadata,
        }
        
        if include_secrets:
            user_dict["password_hash"] = self.password_hash
            user_dict["api_keys"] = self.api_keys
        
        return user_dict


class UserManager:
    """
    Manages API users and their authentication.
    
    In a real implementation, this would use a database for persistence.
    """
    
    def __init__(self):
        """Initialize the user manager."""
        self.users_by_id: Dict[str, User] = {}
        self.users_by_username: Dict[str, User] = {}
        self.users_by_email: Dict[str, User] = {}
        self.api_keys: Dict[str, str] = {}  # Maps API keys to user IDs
    
    def create_user(self, 
                  username: str, 
                  email: str, 
                  password: str,
                  scopes: Optional[List[str]] = None) -> User:
        """
        Create a new user.
        
        Args:
            username: User's username
            email: User's email address
            password: User's password
            scopes: Permission scopes
            
        Returns:
            Created user
            
        Raises:
            ValueError: If username or email already exists
        """
        if username in self.users_by_username:
            raise ValueError(f"Username '{username}' already exists")
        
        if email in self.users_by_email:
            raise ValueError(f"Email '{email}' already exists")
        
        user = User(
            username=username,
            email=email,
            password=password,
            scopes=scopes
        )
        
        self.users_by_id[user.id] = user
        self.users_by_username[user.username] = user
        self.users_by_email[user.email] = user
        
        return user
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        Get a user by ID.
        
        Args:
            user_id: User ID to look up
            
        Returns:
            User if found, None otherwise
        """
        return self.users_by_id.get(user_id)
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Get a user by username.
        
        Args:
            username: Username to look up
            
        Returns:
            User if found, None otherwise
        """
        return self.users_by_username.get(username)
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get a user by email.
        
        Args:
            email: Email to look up
            
        Returns:
            User if found, None otherwise
        """
        return self.users_by_email.get(email)
    
    def authenticate(self, username: str, password: str) -> Optional[User]:
        """
        Authenticate a user with username/password.
        
        Args:
            username: Username
            password: Password
            
        Returns:
            User if authentication successful, None otherwise
        """
        user = self.get_user_by_username(username)
        
        if user and user.is_active and user.verify_password(password):
            return user
        
        return None
    
    def generate_api_key(self, user_id: str) -> Optional[str]:
        """
        Generate a new API key for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Generated API key, or None if user not found
        """
        user = self.get_user_by_id(user_id)
        
        if not user:
            return None
        
        api_key = user.generate_api_key()
        self.api_keys[api_key] = user.id
        
        return api_key
    
    def get_user_by_api_key(self, api_key: str) -> Optional[User]:
        """
        Get a user by API key.
        
        Args:
            api_key: API key to look up
            
        Returns:
            User if found, None otherwise
        """
        user_id = self.api_keys.get(api_key)
        
        if not user_id:
            return None
        
        return self.get_user_by_id(user_id)
    
    def revoke_api_key(self, api_key: str) -> bool:
        """
        Revoke an API key.
        
        Args:
            api_key: API key to revoke
            
        Returns:
            True if key was revoked, False otherwise
        """
        user_id = self.api_keys.get(api_key)
        
        if not user_id:
            return False
        
        user = self.get_user_by_id(user_id)
        
        if not user:
            return False
        
        if user.revoke_api_key(api_key):
            del self.api_keys[api_key]
            return True
        
        return False
    
    def update_user(self, 
                  user_id: str, 
                  username: Optional[str] = None,
                  email: Optional[str] = None,
                  password: Optional[str] = None,
                  scopes: Optional[List[str]] = None,
                  is_active: Optional[bool] = None,
                  metadata: Optional[Dict[str, Any]] = None) -> Optional[User]:
        """
        Update a user's information.
        
        Args:
            user_id: User ID
            username: New username
            email: New email
            password: New password
            scopes: New scopes
            is_active: New active status
            metadata: New metadata
            
        Returns:
            Updated user, or None if user not found
            
        Raises:
            ValueError: If username or email already exists
        """
        user = self.get_user_by_id(user_id)
        
        if not user:
            return None
        
        if username and username != user.username:
            if username in self.users_by_username:
                raise ValueError(f"Username '{username}' already exists")
            
            del self.users_by_username[user.username]
            user.username = username
            self.users_by_username[username] = user
        
        if email and email != user.email:
            if email in self.users_by_email:
                raise ValueError(f"Email '{email}' already exists")
            
            del self.users_by_email[user.email]
            user.email = email
            self.users_by_email[email] = user
        
        if password:
            user.change_password(password)
        
        if scopes is not None:
            user.scopes = set(scopes)
        
        if is_active is not None:
            user.is_active = is_active
        
        if metadata is not None:
            user.metadata = metadata
        
        return user
    
    def delete_user(self, user_id: str) -> bool:
        """
        Delete a user.
        
        Args:
            user_id: User ID
            
        Returns:
            True if user was deleted, False otherwise
        """
        user = self.get_user_by_id(user_id)
        
        if not user:
            return False
        
        # Remove from lookup dictionaries
        del self.users_by_id[user.id]
        del self.users_by_username[user.username]
        del self.users_by_email[user.email]
        
        # Remove API keys
        for api_key in user.api_keys:
            if api_key in self.api_keys:
                del self.api_keys[api_key]
        
        return True 