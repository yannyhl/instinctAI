"""
WebSocket API

This module provides the WebSocket API for the Instinct AI trading platform,
enabling real-time data streaming and notifications.
"""

from .server import WebSocketServer
from .handlers import WebSocketHandler, get_websocket_handler 