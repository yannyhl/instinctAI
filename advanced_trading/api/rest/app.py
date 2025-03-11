"""
FastAPI Application

This module provides the FastAPI application factory for the Instinct AI API.
"""

import logging
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi

from .config import APIConfig
from .routes import api_router

logger = logging.getLogger("advanced_trading.api.rest")


def create_app(config: APIConfig) -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Args:
        config: The API configuration.
        
    Returns:
        The configured FastAPI application.
    """
    app = FastAPI(
        title=config.title,
        description=config.description,
        version=config.version,
        docs_url=config.docs_url,
        redoc_url=config.redoc_url,
        openapi_url=config.openapi_url,
        openapi_prefix=config.openapi_prefix,
        debug=config.debug,
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors.allow_origins,
        allow_credentials=config.cors.allow_credentials,
        allow_methods=config.cors.allow_methods,
        allow_headers=config.cors.allow_headers,
    )
    
    # Register exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Handle HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle general exceptions."""
        logger.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
    
    # Add health check endpoint
    @app.get("/health", tags=["health"])
    async def health_check() -> Dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok"}
    
    # Include the API router
    app.include_router(api_router)
    
    # Customize OpenAPI schema
    def custom_openapi() -> Dict[str, Any]:
        """Generate custom OpenAPI schema."""
        if app.openapi_schema:
            return app.openapi_schema
        
        openapi_schema = get_openapi(
            title=config.title,
            version=config.version,
            description=config.description,
            routes=app.routes,
        )
        
        # Add security schemes
        openapi_schema["components"] = openapi_schema.get("components", {})
        openapi_schema["components"]["securitySchemes"] = {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            },
            "apiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": config.auth.api_key_header,
            },
        }
        
        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    app.openapi = custom_openapi
    
    return app 