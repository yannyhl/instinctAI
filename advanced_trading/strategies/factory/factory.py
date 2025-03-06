"""
Strategy Factory Implementation

This module provides the implementation of the strategy factory, which is responsible for
creating and managing trading strategies in the Instinct AI platform.

The factory maintains a registry of strategy classes and provides methods for creating
strategy instances, registering new strategy classes, and discovering available strategies.
"""

import inspect
from typing import Dict, List, Optional, Union, Any, Type, Callable

from advanced_trading.core.common import ComponentRegistry
from advanced_trading.core.observability import get_logger
from advanced_trading.strategies.base import Strategy, StrategyConfig, StrategyType

# Initialize logger
logger = get_logger(__name__)

# Strategy registry
_strategy_registry: Dict[str, Type[Strategy]] = {}
_strategy_metadata: Dict[str, Dict[str, Any]] = {}


def register_strategy(
    strategy_class: Type[Strategy],
    name: Optional[str] = None,
    strategy_type: Optional[StrategyType] = None,
    description: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Register a strategy class with the factory.
    
    Args:
        strategy_class (Type[Strategy]): The strategy class to register.
        name (Optional[str]): The name to register the strategy under. Defaults to the class name.
        strategy_type (Optional[StrategyType]): The type of the strategy. Defaults to StrategyType.CUSTOM.
        description (Optional[str]): A description of the strategy. Defaults to the class docstring.
        metadata (Optional[Dict[str, Any]]): Additional metadata about the strategy.
    
    Raises:
        ValueError: If a strategy with the same name is already registered.
    """
    # Get the strategy name
    if name is None:
        name = strategy_class.__name__
    
    # Check if the strategy is already registered
    if name in _strategy_registry:
        raise ValueError(f"Strategy '{name}' is already registered")
    
    # Register the strategy
    _strategy_registry[name] = strategy_class
    
    # Get the strategy type
    if strategy_type is None:
        strategy_type = StrategyType.CUSTOM
    
    # Get the strategy description
    if description is None:
        description = inspect.getdoc(strategy_class) or ""
    
    # Create the strategy metadata
    _strategy_metadata[name] = {
        "name": name,
        "type": strategy_type,
        "description": description,
        **(metadata or {})
    }
    
    logger.info(f"Registered strategy '{name}' of type '{strategy_type.value}'")


def get_strategy_class(name: str) -> Type[Strategy]:
    """Get a strategy class by name.
    
    Args:
        name (str): The name of the strategy class.
    
    Returns:
        Type[Strategy]: The strategy class.
    
    Raises:
        ValueError: If no strategy with the given name is registered.
    """
    if name not in _strategy_registry:
        raise ValueError(f"No strategy registered with name '{name}'")
    
    return _strategy_registry[name]


def create_strategy(config: StrategyConfig) -> Strategy:
    """Create a strategy instance from a configuration.
    
    Args:
        config (StrategyConfig): The strategy configuration.
    
    Returns:
        Strategy: The created strategy instance.
    
    Raises:
        ValueError: If no strategy with the given name is registered.
    """
    # Get the strategy class
    strategy_class = get_strategy_class(config.name)
    
    # Create the strategy instance
    strategy = strategy_class(config)
    
    # Initialize the strategy
    strategy.initialize()
    
    logger.info(f"Created strategy '{config.name}' with symbols {config.symbols}")
    
    return strategy


def list_available_strategies() -> List[str]:
    """List the names of all available strategies.
    
    Returns:
        List[str]: The names of all available strategies.
    """
    return list(_strategy_registry.keys())


def strategy_metadata(name: Optional[str] = None) -> Union[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """Get metadata about strategies.
    
    Args:
        name (Optional[str]): The name of the strategy to get metadata for.
            If None, returns metadata for all strategies.
    
    Returns:
        Union[Dict[str, Any], Dict[str, Dict[str, Any]]]: The strategy metadata.
    
    Raises:
        ValueError: If no strategy with the given name is registered.
    """
    if name is not None:
        if name not in _strategy_metadata:
            raise ValueError(f"No strategy registered with name '{name}'")
        return _strategy_metadata[name]
    
    return _strategy_metadata


# Register the factory with the component registry
ComponentRegistry.register_component_factory("strategy", create_strategy) 