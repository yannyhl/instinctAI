"""
Component Registry

This module provides a registry for system components, allowing them to be
registered, retrieved, and managed throughout the application lifecycle.
"""

import logging
import threading
from typing import Dict, Any, Optional, List, Callable, Type, Union

# Configure logging
logger = logging.getLogger(__name__)

# Global registry instance
_registry = None
_registry_lock = threading.RLock()


class ComponentRegistry:
    """
    Registry for system components.
    
    Provides a centralized registry for components, allowing them to be
    registered, retrieved, and managed throughout the application lifecycle.
    """
    
    def __init__(self):
        """Initialize the component registry."""
        self._components = {}
        self._factories = {}
        self._dependencies = {}
        self._initialized = set()
        self._lock = threading.RLock()
    
    def register(self, name: str, component: Any, dependencies: List[str] = None) -> None:
        """
        Register a component.
        
        Args:
            name: Component name
            component: Component instance
            dependencies: List of component names this component depends on
        """
        with self._lock:
            if name in self._components:
                logger.warning(f"Component '{name}' already registered, replacing")
            
            self._components[name] = component
            self._dependencies[name] = dependencies or []
            
            logger.debug(f"Component '{name}' registered")
    
    def register_factory(self, name: str, factory: Callable, dependencies: List[str] = None) -> None:
        """
        Register a component factory.
        
        Args:
            name: Component name
            factory: Factory function to create the component
            dependencies: List of component names this component depends on
        """
        with self._lock:
            if name in self._factories:
                logger.warning(f"Factory for '{name}' already registered, replacing")
            
            self._factories[name] = factory
            self._dependencies[name] = dependencies or []
            
            logger.debug(f"Factory for '{name}' registered")
    
    def get(self, name: str, initialize: bool = True) -> Any:
        """
        Get a component by name.
        
        Args:
            name: Component name
            initialize: Whether to initialize the component if it's not already initialized
            
        Returns:
            Component instance
            
        Raises:
            KeyError: If the component is not registered
        """
        with self._lock:
            # Check if component is already instantiated
            if name in self._components:
                return self._components[name]
            
            # Check if we have a factory for this component
            if name in self._factories:
                if initialize:
                    return self._initialize_component(name)
                else:
                    raise KeyError(f"Component '{name}' is not initialized")
            
            raise KeyError(f"Component '{name}' is not registered")
    
    def _initialize_component(self, name: str) -> Any:
        """
        Initialize a component using its factory.
        
        Args:
            name: Component name
            
        Returns:
            Initialized component
            
        Raises:
            KeyError: If the component or its dependencies are not registered
            RuntimeError: If there is a circular dependency
        """
        # Check for circular dependencies
        if name in self._initialized:
            raise RuntimeError(f"Circular dependency detected for '{name}'")
        
        self._initialized.add(name)
        
        # Initialize dependencies first
        dependencies = {}
        for dep_name in self._dependencies.get(name, []):
            if dep_name not in self._components:
                if dep_name not in self._factories:
                    raise KeyError(f"Dependency '{dep_name}' for '{name}' is not registered")
                
                # Initialize dependency
                dependencies[dep_name] = self._initialize_component(dep_name)
            else:
                dependencies[dep_name] = self._components[dep_name]
        
        # Initialize component
        factory = self._factories[name]
        try:
            component = factory(**dependencies)
            self._components[name] = component
            logger.debug(f"Component '{name}' initialized")
            return component
        except Exception as e:
            logger.error(f"Error initializing component '{name}': {str(e)}")
            raise
        finally:
            self._initialized.remove(name)
    
    def initialize_all(self) -> None:
        """
        Initialize all registered components.
        
        Raises:
            RuntimeError: If there is an error initializing any component
        """
        with self._lock:
            # Get all component names
            names = list(self._factories.keys())
            
            # Initialize each component
            for name in names:
                if name not in self._components:
                    try:
                        self._initialize_component(name)
                    except Exception as e:
                        logger.error(f"Error initializing component '{name}': {str(e)}")
                        raise RuntimeError(f"Error initializing component '{name}'") from e
    
    def list(self) -> List[str]:
        """
        List all registered components.
        
        Returns:
            List of component names
        """
        with self._lock:
            # Get all registered components (both instantiated and factories)
            return list(set(list(self._components.keys()) + list(self._factories.keys())))
    
    def clear(self) -> None:
        """Clear all registered components."""
        with self._lock:
            self._components = {}
            self._factories = {}
            self._dependencies = {}
            self._initialized = set()
            
            logger.debug("Component registry cleared")


def get_registry() -> ComponentRegistry:
    """
    Get the global component registry.
    
    Returns:
        Global component registry instance
    """
    global _registry
    
    with _registry_lock:
        if _registry is None:
            _registry = ComponentRegistry()
    
    return _registry


def register_component(name: str, component: Any, dependencies: List[str] = None) -> None:
    """
    Register a component in the global registry.
    
    Args:
        name: Component name
        component: Component instance
        dependencies: List of component names this component depends on
    """
    registry = get_registry()
    registry.register(name, component, dependencies)


def register_component_factory(name: str, factory: Callable, dependencies: List[str] = None) -> None:
    """
    Register a component factory in the global registry.
    
    Args:
        name: Component name
        factory: Factory function to create the component
        dependencies: List of component names this component depends on
    """
    registry = get_registry()
    registry.register_factory(name, factory, dependencies)


def get_component(name: str, initialize: bool = True) -> Any:
    """
    Get a component from the global registry.
    
    Args:
        name: Component name
        initialize: Whether to initialize the component if it's not already initialized
        
    Returns:
        Component instance
        
    Raises:
        KeyError: If the component is not registered
    """
    registry = get_registry()
    return registry.get(name, initialize)


def list_components() -> List[str]:
    """
    List all components in the global registry.
    
    Returns:
        List of component names
    """
    registry = get_registry()
    return registry.list()


def clear_registry() -> None:
    """Clear the global component registry."""
    registry = get_registry()
    registry.clear() 