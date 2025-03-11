"""
Strategy Registry Module

This module provides a registry for managing strategy classes, enabling dynamic discovery,
registration, and instantiation of strategies. The registry is responsible for:

1. Registering strategy classes with metadata
2. Discovering available strategies in the codebase
3. Instantiating strategies based on configuration
4. Maintaining version information for strategies
5. Providing strategy documentation and requirements

The registry ensures that strategies can be discovered and used dynamically without
requiring code changes when new strategies are added.
"""

import os
import sys
import inspect
import importlib
import pkgutil
from typing import Dict, List, Type, Optional, Any, Callable, Set, Union
import logging
from dataclasses import dataclass

from advanced_trading.strategies.base import Strategy, StrategyConfig, StrategyType
from advanced_trading.core.common import ComponentRegistry

# Setup logging
logger = logging.getLogger(__name__)


@dataclass
class StrategyMetadata:
    """Metadata for a strategy class.
    
    This class contains metadata about a strategy, including its name, description,
    parameters, requirements, and version information.
    
    Attributes:
        name (str): The name of the strategy.
        description (str): A description of the strategy.
        strategy_type (StrategyType): The type of the strategy.
        parameters (Dict[str, Dict[str, Any]]): The parameters accepted by the strategy.
        required_data (List[str]): The data required by the strategy.
        version (str): The version of the strategy.
        author (str): The author of the strategy.
        tags (List[str]): Tags associated with the strategy.
        performance_metrics (Dict[str, float]): Performance metrics for the strategy.
        example_config (Optional[Dict[str, Any]]): An example configuration for the strategy.
    """
    name: str
    description: str
    strategy_type: StrategyType
    parameters: Dict[str, Dict[str, Any]]
    required_data: List[str]
    version: str = "1.0.0"
    author: str = "Instinct AI Team"
    tags: List[str] = None
    performance_metrics: Dict[str, float] = None
    example_config: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.performance_metrics is None:
            self.performance_metrics = {}


