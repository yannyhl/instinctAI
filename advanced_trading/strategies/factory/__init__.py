"""
Strategy Factory Module

This module provides factory classes and functions for dynamically creating,
configuring, and managing trading strategies. It enables runtime strategy
instantiation, parameter validation, and strategy registration.

Components:
- StrategyFactory: Central factory for strategy creation and management
- StrategyRegistry: Registry of available strategy classes
- StrategyValidator: Parameter and configuration validator
"""

from typing import Dict, List, Optional, Union, Any, Type

from advanced_trading.strategies.base import Strategy, StrategyConfig

# Import factory components
from .factory import (
    create_strategy, register_strategy, get_strategy_class,
    list_available_strategies, strategy_metadata
)

# Public API
__all__ = [
    'StrategyFactory',
    'StrategyRegistry',
    'StrategyValidator',
] 