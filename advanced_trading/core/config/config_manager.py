"""
Configuration Manager

This module provides a comprehensive configuration management system for the Instinct AI trading platform.
It supports:
- Hierarchical configuration with inheritance
- Environment-specific overrides
- Dynamic configuration updates
- Schema validation for configuration values
- Default value management
"""

import os
import json
import yaml
import logging
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
import jsonschema
from copy import deepcopy
from threading import RLock

logger = logging.getLogger(__name__)

class ConfigurationManager:
    """
    Manages configuration for the Instinct AI trading platform.
    
    This class provides a centralized configuration system with support for:
    - Loading configuration from multiple sources (YAML, JSON, environment variables)
    - Environment-specific configuration overrides
    - Dynamic configuration updates
    - Configuration validation against schemas
    - Default values for missing configuration
    
    Example:
        config_manager = ConfigurationManager()
        config_manager.load_config('config.yaml')
        db_config = config_manager.get('database')
        api_key = config_manager.get('api.credentials.key')
    """
    
    def __init__(self, 
                 base_config_path: Optional[str] = None,
                 env_prefix: str = "INSTINCT_",
                 schema_path: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            base_config_path: Path to the base configuration file
            env_prefix: Prefix for environment variables to be included in configuration
            schema_path: Path to the schema directory for configuration validation
        """
        self._config = {}
        self._schemas = {}
        self._env_prefix = env_prefix
        self._lock = RLock()
        
        # Load schema files if path is provided
        if schema_path:
            self._load_schemas(schema_path)
            
        # Load base configuration if provided
        if base_config_path:
            self.load_config(base_config_path)
            
        # Load environment-specific configuration
        self._load_environment_overrides()
    
    def load_config(self, config_path: str) -> None:
        """
        Load configuration from a file.
        
        Args:
            config_path: Path to the configuration file (YAML or JSON)
        
        Raises:
            FileNotFoundError: If the configuration file does not exist
            ValueError: If the configuration file format is not supported
        """
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(path, 'r') as f:
            if path.suffix.lower() in ['.yaml', '.yml']:
                config_data = yaml.safe_load(f)
            elif path.suffix.lower() == '.json':
                config_data = json.load(f)
            else:
                raise ValueError(f"Unsupported configuration file format: {path.suffix}")
        
        with self._lock:
            self._update_config_recursive(self._config, config_data)
            
        logger.info(f"Loaded configuration from {config_path}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value by its key path.
        
        Args:
            key_path: Dot-separated path to the configuration value
            default: Default value to return if the key does not exist
            
        Returns:
            The configuration value or the default value if not found
        """
        keys = key_path.split('.')
        
        with self._lock:
            current = self._config
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    return default
                    
        return current
    
    def set(self, key_path: str, value: Any, validate: bool = True) -> None:
        """
        Set a configuration value by its key path.
        
        Args:
            key_path: Dot-separated path to the configuration value
            value: Value to set
            validate: Whether to validate the configuration after setting
            
        Raises:
            ValueError: If validation fails
        """
        keys = key_path.split('.')
        
        with self._lock:
            current = self._config
            for i, key in enumerate(keys[:-1]):
                if key not in current:
                    current[key] = {}
                current = current[key]
                
            current[keys[-1]] = value
            
            if validate:
                self._validate_config()
                
        logger.debug(f"Set configuration value for {key_path}")
    
    def update(self, config_dict: Dict[str, Any], validate: bool = True) -> None:
        """
        Update the configuration with a dictionary.
        
        Args:
            config_dict: Dictionary containing configuration values
            validate: Whether to validate the configuration after updating
            
        Raises:
            ValueError: If validation fails
        """
        with self._lock:
            self._update_config_recursive(self._config, config_dict)
            
            if validate:
                self._validate_config()
                
        logger.debug("Updated configuration with dictionary")
    
    def save_config(self, config_path: str) -> None:
        """
        Save the current configuration to a file.
        
        Args:
            config_path: Path to save the configuration file
            
        Raises:
            ValueError: If the file format is not supported
        """
        path = Path(config_path)
        
        with self._lock:
            config_copy = deepcopy(self._config)
        
        with open(path, 'w') as f:
            if path.suffix.lower() in ['.yaml', '.yml']:
                yaml.dump(config_copy, f, default_flow_style=False)
            elif path.suffix.lower() == '.json':
                json.dump(config_copy, f, indent=2)
            else:
                raise ValueError(f"Unsupported configuration file format: {path.suffix}")
                
        logger.info(f"Saved configuration to {config_path}")
    
    def register_schema(self, schema_name: str, schema: Dict[str, Any]) -> None:
        """
        Register a JSON schema for configuration validation.
        
        Args:
            schema_name: Name of the schema
            schema: JSON schema dictionary
        """
        with self._lock:
            self._schemas[schema_name] = schema
            
        logger.debug(f"Registered schema: {schema_name}")
    
    def validate_against_schema(self, schema_name: str, config_section: Optional[str] = None) -> bool:
        """
        Validate a section of the configuration against a schema.
        
        Args:
            schema_name: Name of the schema to validate against
            config_section: Section of the configuration to validate (None for entire config)
            
        Returns:
            True if validation succeeds, False otherwise
            
        Raises:
            ValueError: If the schema does not exist
        """
        if schema_name not in self._schemas:
            raise ValueError(f"Schema not found: {schema_name}")
        
        with self._lock:
            if config_section:
                config_to_validate = self.get(config_section, {})
            else:
                config_to_validate = deepcopy(self._config)
        
        try:
            jsonschema.validate(instance=config_to_validate, schema=self._schemas[schema_name])
            return True
        except jsonschema.exceptions.ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
    
    def _load_schemas(self, schema_path: str) -> None:
        """
        Load JSON schemas from a directory.
        
        Args:
            schema_path: Path to the schema directory
        """
        path = Path(schema_path)
        if not path.exists() or not path.is_dir():
            logger.warning(f"Schema directory not found: {schema_path}")
            return
        
        for schema_file in path.glob('*.json'):
            try:
                with open(schema_file, 'r') as f:
                    schema = json.load(f)
                    schema_name = schema_file.stem
                    self.register_schema(schema_name, schema)
            except Exception as e:
                logger.error(f"Failed to load schema {schema_file}: {e}")
    
    def _load_environment_overrides(self) -> None:
        """
        Load configuration overrides from environment variables.
        
        Environment variables with the specified prefix are converted to configuration values.
        For example, INSTINCT_DATABASE_HOST becomes database.host in the configuration.
        """
        env_vars = {k: v for k, v in os.environ.items() if k.startswith(self._env_prefix)}
        
        for env_var, value in env_vars.items():
            # Remove prefix and convert to lowercase
            key = env_var[len(self._env_prefix):].lower()
            
            # Convert to nested dictionary keys
            key_path = key.replace('__', '.')
            
            # Try to parse as JSON, otherwise use as string
            try:
                parsed_value = json.loads(value)
            except json.JSONDecodeError:
                parsed_value = value
                
            self.set(key_path, parsed_value, validate=False)
            
        logger.debug(f"Loaded {len(env_vars)} configuration values from environment variables")
    
    def _update_config_recursive(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """
        Recursively update a nested dictionary.
        
        Args:
            target: Target dictionary to update
            source: Source dictionary with updates
        """
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._update_config_recursive(target[key], value)
            else:
                target[key] = value
    
    def _validate_config(self) -> None:
        """
        Validate the entire configuration against all registered schemas.
        
        Raises:
            ValueError: If validation fails
        """
        for schema_name, schema in self._schemas.items():
            if not self.validate_against_schema(schema_name):
                raise ValueError(f"Configuration validation failed for schema: {schema_name}")


# Create a singleton instance
config_manager = ConfigurationManager()

def get_config(key_path: str, default: Any = None) -> Any:
    """
    Get a configuration value by its key path.
    
    This is a convenience function that uses the singleton ConfigurationManager instance.
    
    Args:
        key_path: Dot-separated path to the configuration value
        default: Default value to return if the key does not exist
        
    Returns:
        The configuration value or the default value if not found
    """
    return config_manager.get(key_path, default)

def set_config(key_path: str, value: Any, validate: bool = True) -> None:
    """
    Set a configuration value by its key path.
    
    This is a convenience function that uses the singleton ConfigurationManager instance.
    
    Args:
        key_path: Dot-separated path to the configuration value
        value: Value to set
        validate: Whether to validate the configuration after setting
        
    Raises:
        ValueError: If validation fails
    """
    config_manager.set(key_path, value, validate)

def load_config(config_path: str) -> None:
    """
    Load configuration from a file.
    
    This is a convenience function that uses the singleton ConfigurationManager instance.
    
    Args:
        config_path: Path to the configuration file (YAML or JSON)
        
    Raises:
        FileNotFoundError: If the configuration file does not exist
        ValueError: If the configuration file format is not supported
    """
    config_manager.load_config(config_path)

def save_config(config_path: str) -> None:
    """
    Save the current configuration to a file.
    
    This is a convenience function that uses the singleton ConfigurationManager instance.
    
    Args:
        config_path: Path to save the configuration file
        
    Raises:
        ValueError: If the file format is not supported
    """
    config_manager.save_config(config_path) 