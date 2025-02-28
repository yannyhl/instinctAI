#!/usr/bin/env python3
"""
Data Manager Module
------------------
Helper module for initializing and configuring the market data handler
with caching and other optimization features.
"""

import os
import sys
import logging
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
import threading

# Add parent directory to path if needed
script_dir = Path(__file__).resolve().parent.parent
if script_dir not in sys.path:
    sys.path.append(str(script_dir))

# Import market monitor and data handler
from utils.market_monitor import MarketMonitor
from dashboard.market_data_handler import MarketDataHandler

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables
_market_monitor = None
_market_data_handler = None
_monitor_lock = threading.Lock()
_handler_lock = threading.Lock()

# Default configuration
DEFAULT_CONFIG = {
    "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT", "AVAX/USDT", "XRP/USDT"],
    "timeframes": ["1m", "5m", "15m", "1h", "4h", "1d"],
    "update_interval": 60,  # seconds
    "cache_dir": "data/cache",
    "strategy_ids": ["momentum_eth", "trend_follower", "mean_reversion", "breakout"],
    "cache_ttl": {
        "market_overview": 300,  # 5 minutes
        "price_data": 120,      # 2 minutes
        "volume_profile": 600,   # 10 minutes
        "correlation": 1800,     # 30 minutes
        "performance": 300,      # 5 minutes
        "regimes": 900,          # 15 minutes
        "alerts": 60             # 1 minute
    }
}

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from a JSON file or use defaults.
    
    Args:
        config_path: Path to the configuration file (optional)
        
    Returns:
        Dict containing configuration settings
    """
    config = DEFAULT_CONFIG.copy()
    
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                
            # Merge user config with defaults
            for key, value in user_config.items():
                if key in config and isinstance(config[key], dict) and isinstance(value, dict):
                    # For nested dicts like cache_ttl, merge instead of replace
                    config[key].update(value)
                else:
                    config[key] = value
                
            logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.error(f"Error loading configuration from {config_path}: {str(e)}")
            logger.warning("Using default configuration instead")
    else:
        logger.info("Using default configuration")
    
    return config

def init_market_monitor(config: Optional[Dict[str, Any]] = None) -> MarketMonitor:
    """
    Initialize or get the market monitor instance.
    
    Args:
        config: Configuration dictionary (optional)
        
    Returns:
        MarketMonitor instance
    """
    global _market_monitor
    
    with _monitor_lock:
        if _market_monitor is None:
            if config is None:
                config = load_config()
                
            logger.info("Initializing MarketMonitor...")
            
            # Create cache directory if it doesn't exist
            os.makedirs(config.get("cache_dir", "data/cache"), exist_ok=True)
            
            # Initialize MarketMonitor
            try:
                _market_monitor = MarketMonitor(
                    symbols=config.get("symbols", ["BTC/USDT", "ETH/USDT"]),
                    timeframes=config.get("timeframes", ["5m", "1h", "1d"]),
                    update_interval=config.get("update_interval", 60),
                    cache_dir=config.get("cache_dir", "data/cache")
                )
                
                # Start the monitor
                _market_monitor.start()
                logger.info("MarketMonitor started successfully")
            except Exception as e:
                logger.error(f"Error initializing MarketMonitor: {str(e)}")
                raise
    
    return _market_monitor

def get_market_data_handler(config: Optional[Dict[str, Any]] = None) -> MarketDataHandler:
    """
    Get or initialize the market data handler instance.
    
    Args:
        config: Configuration dictionary (optional)
        
    Returns:
        MarketDataHandler instance
    """
    global _market_data_handler
    
    with _handler_lock:
        if _market_data_handler is None:
            if config is None:
                config = load_config()
                
            logger.info("Initializing MarketDataHandler...")
            
            # Ensure market monitor is initialized
            monitor = init_market_monitor(config)
            
            # Initialize MarketDataHandler
            try:
                _market_data_handler = MarketDataHandler(
                    market_monitor=monitor,
                    strategy_ids=config.get("strategy_ids", ["momentum_eth", "trend_follower"]),
                    cache_ttl=config.get("cache_ttl", DEFAULT_CONFIG["cache_ttl"])
                )
                logger.info("MarketDataHandler initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing MarketDataHandler: {str(e)}")
                raise
    
    return _market_data_handler

def shutdown_market_monitor():
    """Safely shut down the market monitor."""
    global _market_monitor
    
    with _monitor_lock:
        if _market_monitor is not None:
            try:
                logger.info("Shutting down MarketMonitor...")
                _market_monitor.stop()
                logger.info("MarketMonitor stopped successfully")
            except Exception as e:
                logger.error(f"Error shutting down MarketMonitor: {str(e)}")
            
            _market_monitor = None

def get_available_symbols() -> List[str]:
    """
    Get a list of available trading symbols.
    
    Returns:
        List of symbol strings
    """
    monitor = init_market_monitor()
    return monitor.symbols

def get_available_timeframes() -> List[str]:
    """
    Get a list of available timeframes.
    
    Returns:
        List of timeframe strings
    """
    monitor = init_market_monitor()
    return monitor.timeframes

def get_available_strategies() -> List[str]:
    """
    Get a list of available strategy IDs.
    
    Returns:
        List of strategy ID strings
    """
    handler = get_market_data_handler()
    return handler.strategy_ids

def register_shutdown_handler():
    """Register shutdown handler to ensure market monitor is stopped when the program exits."""
    import atexit
    atexit.register(shutdown_market_monitor)
    
    # Also handle signals
    try:
        import signal
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, lambda s, f: shutdown_market_monitor())
    except (ImportError, AttributeError):
        # Signal handling may not be available on all platforms
        pass
    
    logger.info("Registered shutdown handlers")

# Register shutdown handler when the module is imported
register_shutdown_handler() 