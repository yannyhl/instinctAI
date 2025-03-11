"""
Instinct AI Client SDK

This package provides a client SDK for interacting with the Instinct AI API.
"""

from .api_client import ApiClient
from .auth import AuthClient
from .strategies import StrategiesClient
from .data import DataClient
from .execution import ExecutionClient
from .backtest import BacktestClient

__version__ = "1.0.0" 