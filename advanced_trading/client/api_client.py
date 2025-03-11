"""
API Client

This module provides the base API client for interacting with the Instinct AI API.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urljoin

import requests
import websocket

logger = logging.getLogger("advanced_trading.client")


class ApiClient:
    """Base API client for Instinct AI."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_version: str = "v1",
        token: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30,
        verify_ssl: bool = True,
        proxies: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize API client.
        
        Args:
            base_url: Base URL for the API.
            api_version: API version to use (e.g., 'v1').
            token: JWT token for authentication.
            api_key: API key for authentication.
            timeout: Request timeout in seconds.
            verify_ssl: Whether to verify SSL certificates.
            proxies: Proxy configuration for requests.
        """
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self.token = token
        self.api_key = api_key
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.proxies = proxies
        self.session = requests.Session()
        
        # Create clients for specific API groups
        self.auth = None  # Will be set after import to avoid circular imports
        self.strategies = None  # Will be set after import to avoid circular imports
        self.data = None  # Will be set after import to avoid circular imports
        self.execution = None  # Will be set after import to avoid circular imports
        self.backtest = None  # Will be set after import to avoid circular imports
    
    def _initialize_clients(self):
        """Initialize API group clients."""
        from .auth import AuthClient
        from .strategies import StrategiesClient
        from .data import DataClient
        from .execution import ExecutionClient
        from .backtest import BacktestClient
        
        self.auth = AuthClient(self)
        self.strategies = StrategiesClient(self)
        self.data = DataClient(self)
        self.execution = ExecutionClient(self)
        self.backtest = BacktestClient(self)
    
    @property
    def headers(self) -> Dict[str, str]:
        """Get request headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        
        return headers
    
    def get_url(self, endpoint: str) -> str:
        """
        Get full URL for an endpoint.
        
        Args:
            endpoint: API endpoint path.
            
        Returns:
            Full URL.
        """
        # Remove leading slash if present
        endpoint = endpoint.lstrip("/")
        
        # Add API version if not already in endpoint
        if self.api_version and not endpoint.startswith(f"{self.api_version}/"):
            endpoint = f"{self.api_version}/{endpoint}"
        
        # Add 'api/' prefix if not already in endpoint
        if not endpoint.startswith("api/"):
            endpoint = f"api/{endpoint}"
        
        return urljoin(f"{self.base_url}/", endpoint)
    
    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
        verify_ssl: Optional[bool] = None,
        proxies: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Make an API request.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.).
            endpoint: API endpoint path.
            params: Query parameters.
            data: Request body data.
            headers: Additional headers.
            timeout: Request timeout in seconds.
            verify_ssl: Whether to verify SSL certificates.
            proxies: Proxy configuration for this request.
            
        Returns:
            API response data.
            
        Raises:
            requests.exceptions.RequestException: If the request fails.
        """
        url = self.get_url(endpoint)
        request_headers = self.headers.copy()
        
        if headers:
            request_headers.update(headers)
        
        if timeout is None:
            timeout = self.timeout
            
        if verify_ssl is None:
            verify_ssl = self.verify_ssl
            
        if proxies is None:
            proxies = self.proxies
        
        # Convert data to JSON if it's a dict
        if data is not None and not isinstance(data, str):
            data = json.dumps(data)
        
        logger.debug(f"Making {method} request to {url}")
        
        response = self.session.request(
            method=method,
            url=url,
            params=params,
            data=data,
            headers=request_headers,
            timeout=timeout,
            verify=verify_ssl,
            proxies=proxies,
        )
        
        logger.debug(f"Response status code: {response.status_code}")
        
        # Raise exception for error status codes
        response.raise_for_status()
        
        # Return JSON response if available
        if response.text:
            return response.json()
        
        return {}
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """
        Make a GET request.
        
        Args:
            endpoint: API endpoint path.
            params: Query parameters.
            **kwargs: Additional arguments for request().
            
        Returns:
            API response data.
        """
        return self.request("GET", endpoint, params=params, **kwargs)
    
    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """
        Make a POST request.
        
        Args:
            endpoint: API endpoint path.
            data: Request body data.
            **kwargs: Additional arguments for request().
            
        Returns:
            API response data.
        """
        return self.request("POST", endpoint, data=data, **kwargs)
    
    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """
        Make a PUT request.
        
        Args:
            endpoint: API endpoint path.
            data: Request body data.
            **kwargs: Additional arguments for request().
            
        Returns:
            API response data.
        """
        return self.request("PUT", endpoint, data=data, **kwargs)
    
    def delete(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make a DELETE request.
        
        Args:
            endpoint: API endpoint path.
            **kwargs: Additional arguments for request().
            
        Returns:
            API response data.
        """
        return self.request("DELETE", endpoint, **kwargs)
    
    def create_websocket_connection(self, authenticated: bool = False) -> websocket.WebSocketApp:
        """
        Create a WebSocket connection.
        
        Args:
            authenticated: Whether to use the authenticated endpoint.
            
        Returns:
            WebSocket connection.
        """
        # Determine endpoint
        endpoint = "ws/auth" if authenticated else "ws"
        
        # Build URL
        ws_base_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_base_url}/{endpoint}"
        
        # Prepare headers
        ws_headers = {}
        
        if authenticated and self.token:
            ws_headers["Authorization"] = f"Bearer {self.token}"
        
        # Create connection
        def on_open(ws):
            logger.info("WebSocket connection opened")
        
        def on_message(ws, message):
            logger.debug(f"WebSocket message received: {message}")
        
        def on_error(ws, error):
            logger.error(f"WebSocket error: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            logger.info(f"WebSocket connection closed: {close_status_code} - {close_msg}")
        
        ws_app = websocket.WebSocketApp(
            ws_url,
            header=ws_headers,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        
        return ws_app 