class StrategyRegistry:
    """Registry for strategy classes.
    
    This class provides a registry for strategy classes, enabling dynamic discovery,
    registration, and instantiation of strategies.
    
    Attributes:
        _strategies (Dict[str, Type[Strategy]]): Registered strategy classes by name.
        _metadata (Dict[str, StrategyMetadata]): Strategy metadata by name.
    """
    
    _instance: Optional['StrategyRegistry'] = None
    
    def __new__(cls):
        """Create or return the singleton instance of the registry."""
        if cls._instance is None:
            cls._instance = super(StrategyRegistry, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the strategy registry."""
        if self._initialized:
            return
            
        self._strategies: Dict[str, Type[Strategy]] = {}
        self._metadata: Dict[str, StrategyMetadata] = {}
        self._initialized = True
        
        logger.info("Strategy registry initialized")
    
    def register_strategy(self, 
                        strategy_class: Type[Strategy], 
                        metadata: StrategyMetadata = None) -> None:
        """Register a strategy class with the registry.
        
        Args:
            strategy_class (Type[Strategy]): The strategy class to register.
            metadata (StrategyMetadata): Metadata for the strategy.
            
        Raises:
            ValueError: If a strategy with the same name is already registered.
        """
        strategy_name = strategy_class.__name__
        
        if strategy_name in self._strategies:
            raise ValueError(f"Strategy '{strategy_name}' is already registered")
        
        # Extract metadata from class docstring if not provided
        if metadata is None:
            metadata = self._extract_metadata_from_class(strategy_class)
        
        self._strategies[strategy_name] = strategy_class
        self._metadata[strategy_name] = metadata
        
        logger.info(f"Strategy '{strategy_name}' registered")
    
    def unregister_strategy(self, strategy_name: str) -> None:
        """Unregister a strategy from the registry.
        
        Args:
            strategy_name (str): The name of the strategy to unregister.
            
        Raises:
            ValueError: If the strategy is not registered.
        """
        if strategy_name not in self._strategies:
            raise ValueError(f"Strategy '{strategy_name}' is not registered")
        
        del self._strategies[strategy_name]
        del self._metadata[strategy_name]
        
        logger.info(f"Strategy '{strategy_name}' unregistered")
    
    def get_strategy_class(self, strategy_name: str) -> Type[Strategy]:
        """Get a strategy class by name.
        
        Args:
            strategy_name (str): The name of the strategy.
            
        Returns:
            Type[Strategy]: The strategy class.
            
        Raises:
            ValueError: If the strategy is not registered.
        """
        if strategy_name not in self._strategies:
            raise ValueError(f"Strategy '{strategy_name}' is not registered")
        
        return self._strategies[strategy_name]
    
    def get_metadata(self, strategy_name: str) -> StrategyMetadata:
        """Get metadata for a strategy.
        
        Args:
            strategy_name (str): The name of the strategy.
            
        Returns:
            StrategyMetadata: The strategy metadata.
            
        Raises:
            ValueError: If the strategy is not registered.
        """
        if strategy_name not in self._metadata:
            raise ValueError(f"Strategy '{strategy_name}' is not registered")
        
        return self._metadata[strategy_name]
    
    def create_strategy(self, 
                      strategy_name: str, 
                      config: Union[StrategyConfig, Dict[str, Any]]) -> Strategy:
        """Create a strategy instance.
        
        Args:
            strategy_name (str): The name of the strategy.
            config (Union[StrategyConfig, Dict[str, Any]]): Configuration for the strategy.
            
        Returns:
            Strategy: The strategy instance.
            
        Raises:
            ValueError: If the strategy is not registered.
        """
        if strategy_name not in self._strategies:
            raise ValueError(f"Strategy '{strategy_name}' is not registered")
        
        strategy_class = self._strategies[strategy_name]
        
        # Convert dict to StrategyConfig if needed
        if isinstance(config, dict):
            config = StrategyConfig(**config)
        
        return strategy_class(config)
    
    def list_strategies(self, 
                       strategy_type: Optional[StrategyType] = None,
                       tags: Optional[List[str]] = None) -> List[str]:
        """List registered strategies.
        
        Args:
            strategy_type (StrategyType): Filter by strategy type.
            tags (List[str]): Filter by tags.
            
        Returns:
            List[str]: The names of registered strategies.
        """
        result = list(self._strategies.keys())
        
        # Filter by strategy type
        if strategy_type is not None:
            result = [name for name in result 
                     if self._metadata[name].strategy_type == strategy_type]
        
        # Filter by tags
        if tags is not None:
            result = [name for name in result 
                     if all(tag in self._metadata[name].tags for tag in tags)]
        
        return result
    
    def discover_strategies(self, package_path: str = 'advanced_trading.strategies') -> int:
        """Discover and register strategies in a package.
        
        This method recursively searches the specified package for strategy classes
        and registers them with the registry.
        
        Args:
            package_path (str): The path to the package to search.
            
        Returns:
            int: The number of strategies discovered and registered.
        """
        package = importlib.import_module(package_path)
        package_dir = os.path.dirname(package.__file__)
        
        count = 0
        
        # Walk through all modules in the package
        for _, name, is_pkg in pkgutil.iter_modules([package_dir]):
            full_name = f"{package_path}.{name}"
            
            # If it's a package, recursively discover strategies
            if is_pkg:
                count += self.discover_strategies(full_name)
            else:
                # Import the module
                try:
                    module = importlib.import_module(full_name)
                    
                    # Find all strategy classes in the module
                    for item_name, item in inspect.getmembers(module):
                        if (inspect.isclass(item) and 
                            issubclass(item, Strategy) and 
                            item != Strategy and
                            item_name not in self._strategies):
                            
                            # Skip abstract classes
                            if inspect.isabstract(item):
                                continue
                                
                            # Register the strategy
                            try:
                                self.register_strategy(item)
                                count += 1
                                logger.info(f"Discovered strategy '{item_name}' in {full_name}")
                            except Exception as e:
                                logger.warning(f"Failed to register strategy '{item_name}' from {full_name}: {str(e)}")
                                
                except Exception as e:
                    logger.warning(f"Error importing module {full_name}: {str(e)}")
        
        logger.info(f"Discovered {count} strategies in {package_path}")
        return count
    
    def get_strategy_info(self, strategy_name: str) -> Dict[str, Any]:
        """Get detailed information about a strategy.
        
        Args:
            strategy_name (str): The name of the strategy.
            
        Returns:
            Dict[str, Any]: Detailed information about the strategy.
            
        Raises:
            ValueError: If the strategy is not registered.
        """
        if strategy_name not in self._strategies:
            raise ValueError(f"Strategy '{strategy_name}' is not registered")
        
        strategy_class = self._strategies[strategy_name]
        metadata = self._metadata[strategy_name]
        
        # Get the source code if possible
        source_code = None
        try:
            source_code = inspect.getsource(strategy_class)
        except Exception:
            pass
        
        # Build the information dictionary
        info = {
            "name": strategy_name,
            "description": metadata.description,
            "type": metadata.strategy_type.value,
            "parameters": metadata.parameters,
            "required_data": metadata.required_data,
            "version": metadata.version,
            "author": metadata.author,
            "tags": metadata.tags,
            "performance_metrics": metadata.performance_metrics,
            "example_config": metadata.example_config,
            "module": strategy_class.__module__,
            "source_code": source_code
        }
        
        return info
    
    def _extract_metadata_from_class(self, strategy_class: Type[Strategy]) -> StrategyMetadata:
        """Extract metadata from a strategy class.
        
        Args:
            strategy_class (Type[Strategy]): The strategy class.
            
        Returns:
            StrategyMetadata: The extracted metadata.
        """
        # Default values
        name = strategy_class.__name__
        description = strategy_class.__doc__ or "No description available"
        strategy_type = StrategyType.CUSTOM
        parameters = {}
        required_data = []
        version = getattr(strategy_class, "version", "1.0.0")
        author = getattr(strategy_class, "author", "Instinct AI Team")
        tags = getattr(strategy_class, "tags", [])
        
        # Try to extract more information from docstring
        docstring = inspect.getdoc(strategy_class)
        if docstring:
            # Clean up and normalize the docstring
            docstring = docstring.strip()
            lines = docstring.split("\n")
            
            # First line is the short description
            if lines:
                description = lines[0].strip()
        
        # Look for class attributes with metadata
        if hasattr(strategy_class, "STRATEGY_TYPE") and isinstance(strategy_class.STRATEGY_TYPE, StrategyType):
            strategy_type = strategy_class.STRATEGY_TYPE
            
        if hasattr(strategy_class, "PARAMETERS") and isinstance(strategy_class.PARAMETERS, dict):
            parameters = strategy_class.PARAMETERS
            
        if hasattr(strategy_class, "REQUIRED_DATA") and isinstance(strategy_class.REQUIRED_DATA, list):
            required_data = strategy_class.REQUIRED_DATA
        
        # Look for initialization parameters
        init_params = {}
        if hasattr(strategy_class, "__init__"):
            sig = inspect.signature(strategy_class.__init__)
            for param_name, param in sig.parameters.items():
                if param_name not in ["self", "config"]:
                    init_params[param_name] = {
                        "type": str(param.annotation),
                        "default": None if param.default is inspect.Parameter.empty else param.default
                    }
        
        # Create and return the metadata
        return StrategyMetadata(
            name=name,
            description=description,
            strategy_type=strategy_type,
            parameters=parameters or init_params,
            required_data=required_data,
            version=version,
            author=author,
            tags=tags,
            performance_metrics={},
            example_config=None
        )


# Create a singleton instance of the registry
strategy_registry = StrategyRegistry() 