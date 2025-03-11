"""
Dashboard Authentication Module
----------------------------
Provides authentication and security features for the Instinct AI Trading Dashboard.
"""

import os
import json
import time
import logging
import hashlib
import secrets
import base64
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import jwt
from werkzeug.security import generate_password_hash, check_password_hash
import threading

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
TOKEN_EXPIRY = 24  # Hours
DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASSWORD = "instinct_admin"  # Should be changed on first login
USER_DB_PATH = Path(__file__).resolve().parent.parent / "config" / "users.json"
API_KEYS_PATH = Path(__file__).resolve().parent.parent / "config" / "api_keys.json"
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))

# Ensure config directory exists
os.makedirs(USER_DB_PATH.parent, exist_ok=True)


class AuthManager:
    """
    Authentication Manager
    
    Handles user authentication, API key management, and security for the dashboard.
    """
    
    def __init__(self):
        """Initialize the authentication manager."""
        self.users = {}
        self.api_keys = {}
        self.active_tokens = {}
        
        # Load users from storage
        self._load_users()
        
        # Load API keys from storage
        self._load_api_keys()
        
        # Ensure admin user exists
        self._ensure_admin_user()
        
        logger.info("Authentication manager initialized")
    
    def _load_users(self):
        """Load users from the JSON storage file."""
        if not USER_DB_PATH.exists():
            logger.warning(f"User database file not found: {USER_DB_PATH}")
            self.users = {}
            return
        
        try:
            with open(USER_DB_PATH, 'r') as f:
                self.users = json.load(f)
            logger.info(f"Loaded {len(self.users)} users from database")
        except Exception as e:
            logger.error(f"Error loading users: {str(e)}")
            self.users = {}
    
    def _save_users(self):
        """Save users to the JSON storage file."""
        try:
            with open(USER_DB_PATH, 'w') as f:
                json.dump(self.users, f, indent=4)
            logger.info(f"Saved {len(self.users)} users to database")
        except Exception as e:
            logger.error(f"Error saving users: {str(e)}")
    
    def _load_api_keys(self):
        """Load API keys from the JSON storage file."""
        if not API_KEYS_PATH.exists():
            logger.warning(f"API keys file not found: {API_KEYS_PATH}")
            self.api_keys = {}
            return
        
        try:
            with open(API_KEYS_PATH, 'r') as f:
                self.api_keys = json.load(f)
            logger.info(f"Loaded API keys for {len(self.api_keys)} exchanges")
        except Exception as e:
            logger.error(f"Error loading API keys: {str(e)}")
            self.api_keys = {}
    
    def _save_api_keys(self):
        """Save API keys to the JSON storage file."""
        try:
            with open(API_KEYS_PATH, 'w') as f:
                json.dump(self.api_keys, f, indent=4)
            logger.info("Saved API keys")
        except Exception as e:
            logger.error(f"Error saving API keys: {str(e)}")
    
    def _ensure_admin_user(self):
        """Ensure that an admin user exists."""
        if DEFAULT_ADMIN_USER not in self.users:
            logger.warning("Admin user not found, creating default admin account")
            self.add_user(
                username=DEFAULT_ADMIN_USER,
                password=DEFAULT_ADMIN_PASSWORD,
                role="admin",
                email="admin@example.com"
            )
    
    def authenticate(self, username: str, password: str) -> Optional[str]:
        """
        Authenticate a user with username and password.
        
        Args:
            username: User's username
            password: User's password
            
        Returns:
            JWT token if authentication successful, None otherwise
        """
        if username not in self.users:
            logger.warning(f"Authentication failed: User '{username}' not found")
            return None
        
        user = self.users[username]
        
        if not check_password_hash(user['password_hash'], password):
            logger.warning(f"Authentication failed: Invalid password for user '{username}'")
            return None
        
        # Create JWT token
        token = self._create_token(username)
        
        # Update last login time
        self.users[username]['last_login'] = datetime.now().isoformat()
        self._save_users()
        
        logger.info(f"User '{username}' authenticated successfully")
        return token
    
    def verify_token(self, token: str) -> Tuple[bool, Optional[str]]:
        """
        Verify a JWT token.
        
        Args:
            token: JWT token
            
        Returns:
            Tuple of (is_valid, username)
        """
        try:
            # Decode the token
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            
            # Check if the token has expired
            expiry = datetime.fromtimestamp(payload['exp'])
            if expiry < datetime.now():
                logger.warning(f"Token expired for user '{payload['sub']}'")
                return False, None
            
            # Check if the user exists
            if payload['sub'] not in self.users:
                logger.warning(f"Token invalid: User '{payload['sub']}' not found")
                return False, None
            
            logger.debug(f"Token valid for user '{payload['sub']}'")
            return True, payload['sub']
            
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return False, None
    
    def _create_token(self, username: str) -> str:
        """
        Create a JWT token for a user.
        
        Args:
            username: User's username
            
        Returns:
            JWT token
        """
        now = datetime.now()
        expiry = now + timedelta(hours=TOKEN_EXPIRY)
        
        payload = {
            'sub': username,
            'iat': now.timestamp(),
            'exp': expiry.timestamp(),
            'role': self.users[username].get('role', 'user')
        }
        
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        
        # Store in active tokens
        self.active_tokens[username] = {
            'token': token,
            'expiry': expiry.isoformat()
        }
        
        return token
    
    def add_user(self, username: str, password: str, role: str = "user", 
                email: Optional[str] = None) -> bool:
        """
        Add a new user.
        
        Args:
            username: User's username
            password: User's password
            role: User's role (admin or user)
            email: User's email address
            
        Returns:
            True if user added successfully, False otherwise
        """
        if username in self.users:
            logger.warning(f"User '{username}' already exists")
            return False
        
        # Create password hash
        password_hash = generate_password_hash(password)
        
        # Create user record
        self.users[username] = {
            'username': username,
            'password_hash': password_hash,
            'role': role,
            'email': email,
            'created_at': datetime.now().isoformat(),
            'last_login': None
        }
        
        # Save users
        self._save_users()
        
        logger.info(f"User '{username}' added successfully with role '{role}'")
        return True
    
    def update_user(self, username: str, **kwargs) -> bool:
        """
        Update a user's details.
        
        Args:
            username: User's username
            **kwargs: Fields to update
            
        Returns:
            True if user updated successfully, False otherwise
        """
        if username not in self.users:
            logger.warning(f"User '{username}' not found")
            return False
        
        user = self.users[username]
        
        # Update fields
        for field, value in kwargs.items():
            if field == 'password':
                # Handle password separately
                user['password_hash'] = generate_password_hash(value)
            elif field in ['username', 'password_hash', 'created_at']:
                # Don't allow these fields to be updated
                continue
            else:
                user[field] = value
        
        # Save users
        self._save_users()
        
        logger.info(f"User '{username}' updated successfully")
        return True
    
    def delete_user(self, username: str) -> bool:
        """
        Delete a user.
        
        Args:
            username: User's username
            
        Returns:
            True if user deleted successfully, False otherwise
        """
        if username not in self.users:
            logger.warning(f"User '{username}' not found")
            return False
        
        # Don't allow deleting the last admin
        if self.users[username].get('role') == 'admin':
            admin_count = sum(1 for user in self.users.values() if user.get('role') == 'admin')
            if admin_count <= 1:
                logger.warning(f"Cannot delete user '{username}': last admin user")
                return False
        
        # Delete user
        del self.users[username]
        
        # Invalidate any active tokens
        if username in self.active_tokens:
            del self.active_tokens[username]
        
        # Save users
        self._save_users()
        
        logger.info(f"User '{username}' deleted successfully")
        return True
    
    def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get a user's information.
        
        Args:
            username: User's username
            
        Returns:
            User information dict, or None if user not found
        """
        if username not in self.users:
            logger.warning(f"User '{username}' not found")
            return None
        
        # Return user info without password hash
        user_info = self.users[username].copy()
        del user_info['password_hash']
        
        return user_info
    
    def list_users(self) -> List[Dict[str, Any]]:
        """
        List all users.
        
        Returns:
            List of user information dicts
        """
        # Return users without password hashes
        users_list = []
        for username, user in self.users.items():
            user_info = user.copy()
            del user_info['password_hash']
            users_list.append(user_info)
        
        return users_list
    
    def change_password(self, username: str, current_password: str, new_password: str) -> bool:
        """
        Change a user's password.
        
        Args:
            username: User's username
            current_password: User's current password
            new_password: User's new password
            
        Returns:
            True if password changed successfully, False otherwise
        """
        if username not in self.users:
            logger.warning(f"User '{username}' not found")
            return False
        
        user = self.users[username]
        
        # Check current password
        if not check_password_hash(user['password_hash'], current_password):
            logger.warning(f"Password change failed: Invalid current password for user '{username}'")
            return False
        
        # Update password
        user['password_hash'] = generate_password_hash(new_password)
        
        # Save users
        self._save_users()
        
        # Invalidate any active tokens
        if username in self.active_tokens:
            del self.active_tokens[username]
        
        logger.info(f"Password changed successfully for user '{username}'")
        return True
    
    def add_api_key(self, exchange: str, api_key: str, api_secret: str, 
                  description: Optional[str] = None) -> bool:
        """
        Add or update an API key for an exchange.
        
        Args:
            exchange: Exchange name
            api_key: API key
            api_secret: API secret
            description: Optional description
            
        Returns:
            True if API key added successfully, False otherwise
        """
        # Encrypt the API secret
        encrypted_secret = self._encrypt_secret(api_secret)
        
        # Add to API keys
        self.api_keys[exchange] = {
            'api_key': api_key,
            'api_secret_encrypted': encrypted_secret,
            'description': description,
            'added_at': datetime.now().isoformat(),
            'last_used': None
        }
        
        # Save API keys
        self._save_api_keys()
        
        logger.info(f"API key for '{exchange}' added successfully")
        return True
    
    def get_api_key(self, exchange: str) -> Optional[Tuple[str, str]]:
        """
        Get API key and secret for an exchange.
        
        Args:
            exchange: Exchange name
            
        Returns:
            Tuple of (api_key, api_secret), or None if not found
        """
        if exchange not in self.api_keys:
            logger.warning(f"API key for '{exchange}' not found")
            return None
        
        api_key_info = self.api_keys[exchange]
        
        # Decrypt the API secret
        api_secret = self._decrypt_secret(api_key_info['api_secret_encrypted'])
        
        # Update last used time
        api_key_info['last_used'] = datetime.now().isoformat()
        self._save_api_keys()
        
        return (api_key_info['api_key'], api_secret)
    
    def list_api_keys(self) -> Dict[str, Dict[str, Any]]:
        """
        List all API keys.
        
        Returns:
            Dict of API key information by exchange
        """
        # Return API keys without secrets
        api_keys_list = {}
        for exchange, api_key_info in self.api_keys.items():
            info = api_key_info.copy()
            del info['api_secret_encrypted']
            api_keys_list[exchange] = info
        
        return api_keys_list
    
    def delete_api_key(self, exchange: str) -> bool:
        """
        Delete an API key.
        
        Args:
            exchange: Exchange name
            
        Returns:
            True if API key deleted successfully, False otherwise
        """
        if exchange not in self.api_keys:
            logger.warning(f"API key for '{exchange}' not found")
            return False
        
        # Delete API key
        del self.api_keys[exchange]
        
        # Save API keys
        self._save_api_keys()
        
        logger.info(f"API key for '{exchange}' deleted successfully")
        return True
    
    def _encrypt_secret(self, secret: str) -> str:
        """
        Encrypt an API secret.
        
        Args:
            secret: Plain text secret
            
        Returns:
            Encrypted secret
        """
        # This is a simple implementation for demonstration
        # In production, use proper encryption libraries
        key = hashlib.sha256(JWT_SECRET.encode()).digest()
        encoded = base64.b64encode(secret.encode())
        return base64.b64encode(encoded + key[:16]).decode()
    
    def _decrypt_secret(self, encrypted_secret: str) -> str:
        """
        Decrypt an API secret.
        
        Args:
            encrypted_secret: Encrypted secret
            
        Returns:
            Plain text secret
        """
        # This is a simple implementation for demonstration
        # In production, use proper encryption libraries
        key = hashlib.sha256(JWT_SECRET.encode()).digest()
        decoded = base64.b64decode(encrypted_secret)
        encoded = decoded[:-16]
        return base64.b64decode(encoded).decode()
    
    def invalidate_token(self, username: str) -> bool:
        """
        Invalidate a user's active token.
        
        Args:
            username: User's username
            
        Returns:
            True if token invalidated successfully, False otherwise
        """
        if username not in self.active_tokens:
            logger.warning(f"No active token for user '{username}'")
            return False
        
        # Delete the token
        del self.active_tokens[username]
        
        logger.info(f"Token invalidated for user '{username}'")
        return True
    
    def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired tokens.
        
        Returns:
            Number of tokens cleaned up
        """
        now = datetime.now()
        expired_tokens = []
        
        for username, token_info in self.active_tokens.items():
            expiry = datetime.fromisoformat(token_info['expiry'])
            if expiry < now:
                expired_tokens.append(username)
        
        # Remove expired tokens
        for username in expired_tokens:
            del self.active_tokens[username]
        
        logger.info(f"Cleaned up {len(expired_tokens)} expired tokens")
        return len(expired_tokens)

# Global auth manager instance
_auth_manager = None
_auth_lock = threading.Lock()

def get_auth_manager() -> AuthManager:
    """
    Get or initialize the authentication manager instance.
    
    Returns:
        AuthManager instance
    """
    global _auth_manager
    
    with _auth_lock:
        if _auth_manager is None:
            logger.info("Initializing AuthManager...")
            _auth_manager = AuthManager()
            logger.info("AuthManager initialized successfully")
    
    return _auth_manager 