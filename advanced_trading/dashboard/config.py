"""
Dashboard Configuration

This module provides configuration utilities for the dashboard.
"""

import os
import sys
import logging
from typing import Dict, Any, Optional, List, Union
import yaml

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import core modules
from core import config_manager
from core.common.validators import validate_string_choice, validate_numeric_range

# Configure logging
logger = logging.getLogger(__name__)

# Default dashboard configuration
DEFAULT_CONFIG = {
    "enabled": True,
    "host": "0.0.0.0",
    "port": 8050,
    "debug": False,
    "theme": "light",
    "refresh_intervals": {
        "fast": 1000,    # 1 second
        "medium": 5000,  # 5 seconds
        "slow": 30000,   # 30 seconds
    },
    "cache_timeout": 60,  # 60 seconds
    "max_items": {
        "logs": 100,
        "trades": 50,
        "positions": 100,
        "signals": 30,
    },
    "views": {
        "system": {
            "enabled": True,
            "metrics_history_length": 100,
        },
        "portfolio": {
            "enabled": True,
            "default_timeframe": "1m",
        },
        "market": {
            "enabled": True,
            "default_symbol": "BTC/USD",
            "default_timeframe": "1h",
        },
        "strategy": {
            "enabled": True,
            "backtest_max_days": 365,
        }
    }
}


def get_dashboard_config() -> Dict[str, Any]:
    """
    Get the dashboard configuration.
    
    Returns:
        Dashboard configuration dictionary
    """
    # Get dashboard configuration from core config manager
    config = config_manager.get_config().get("dashboard", {})
    
    # Merge with default configuration
    merged_config = _deep_merge(DEFAULT_CONFIG, config)
    
    # Validate configuration
    _validate_config(merged_config)
    
    return merged_config


def _deep_merge(default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries, with override values taking precedence.
    
    Args:
        default: Default dictionary
        override: Override dictionary with values to apply
        
    Returns:
        Merged dictionary
    """
    result = default.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
            
    return result


def _validate_config(config: Dict[str, Any]) -> None:
    """
    Validate the dashboard configuration.
    
    Args:
        config: Configuration dictionary to validate
    """
    # Validate basic settings
    if not isinstance(config.get("enabled"), bool):
        logger.warning("Invalid 'enabled' setting, using default: True")
        config["enabled"] = True
        
    if not isinstance(config.get("host"), str):
        logger.warning("Invalid 'host' setting, using default: 0.0.0.0")
        config["host"] = "0.0.0.0"
        
    if not validate_numeric_range(config.get("port", 0), 1, 65535):
        logger.warning("Invalid 'port' setting, using default: 8050")
        config["port"] = 8050
        
    if not isinstance(config.get("debug"), bool):
        logger.warning("Invalid 'debug' setting, using default: False")
        config["debug"] = False
        
    if not validate_string_choice(config.get("theme", ""), ["light", "dark"]):
        logger.warning("Invalid 'theme' setting, using default: light")
        config["theme"] = "light"
        
    # Validate refresh intervals
    if not isinstance(config.get("refresh_intervals", {}), dict):
        logger.warning("Invalid 'refresh_intervals' setting, using defaults")
        config["refresh_intervals"] = DEFAULT_CONFIG["refresh_intervals"]
    else:
        for interval in ["fast", "medium", "slow"]:
            if not validate_numeric_range(config["refresh_intervals"].get(interval, 0), 100, 3600000):
                logger.warning(f"Invalid '{interval}' refresh interval, using default")
                config["refresh_intervals"][interval] = DEFAULT_CONFIG["refresh_intervals"][interval]
                
    # Validate max items
    if not isinstance(config.get("max_items", {}), dict):
        logger.warning("Invalid 'max_items' setting, using defaults")
        config["max_items"] = DEFAULT_CONFIG["max_items"]
    else:
        for item in ["logs", "trades", "positions", "signals"]:
            if not validate_numeric_range(config["max_items"].get(item, 0), 1, 1000):
                logger.warning(f"Invalid '{item}' max items setting, using default")
                config["max_items"][item] = DEFAULT_CONFIG["max_items"][item]
                
    # Validate views
    if not isinstance(config.get("views", {}), dict):
        logger.warning("Invalid 'views' setting, using defaults")
        config["views"] = DEFAULT_CONFIG["views"]
    else:
        for view in ["system", "portfolio", "market", "strategy"]:
            if view not in config["views"] or not isinstance(config["views"][view], dict):
                logger.warning(f"Invalid '{view}' view setting, using default")
                config["views"][view] = DEFAULT_CONFIG["views"][view]
            elif not isinstance(config["views"][view].get("enabled"), bool):
                logger.warning(f"Invalid '{view}.enabled' setting, using default")
                config["views"][view]["enabled"] = DEFAULT_CONFIG["views"][view]["enabled"]


def save_dashboard_config(config: Dict[str, Any]) -> bool:
    """
    Save dashboard configuration to the core configuration.
    
    Args:
        config: Dashboard configuration to save
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Validate configuration
        _validate_config(config)
        
        # Get the main configuration
        main_config = config_manager.get_config()
        
        # Update dashboard section
        main_config["dashboard"] = config
        
        # Save configuration
        return config_manager.save_config(main_config)
    except Exception as e:
        logger.error(f"Error saving dashboard configuration: {str(e)}")
        return False


def get_view_config(view_name: str) -> Dict[str, Any]:
    """
    Get configuration for a specific view.
    
    Args:
        view_name: Name of the view
        
    Returns:
        View configuration dictionary
    """
    config = get_dashboard_config()
    return config.get("views", {}).get(view_name, {}) 