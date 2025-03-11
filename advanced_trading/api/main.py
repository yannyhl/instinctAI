"""
API Entry Point

This module provides the entry point for the Instinct AI API.
"""

import os
import logging
import asyncio
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends

from .rest.app import create_app
from .rest.config import APIConfig
from .websocket.server import WebSocketServer
from .websocket.handlers import WebSocketHandler, get_websocket_handler
from .auth.jwt import JWTAuth
from .auth.api_key import APIKeyAuth
from .version import API_VERSION, get_version_info

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("advanced_trading.api")

# Load configuration
config = APIConfig.from_env()

# Create API components
websocket_server = WebSocketServer()
jwt_auth = JWTAuth(
    secret_key=config.auth.jwt_secret or "insecure-secret-key",  # Default for development
    algorithm=config.auth.jwt_algorithm,
    token_expiration=config.auth.jwt_expiration
)
api_key_auth = APIKeyAuth(header_name=config.auth.api_key_header)

# Create REST API
app = create_app(config)

# Add WebSocket endpoints

@app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup."""
    logger.info(f"Starting Instinct AI API v{API_VERSION}")
    logger.info("Starting WebSocket server")
    await websocket_server.start()

@app.on_event("shutdown")
async def shutdown_event():
    """Stop background tasks on application shutdown."""
    logger.info("Stopping WebSocket server")
    await websocket_server.stop()

@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    handler: WebSocketHandler = Depends(lambda: get_websocket_handler(websocket_server, jwt_auth))
):
    """
    WebSocket endpoint for real-time data streaming.
    
    This endpoint allows clients to connect to the WebSocket server and
    receive real-time data. No authentication is required.
    """
    await handler.handle_connection(websocket)

@app.websocket("/ws/auth")
async def authenticated_websocket_endpoint(
    websocket: WebSocket,
    handler: WebSocketHandler = Depends(lambda: get_websocket_handler(websocket_server, jwt_auth))
):
    """
    Authenticated WebSocket endpoint for real-time data streaming.
    
    This endpoint allows authenticated clients to connect to the WebSocket server
    and receive real-time data. Authentication is done via JWT token in the
    Authorization header.
    """
    token_data = await handler.get_token_data(websocket)
    
    if not token_data:
        await websocket.close(code=1008, reason="Unauthorized")
        return
    
    await handler.handle_authenticated_connection(websocket, token_data)


def main():
    """Start the API server."""
    # Get host and port from environment or use defaults
    host = os.environ.get("API_HOST", "0.0.0.0")
    port = int(os.environ.get("API_PORT", "8000"))
    
    logger.info(f"Starting API server on {host}:{port}")
    
    # Start API server
    uvicorn.run(
        "advanced_trading.api.main:app",
        host=host,
        port=port,
        reload=config.debug
    )


if __name__ == "__main__":
    main() 