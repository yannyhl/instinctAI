"""
Exchange Client Module

This module provides a client interface for connecting to and interacting with
various cryptocurrency and traditional exchanges. It abstracts away the differences
between different exchange APIs and provides a unified interface for trading.

The ExchangeClient class is the main entry point for interacting with exchanges,
with methods for connecting, disconnecting, and retrieving information about exchanges.
"""

import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Union, Any, Type, Set

from advanced_trading.core.observability import get_logger
from advanced_trading.core.common import ComponentRegistry

# Initialize logger
logger = get_logger(__name__)


class ExchangeType(Enum):
    """Types of exchanges supported by the system."""
    SPOT = "spot"
    FUTURES = "futures"
    OPTIONS = "options"
    MARGIN = "margin"
    DEX = "dex"


class AuthMethod(Enum):
    """Authentication methods supported by exchanges."""
    API_KEY = "api_key"
    OAUTH = "oauth"
    JWT = "jwt"
    CERTIFICATE = "certificate"
    CUSTOM = "custom"


class ExchangeClient(ABC):
    """
    Abstract base class for exchange clients.
    
    This class defines the interface that all exchange clients must implement.
    It provides methods for connecting to exchanges, executing trades, and
    retrieving market data.
    
    Attributes:
        name (str): The name of the exchange.
        exchange_type (ExchangeType): The type of exchange.
        auth_method (AuthMethod): The authentication method used.
        base_url (str): The base URL for API requests.
        rate_limit (int): The rate limit in requests per minute.
        timeout (int): The timeout for API requests in seconds.
        connected (bool): Whether the client is connected to the exchange.
    """
    
    def __init__(
        self,
        name: str,
        exchange_type: ExchangeType,
        auth_method: AuthMethod,
        base_url: str,
        rate_limit: int = 60,
        timeout: int = 30
    ):
        """
        Initialize the exchange client.
        
        Args:
            name (str): The name of the exchange.
            exchange_type (ExchangeType): The type of exchange.
            auth_method (AuthMethod): The authentication method used.
            base_url (str): The base URL for API requests.
            rate_limit (int, optional): The rate limit in requests per minute. Defaults to 60.
            timeout (int, optional): The timeout for API requests in seconds. Defaults to 30.
        """
        self.name = name
        self.exchange_type = exchange_type
        self.auth_method = auth_method
        self.base_url = base_url
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.connected = False
        self.session = None
        self.last_request_time = 0
        self.request_count = 0
    
    @abstractmethod
    def connect(self, credentials: Dict[str, Any]) -> bool:
        """
        Connect to the exchange using the provided credentials.
        
        Args:
            credentials (Dict[str, Any]): The credentials to use for authentication.
        
        Returns:
            bool: True if the connection was successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """
        Disconnect from the exchange.
        
        Returns:
            bool: True if the disconnection was successful, False otherwise.
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if the client is connected to the exchange.
        
        Returns:
            bool: True if the client is connected, False otherwise.
        """
        pass
    
    @abstractmethod
    def get_exchange_info(self) -> Dict[str, Any]:
        """
        Get information about the exchange.
        
        Returns:
            Dict[str, Any]: Information about the exchange.
        """
        pass
    
    def _rate_limit_check(self) -> None:
        """
        Check if we're exceeding the rate limit and wait if necessary.
        """
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        # If less than a minute has passed since the first request in this window
        if elapsed < 60 and self.request_count >= self.rate_limit:
            # Wait until the minute is up
            sleep_time = 60 - elapsed
            logger.info(f"Rate limit reached, waiting {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
            # Reset the window
            self.last_request_time = time.time()
            self.request_count = 0
        
        # If more than a minute has passed, start a new window
        elif elapsed >= 60:
            self.last_request_time = current_time
            self.request_count = 0
        
        # Increment the request count
        self.request_count += 1


# Registry of available exchange clients
_exchange_registry: Dict[str, Type[ExchangeClient]] = {}


def register_exchange_client(name: str, client_class: Type[ExchangeClient]) -> None:
    """
    Register an exchange client class with the registry.
    
    Args:
        name (str): The name of the exchange.
        client_class (Type[ExchangeClient]): The exchange client class.
    
    Raises:
        ValueError: If an exchange with the same name is already registered.
    """
    if name in _exchange_registry:
        raise ValueError(f"Exchange client '{name}' is already registered")
    
    _exchange_registry[name] = client_class
    logger.info(f"Registered exchange client for {name}")


def connect_exchange(
    name: str,
    credentials: Dict[str, Any],
    **kwargs
) -> ExchangeClient:
    """
    Connect to an exchange using the registered client class.
    
    Args:
        name (str): The name of the exchange to connect to.
        credentials (Dict[str, Any]): The credentials to use for authentication.
        **kwargs: Additional arguments to pass to the client constructor.
    
    Returns:
        ExchangeClient: The connected exchange client.
    
    Raises:
        ValueError: If no client is registered for the specified exchange.
    """
    if name not in _exchange_registry:
        raise ValueError(f"No exchange client registered for {name}")
    
    client_class = _exchange_registry[name]
    client = client_class(**kwargs)
    
    success = client.connect(credentials)
    if not success:
        raise ConnectionError(f"Failed to connect to exchange {name}")
    
    logger.info(f"Connected to exchange {name}")
    return client


def disconnect_exchange(client: ExchangeClient) -> bool:
    """
    Disconnect from an exchange.
    
    Args:
        client (ExchangeClient): The exchange client to disconnect.
    
    Returns:
        bool: True if the disconnection was successful, False otherwise.
    """
    success = client.disconnect()
    if success:
        logger.info(f"Disconnected from exchange {client.name}")
    else:
        logger.warning(f"Failed to disconnect from exchange {client.name}")
    
    return success


def get_exchange_info(client: ExchangeClient) -> Dict[str, Any]:
    """
    Get information about an exchange.
    
    Args:
        client (ExchangeClient): The exchange client.
    
    Returns:
        Dict[str, Any]: Information about the exchange.
    """
    return client.get_exchange_info()


def list_available_exchanges() -> List[str]:
    """
    List the names of all available exchanges.
    
    Returns:
        List[str]: The names of all available exchanges.
    """
    return list(_exchange_registry.keys())


# Register the ExchangeClient class with the component registry
ComponentRegistry.register_component("exchange_client", ExchangeClient) 