"""
WebSocket Server

This module provides a WebSocket server for real-time data streaming.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Set, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np

logger = logging.getLogger("advanced_trading.api.websocket")


@dataclass
class WebSocketClient:
    """
    WebSocket client connection.
    
    Attributes:
        id: Unique client identifier
        subscriptions: Topics the client is subscribed to
        send_queue: Queue for messages to be sent to the client
        send_func: Function to send messages to the client
        authenticated: Whether the client is authenticated
        user_data: Additional data about the user
        connected_at: Time when the client connected
        last_seen: Time of last activity
    """
    
    id: str
    subscriptions: Set[str] = field(default_factory=set)
    send_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    send_func: Optional[Callable[[str], Awaitable[None]]] = None
    authenticated: bool = False
    user_data: Dict[str, Any] = field(default_factory=dict)
    connected_at: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)


class WebSocketServer:
    """
    WebSocket server for real-time data streaming.
    
    This server handles client connections, subscriptions, and message routing.
    """
    
    def __init__(self):
        """Initialize the WebSocket server."""
        self.clients: Dict[str, WebSocketClient] = {}
        self.topics: Dict[str, Set[str]] = {}  # Maps topics to client IDs
        self.running = False
        self.publish_task = None
    
    async def start(self):
        """Start the WebSocket server."""
        if self.running:
            logger.warning("WebSocket server is already running")
            return
        
        self.running = True
        self.publish_task = asyncio.create_task(self._publish_loop())
        logger.info("WebSocket server started")
    
    async def stop(self):
        """Stop the WebSocket server."""
        if not self.running:
            logger.warning("WebSocket server is not running")
            return
        
        self.running = False
        
        if self.publish_task:
            self.publish_task.cancel()
            try:
                await self.publish_task
            except asyncio.CancelledError:
                pass
        
        # Close all client connections
        for client_id in list(self.clients.keys()):
            await self.disconnect_client(client_id)
        
        logger.info("WebSocket server stopped")
    
    async def register_client(self, 
                           client_id: str, 
                           send_func: Callable[[str], Awaitable[None]]) -> WebSocketClient:
        """
        Register a new WebSocket client.
        
        Args:
            client_id: Unique client identifier
            send_func: Function to send messages to the client
            
        Returns:
            Registered client
        """
        client = WebSocketClient(id=client_id, send_func=send_func)
        self.clients[client_id] = client
        
        logger.info(f"Client {client_id} connected")
        
        # Send welcome message
        await self.send_to_client(
            client_id,
            {
                "type": "welcome",
                "data": {
                    "client_id": client_id,
                    "server_time": datetime.now().isoformat()
                }
            }
        )
        
        return client
    
    async def disconnect_client(self, client_id: str) -> bool:
        """
        Disconnect a WebSocket client.
        
        Args:
            client_id: Client ID to disconnect
            
        Returns:
            True if client was disconnected, False if not found
        """
        client = self.clients.get(client_id)
        
        if not client:
            return False
        
        # Remove client from all topic subscriptions
        for topic in client.subscriptions:
            if topic in self.topics and client_id in self.topics[topic]:
                self.topics[topic].remove(client_id)
        
        # Remove client
        del self.clients[client_id]
        
        logger.info(f"Client {client_id} disconnected")
        
        return True
    
    async def authenticate_client(self, 
                               client_id: str, 
                               user_data: Dict[str, Any]) -> bool:
        """
        Authenticate a WebSocket client.
        
        Args:
            client_id: Client ID to authenticate
            user_data: User data to associate with the client
            
        Returns:
            True if client was authenticated, False if not found
        """
        client = self.clients.get(client_id)
        
        if not client:
            return False
        
        client.authenticated = True
        client.user_data = user_data
        client.last_seen = datetime.now()
        
        # Send authentication confirmation
        await self.send_to_client(
            client_id,
            {
                "type": "auth",
                "data": {
                    "authenticated": True,
                    "user_id": user_data.get("user_id", "unknown")
                }
            }
        )
        
        logger.info(f"Client {client_id} authenticated as {user_data.get('user_id', 'unknown')}")
        
        return True
    
    async def subscribe(self, client_id: str, topics: List[str]) -> bool:
        """
        Subscribe a client to topics.
        
        Args:
            client_id: Client ID to subscribe
            topics: Topics to subscribe to
            
        Returns:
            True if subscription was successful, False if client not found
        """
        client = self.clients.get(client_id)
        
        if not client:
            return False
        
        # Update client subscriptions
        for topic in topics:
            client.subscriptions.add(topic)
            
            # Initialize topic if not exists
            if topic not in self.topics:
                self.topics[topic] = set()
            
            # Add client to topic
            self.topics[topic].add(client_id)
        
        client.last_seen = datetime.now()
        
        # Send subscription confirmation
        await self.send_to_client(
            client_id,
            {
                "type": "subscription",
                "data": {
                    "topics": list(client.subscriptions)
                }
            }
        )
        
        logger.info(f"Client {client_id} subscribed to {topics}")
        
        return True
    
    async def unsubscribe(self, client_id: str, topics: List[str]) -> bool:
        """
        Unsubscribe a client from topics.
        
        Args:
            client_id: Client ID to unsubscribe
            topics: Topics to unsubscribe from
            
        Returns:
            True if unsubscription was successful, False if client not found
        """
        client = self.clients.get(client_id)
        
        if not client:
            return False
        
        # Update client subscriptions
        for topic in topics:
            if topic in client.subscriptions:
                client.subscriptions.remove(topic)
            
            # Remove client from topic
            if topic in self.topics and client_id in self.topics[topic]:
                self.topics[topic].remove(client_id)
        
        client.last_seen = datetime.now()
        
        # Send unsubscription confirmation
        await self.send_to_client(
            client_id,
            {
                "type": "subscription",
                "data": {
                    "topics": list(client.subscriptions)
                }
            }
        )
        
        logger.info(f"Client {client_id} unsubscribed from {topics}")
        
        return True
    
    async def process_message(self, client_id: str, message: str) -> bool:
        """
        Process a message from a client.
        
        Args:
            client_id: Client ID that sent the message
            message: Message received from the client
            
        Returns:
            True if message was processed, False otherwise
        """
        client = self.clients.get(client_id)
        
        if not client:
            return False
        
        client.last_seen = datetime.now()
        
        try:
            data = json.loads(message)
            
            if not isinstance(data, dict):
                await self.send_to_client(
                    client_id,
                    {
                        "type": "error",
                        "data": {
                            "code": "invalid_message",
                            "message": "Message must be a JSON object"
                        }
                    }
                )
                return False
            
            message_type = data.get("type")
            
            if not message_type:
                await self.send_to_client(
                    client_id,
                    {
                        "type": "error",
                        "data": {
                            "code": "missing_type",
                            "message": "Message must have a 'type' field"
                        }
                    }
                )
                return False
            
            if message_type == "ping":
                await self.send_to_client(
                    client_id,
                    {
                        "type": "pong",
                        "data": {
                            "server_time": datetime.now().isoformat()
                        }
                    }
                )
                return True
            
            if message_type == "subscribe":
                topics = data.get("topics", [])
                return await self.subscribe(client_id, topics)
            
            if message_type == "unsubscribe":
                topics = data.get("topics", [])
                return await self.unsubscribe(client_id, topics)
            
            if message_type == "auth":
                # In a real implementation, this would validate the token
                # and retrieve user data
                auth_token = data.get("token")
                
                if not auth_token:
                    await self.send_to_client(
                        client_id,
                        {
                            "type": "error",
                            "data": {
                                "code": "missing_token",
                                "message": "Authentication requires a token"
                            }
                        }
                    )
                    return False
                
                # Mock authentication for now
                user_data = {
                    "user_id": "test-user",
                    "scopes": ["read", "write"]
                }
                
                return await self.authenticate_client(client_id, user_data)
            
            # Unknown message type
            await self.send_to_client(
                client_id,
                {
                    "type": "error",
                    "data": {
                        "code": "unknown_type",
                        "message": f"Unknown message type: {message_type}"
                    }
                }
            )
            return False
            
        except json.JSONDecodeError:
            await self.send_to_client(
                client_id,
                {
                    "type": "error",
                    "data": {
                        "code": "invalid_json",
                        "message": "Invalid JSON"
                    }
                }
            )
            return False
        except Exception as e:
            logger.exception(f"Error processing message from client {client_id}")
            await self.send_to_client(
                client_id,
                {
                    "type": "error",
                    "data": {
                        "code": "internal_error",
                        "message": f"Internal server error: {str(e)}"
                    }
                }
            )
            return False
    
    async def send_to_client(self, client_id: str, message: Dict[str, Any]) -> bool:
        """
        Send a message to a client.
        
        Args:
            client_id: Client ID to send to
            message: Message to send
            
        Returns:
            True if message was queued, False if client not found
        """
        client = self.clients.get(client_id)
        
        if not client:
            return False
        
        # Add message to client's send queue
        await client.send_queue.put(json.dumps(message))
        
        return True
    
    async def publish(self, topic: str, message: Dict[str, Any]) -> int:
        """
        Publish a message to all clients subscribed to a topic.
        
        Args:
            topic: Topic to publish to
            message: Message to publish
            
        Returns:
            Number of clients the message was sent to
        """
        if topic not in self.topics:
            return 0
        
        client_ids = self.topics[topic]
        sent_count = 0
        
        for client_id in client_ids:
            if await self.send_to_client(client_id, message):
                sent_count += 1
        
        logger.debug(f"Published to topic {topic}: {sent_count} clients")
        
        return sent_count
    
    async def client_sender(self, client_id: str) -> None:
        """
        Background task to send queued messages to a client.
        
        Args:
            client_id: Client ID to send to
        """
        client = self.clients.get(client_id)
        
        if not client or not client.send_func:
            return
        
        while True:
            try:
                message = await client.send_queue.get()
                
                if message is None:
                    break
                
                await client.send_func(message)
                client.send_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error sending message to client {client_id}")
                # Don't break the loop on send error, continue with next message
    
    async def _publish_loop(self) -> None:
        """Background task for sending periodic updates to clients."""
        while self.running:
            try:
                # Example: publish market tick data every second
                await self.publish("market.tick", {
                    "type": "market.tick",
                    "data": {
                        "symbol": "BTC/USD",
                        "price": 50000.0 + 1000.0 * (0.5 - np.random.random()),
                        "volume": np.random.random() * 10.0,
                        "timestamp": datetime.now().isoformat()
                    }
                })
                
                # Example: publish system status every 5 seconds
                if int(time.time()) % 5 == 0:
                    await self.publish("system.status", {
                        "type": "system.status",
                        "data": {
                            "status": "healthy",
                            "active_strategies": 2,
                            "timestamp": datetime.now().isoformat()
                        }
                    })
                
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Error in publish loop")
                await asyncio.sleep(1.0)  # Sleep and retry 