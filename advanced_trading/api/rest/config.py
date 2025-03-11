"""
API Configuration

This module provides configuration classes for the Instinct AI API.
These configurations can be loaded from environment variables,
configuration files, or directly set in code.
"""

import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from pydantic import BaseSettings, Field


@dataclass
class AuthConfig:
    """Authentication configuration."""
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expiration: int = 3600  # 1 hour
    api_key_header: str = "X-API-Key"
    

@dataclass
class CORSConfig:
    """CORS configuration."""
    allow_origins: List[str] = field(default_factory=lambda: ["*"])
    allow_credentials: bool = True
    allow_methods: List[str] = field(default_factory=lambda: ["*"])
    allow_headers: List[str] = field(default_factory=lambda: ["*"])


@dataclass
class APIConfig:
    """API configuration."""
    debug: bool = False
    docs_url: str = "/docs"
    redoc_url: str = "/redoc"
    openapi_url: str = "/openapi.json"
    openapi_prefix: str = ""
    title: str = "Instinct AI API"
    description: str = "API for the Instinct AI trading platform"
    version: str = "1.0.0"
    auth: AuthConfig = field(default_factory=AuthConfig)
    cors: CORSConfig = field(default_factory=CORSConfig)
    
    @classmethod
    def from_env(cls) -> "APIConfig":
        """Create a configuration from environment variables."""
        config = cls()
        
        # Set debug mode
        if os.environ.get("DEBUG", "").lower() in ("true", "1", "yes"):
            config.debug = True
        
        # Set API info
        config.title = os.environ.get("API_TITLE", config.title)
        config.description = os.environ.get("API_DESCRIPTION", config.description)
        config.version = os.environ.get("API_VERSION", config.version)
        
        # Set JWT config
        config.auth.jwt_secret = os.environ.get("JWT_SECRET", config.auth.jwt_secret)
        config.auth.jwt_algorithm = os.environ.get("JWT_ALGORITHM", config.auth.jwt_algorithm)
        if jwt_exp := os.environ.get("JWT_EXPIRATION"):
            config.auth.jwt_expiration = int(jwt_exp)
        
        # Set CORS config
        if origins := os.environ.get("CORS_ORIGINS"):
            config.cors.allow_origins = origins.split(",")
        if methods := os.environ.get("CORS_METHODS"):
            config.cors.allow_methods = methods.split(",")
        if headers := os.environ.get("CORS_HEADERS"):
            config.cors.allow_headers = headers.split(",")
        
        if os.environ.get("CORS_CREDENTIALS", "").lower() in ("false", "0", "no"):
            config.cors.allow_credentials = False
        
        return config 