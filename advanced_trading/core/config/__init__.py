"""
Configuration Module

This module provides configuration management for the Instinct AI trading platform.
It includes functionality for loading, validating, and accessing configuration values.
"""

import os
import logging
from pathlib import Path
from .config_manager import (
    ConfigurationManager,
    get_config,
    set_config,
    load_config,
    save_config,
    config_manager
)

logger = logging.getLogger(__name__)

# Initialize configuration with default values
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'default_config.yaml')
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schemas')

# Initialize configuration if default config exists
if os.path.exists(DEFAULT_CONFIG_PATH):
    try:
        # Load schemas if they exist
        if os.path.exists(SCHEMA_PATH) and os.path.isdir(SCHEMA_PATH):
            for schema_file in Path(SCHEMA_PATH).glob('*.json'):
                try:
                    config_manager._load_schemas(SCHEMA_PATH)
                    logger.info(f"Loaded schemas from {SCHEMA_PATH}")
                    break  # Only need to load schemas once
                except Exception as e:
                    logger.error(f"Failed to load schemas: {e}")
        
        # Load default configuration
        config_manager.load_config(DEFAULT_CONFIG_PATH)
        logger.info(f"Loaded default configuration from {DEFAULT_CONFIG_PATH}")
    except Exception as e:
        logger.error(f"Failed to load default configuration: {e}")
else:
    logger.warning(f"Default configuration file not found: {DEFAULT_CONFIG_PATH}")

# Look for environment-specific configuration
ENV = os.environ.get('INSTINCT_ENVIRONMENT', 'development')
ENV_CONFIG_PATH = os.path.join(os.path.dirname(__file__), f'{ENV}_config.yaml')

if os.path.exists(ENV_CONFIG_PATH):
    try:
        config_manager.load_config(ENV_CONFIG_PATH)
        logger.info(f"Loaded environment-specific configuration from {ENV_CONFIG_PATH}")
    except Exception as e:
        logger.error(f"Failed to load environment-specific configuration: {e}")

# Export public API
__all__ = [
    'ConfigurationManager',
    'get_config',
    'set_config',
    'load_config',
    'save_config',
    'config_manager'
] 