"""
Strategy Factory

This module implements the factory pattern for creating trading strategies.
It provides centralized strategy instantiation, parameter validation, and
strategy registration.
"""

import logging
import inspect
from typing import Dict, Type, Any, List, Optional, Callable, Set, Union
from dataclasses import dataclass
from enum import Enum
import importlib
import json
import os
import re

from ..base import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """Types of strategies supported by the factory."""
    ARBITRAGE = "arbitrage"
    STATISTICAL = "statistical"
    ML = "machine_learning"
    META = "meta"
    CUSTOM = "custom"


@dataclass
class StrategyMetadata:
    """Metadata about a strategy class."""
    name: str
    type: StrategyType
    description: str
    params: Dict[str, Dict[str, Any]]
    default_params: Dict[str, Any]
    required_data: List[str]
    tags: List[str]
    class_ref: Type[BaseStrategy]


class StrategyRegistry:
    """
    Registry of available strategy classes.
    
    This class maintains a registry of all available strategy classes, their
    metadata, and provides lookup functionality.
    """
    
    def __init__(self):
        """Initialize the strategy registry."""
        self._strategies: Dict[str, StrategyMetadata] = {}
        self._tags: Set[str] = set()
    
    def register(self, strategy_class: Type[BaseStrategy]) -> bool:
        """
        Register a strategy class.
        
        Args:
            strategy_class: The strategy class to register.
            
        Returns:
            True if registration was successful, False otherwise.
        """
        if not issubclass(strategy_class, BaseStrategy):
            logger.error(f"Cannot register {strategy_class.__name__}: Not a BaseStrategy subclass")
            return False
        
        try:
            # Extract metadata from class and docstring
            name = strategy_class.__name__
            
            # Get description and tags from docstring
            description, tags = self._parse_docstring(strategy_class.__doc__ or "")
            
            # Determine strategy type
            strategy_type = self._determine_strategy_type(strategy_class)
            
            # Extract parameter information
            params, default_params = self._extract_parameters(strategy_class)
            
            # Extract required data
            required_data = getattr(strategy_class, "REQUIRED_DATA", [])
            if not isinstance(required_data, list):
                required_data = []
            
            # Create metadata
            metadata = StrategyMetadata(
                name=name,
                type=strategy_type,
                description=description,
                params=params,
                default_params=default_params,
                required_data=required_data,
                tags=tags,
                class_ref=strategy_class
            )
            
            # Add to registry
            self._strategies[name] = metadata
            
            # Update tags
            self._tags.update(tags)
            
            logger.info(f"Registered strategy: {name}")
            return True
        
        except Exception as e:
            logger.error(f"Error registering strategy {strategy_class.__name__}: {str(e)}")
            return False
    
    def get_strategy(self, name: str) -> Optional[StrategyMetadata]:
        """
        Get strategy metadata by name.
        
        Args:
            name: Name of the strategy.
            
        Returns:
            Strategy metadata, or None if not found.
        """
        return self._strategies.get(name)
    
    def get_all_strategies(self) -> List[StrategyMetadata]:
        """
        Get all registered strategies.
        
        Returns:
            List of all strategy metadata.
        """
        return list(self._strategies.values())
    
    def get_strategies_by_type(self, strategy_type: StrategyType) -> List[StrategyMetadata]:
        """
        Get strategies of a specific type.
        
        Args:
            strategy_type: The type of strategies to get.
            
        Returns:
            List of strategy metadata for the specified type.
        """
        return [s for s in self._strategies.values() if s.type == strategy_type]
    
    def get_strategies_by_tag(self, tag: str) -> List[StrategyMetadata]:
        """
        Get strategies with a specific tag.
        
        Args:
            tag: The tag to search for.
            
        Returns:
            List of strategy metadata with the specified tag.
        """
        return [s for s in self._strategies.values() if tag in s.tags]
    
    def get_all_tags(self) -> List[str]:
        """
        Get all registered tags.
        
        Returns:
            List of all tags.
        """
        return sorted(list(self._tags))
    
    def clear(self) -> None:
        """Clear the registry."""
        self._strategies.clear()
        self._tags.clear()
    
    def _parse_docstring(self, docstring: str) -> tuple:
        """
        Parse the strategy docstring for description and tags.
        
        Args:
            docstring: The strategy class docstring.
            
        Returns:
            Tuple of (description, tags).
        """
        lines = [line.strip() for line in docstring.split("\n")]
        description = ""
        tags = []
        
        # Extract the first non-empty line as description
        for line in lines:
            if line and not line.startswith(":"):
                description = line
                break
        
        # Look for tags in docstring
        tag_pattern = re.compile(r"tags:\s*\[(.*?)\]", re.IGNORECASE)
        for line in lines:
            match = tag_pattern.search(line)
            if match:
                tag_str = match.group(1)
                tags = [t.strip().strip("'\"") for t in tag_str.split(",")]
                break
        
        return description, tags
    
    def _determine_strategy_type(self, strategy_class: Type[BaseStrategy]) -> StrategyType:
        """
        Determine the strategy type from the class.
        
        Args:
            strategy_class: The strategy class.
            
        Returns:
            The determined strategy type.
        """
        name = strategy_class.__name__
        module = strategy_class.__module__
        
        if "arbitrage" in module.lower() or "arbitrage" in name.lower():
            return StrategyType.ARBITRAGE
        elif "ml" in module.lower() or "machine" in module.lower() or "lstm" in name.lower():
            return StrategyType.ML
        elif "statistical" in module.lower() or "stat" in module.lower():
            return StrategyType.STATISTICAL
        elif "meta" in name.lower() or "adaptive" in name.lower():
            return StrategyType.META
        else:
            return StrategyType.CUSTOM
    
    def _extract_parameters(self, strategy_class: Type[BaseStrategy]) -> tuple:
        """
        Extract parameter information from the strategy class.
        
        Args:
            strategy_class: The strategy class.
            
        Returns:
            Tuple of (params, default_params).
        """
        params = {}
        default_params = {}
        
        # Check for init signature
        if hasattr(strategy_class, "__init__"):
            sig = inspect.signature(strategy_class.__init__)
            for name, param in sig.parameters.items():
                # Skip self parameter
                if name == "self":
                    continue
                
                param_info = {
                    "type": str(param.annotation) if param.annotation != inspect.Parameter.empty else "Any",
                    "required": param.default == inspect.Parameter.empty,
                    "default": None if param.default == inspect.Parameter.empty else param.default
                }
                
                params[name] = param_info
                
                # Add to default params if it has a default
                if param.default != inspect.Parameter.empty:
                    default_params[name] = param.default
        
        # Check for class variable DEFAULT_PARAMS
        if hasattr(strategy_class, "DEFAULT_PARAMS") and isinstance(strategy_class.DEFAULT_PARAMS, dict):
            for name, value in strategy_class.DEFAULT_PARAMS.items():
                default_params[name] = value
                if name not in params:
                    params[name] = {
                        "type": "Any",
                        "required": False,
                        "default": value
                    }
        
        return params, default_params


