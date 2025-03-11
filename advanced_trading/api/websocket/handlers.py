"""
WebSocket Handlers

This module provides handlers for WebSocket connections.
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

import jwt
from fastapi import WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .server import WebSocketServer
from ..auth.jwt import JWTAuth

logger = logging.getLogger("advanced_trading.api.websocket")


class WebSocketHandler:
    """
    WebSocket connection handler.
    
    This class handles WebSocket connections, authentication, and message routing.
    """
    
    def __init__(self, server: WebSocketServer, jwt_auth: JWTAuth):
        """
        Initialize WebSocket handler.
        
        Args:
            server: WebSocket server
            jwt_auth: JWT authentication handler
        """
        self.server = server
        self.jwt_auth = jwt_auth
    
    async def handle_connection(self, websocket: WebSocket):
        """
        Handle a WebSocket connection.
        
        Args:
            websocket: WebSocket connection
        """
        await websocket.accept()
        
        # Generate client ID
        client_id = f"client_{uuid.uuid4().hex}"
        
        # Register client with server
        send_func = lambda msg: websocket.send_text(msg)
        client = await self.server.register_client(client_id, send_func)
        
        # Start client sender task
        sender_task = asyncio.create_task(self.server.client_sender(client_id))
        
        try:
            # Main message loop
            while True:
                message = await websocket.receive_text()
                await self.server.process_message(client_id, message)
        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            logger.exception(f"Error handling WebSocket connection for client {client_id}")
        finally:
            # Clean up
            sender_task.cancel()
            await self.server.disconnect_client(client_id)
    
    async def handle_authenticated_connection(self, 
                                         websocket: WebSocket, 
                                         token_data: Dict[str, Any]):
        """
        Handle an authenticated WebSocket connection.
        
        Args:
            websocket: WebSocket connection
            token_data: JWT token data
        """
        await websocket.accept()
        
        # Generate client ID
        client_id = f"client_{uuid.uuid4().hex}"
        
        # Register client with server
        send_func = lambda msg: websocket.send_text(msg)
        client = await self.server.register_client(client_id, send_func)
        
        # Authenticate client
        user_data = {
            "user_id": token_data.get("sub", "unknown"),
            "username": token_data.get("username", "unknown"),
            "scopes": token_data.get("scopes", [])
        }
        await self.server.authenticate_client(client_id, user_data)
        
        # Start client sender task
        sender_task = asyncio.create_task(self.server.client_sender(client_id))
        
        try:
            # Main message loop
            while True:
                message = await websocket.receive_text()
                await self.server.process_message(client_id, message)
        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected")
        except Exception as e:
            logger.exception(f"Error handling WebSocket connection for client {client_id}")
        finally:
            # Clean up
            sender_task.cancel()
            await self.server.disconnect_client(client_id)
    
    async def get_token_data(self, websocket: WebSocket) -> Optional[Dict[str, Any]]:
        """
        Extract and validate JWT token from WebSocket headers.
        
        Args:
            websocket: WebSocket connection
            
        Returns:
            Decoded token data, or None if no valid token found
        """
        # Get token from headers
        auth_header = websocket.headers.get("authorization")
        
        if not auth_header:
            return None
        
        # Extract token
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        
        token = parts[1]
        
        try:
            # Decode token
            token_data = self.jwt_auth.decode_token(token)
            return token_data
        except Exception as e:
            logger.warning(f"Invalid JWT token: {str(e)}")
            return None


async def get_websocket_handler(websocket_server: WebSocketServer, jwt_auth: JWTAuth) -> WebSocketHandler:
    """
    Get a WebSocket handler instance.
    
    This function can be used as a FastAPI dependency.
    
    Args:
        websocket_server: WebSocket server
        jwt_auth: JWT authentication handler
        
    Returns:
        WebSocket handler instance
    """
    return WebSocketHandler(websocket_server, jwt_auth) 