class StrategyValidator:
    """
    Validates strategy parameters and configurations.
    
    This class provides parameter validation, type checking, and value
    validation for strategy parameters.
    """
    
    def __init__(self, registry: StrategyRegistry):
        """
        Initialize the validator.
        
        Args:
            registry: The strategy registry to use for validation.
        """
        self.registry = registry
    
    def validate_parameters(self, strategy_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize parameters for a strategy.
        
        Args:
            strategy_name: Name of the strategy.
            parameters: Parameters to validate.
            
        Returns:
            Normalized parameters.
            
        Raises:
            ValueError: If parameters are invalid.
        """
        metadata = self.registry.get_strategy(strategy_name)
        if not metadata:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        
        # Start with default parameters
        normalized = metadata.default_params.copy()
        
        # Check for required parameters
        for name, param_info in metadata.params.items():
            if param_info["required"] and name not in parameters:
                raise ValueError(f"Missing required parameter: {name}")
        
        # Apply provided parameters
        for name, value in parameters.items():
            if name not in metadata.params:
                logger.warning(f"Unknown parameter for {strategy_name}: {name}")
                continue
            
            # TODO: Add type checking and value validation
            normalized[name] = value
        
        return normalized
    
    def validate_configuration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a complete strategy configuration.
        
        Args:
            config: Strategy configuration.
            
        Returns:
            Validated configuration.
            
        Raises:
            ValueError: If configuration is invalid.
        """
        if "strategy" not in config:
            raise ValueError("Missing 'strategy' in configuration")
        
        strategy_name = config["strategy"]
        parameters = config.get("parameters", {})
        
        # Validate parameters
        validated_parameters = self.validate_parameters(strategy_name, parameters)
        
        # Return validated configuration
        return {
            "strategy": strategy_name,
            "parameters": validated_parameters,
            "data_requirements": self.registry.get_strategy(strategy_name).required_data
        }


class StrategyFactory:
    """
    Factory for creating strategy instances.
    
    This class provides methods for creating strategy instances, registering
    strategy classes, and validating strategy configurations.
    """
    
    def __init__(self):
        """Initialize the strategy factory."""
        self.registry = StrategyRegistry()
        self.validator = StrategyValidator(self.registry)
    
    def register_strategy(self, strategy_class: Type[BaseStrategy]) -> bool:
        """
        Register a strategy class.
        
        Args:
            strategy_class: The strategy class to register.
            
        Returns:
            True if registration was successful, False otherwise.
        """
        return self.registry.register(strategy_class)
    
    def discover_strategies(self) -> int:
        """
        Discover and register strategies from the strategies module.
        
        Returns:
            Number of strategies discovered and registered.
        """
        count = 0
        
        # Import strategy modules
        from .. import arbitrage, statistical, ml
        
        # Discover strategy classes in modules
        modules = [arbitrage, statistical, ml]
        
        for module in modules:
            # Get all classes from the module
            for name in dir(module):
                if name.startswith("_"):
                    continue
                
                obj = getattr(module, name)
                
                # Check if it's a strategy class
                if (
                    inspect.isclass(obj) and 
                    issubclass(obj, BaseStrategy) and 
                    obj != BaseStrategy
                ):
                    if self.register_strategy(obj):
                        count += 1
        
        return count
    
    def create_strategy(self, strategy_name: str, parameters: Dict[str, Any] = None) -> BaseStrategy:
        """
        Create a strategy instance.
        
        Args:
            strategy_name: Name of the strategy to create.
            parameters: Parameters for the strategy. If None, default parameters are used.
            
        Returns:
            Strategy instance.
            
        Raises:
            ValueError: If strategy is unknown or parameters are invalid.
        """
        parameters = parameters or {}
        
        # Get strategy metadata
        metadata = self.registry.get_strategy(strategy_name)
        if not metadata:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        
        # Validate parameters
        validated_params = self.validator.validate_parameters(strategy_name, parameters)
        
        # Create instance
        try:
            strategy = metadata.class_ref(**validated_params)
            logger.info(f"Created strategy: {strategy_name}")
            return strategy
        except Exception as e:
            logger.error(f"Error creating strategy {strategy_name}: {str(e)}")
            raise ValueError(f"Error creating strategy: {str(e)}")
    
    def create_from_config(self, config: Dict[str, Any]) -> BaseStrategy:
        """
        Create a strategy from a configuration dictionary.
        
        Args:
            config: Strategy configuration.
            
        Returns:
            Strategy instance.
            
        Raises:
            ValueError: If configuration is invalid.
        """
        # Validate configuration
        validated_config = self.validator.validate_configuration(config)
        
        # Create strategy
        return self.create_strategy(
            validated_config["strategy"],
            validated_config["parameters"]
        )
    
    def create_from_json(self, json_str: str) -> BaseStrategy:
        """
        Create a strategy from a JSON string.
        
        Args:
            json_str: JSON string containing strategy configuration.
            
        Returns:
            Strategy instance.
            
        Raises:
            ValueError: If JSON is invalid or configuration is invalid.
        """
        try:
            config = json.loads(json_str)
            return self.create_from_config(config)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {str(e)}")
    
    def create_from_file(self, file_path: str) -> BaseStrategy:
        """
        Create a strategy from a configuration file.
        
        Args:
            file_path: Path to the configuration file.
            
        Returns:
            Strategy instance.
            
        Raises:
            ValueError: If file is not found or configuration is invalid.
        """
        if not os.path.exists(file_path):
            raise ValueError(f"Configuration file not found: {file_path}")
        
        try:
            with open(file_path, "r") as f:
                config = json.load(f)
            
            return self.create_from_config(config)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {file_path}: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error reading configuration file: {str(e)}")


# Update module exports
__all__ = [
    'StrategyType',
    'StrategyMetadata',
    'StrategyRegistry',
    'StrategyValidator',
    'StrategyFactory'
] 