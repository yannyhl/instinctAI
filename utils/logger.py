"""
Logger Module
------------
Provides centralized logging configuration for InstinctAI
"""

import logging
import os
from pathlib import Path

import config

def setup_logger(name, log_file=None, level=None):
    """
    Set up a logger with specified name, file, and level
    
    Args:
        name: Name of the logger
        log_file: Path to log file (optional)
        level: Logging level (optional)
        
    Returns:
        Logger instance
    """
    # Get configuration
    if level is None:
        level = config.LOGGING_CONFIG['level']
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(config.LOGGING_CONFIG['format'])
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Add file handler if log_file is specified
    if log_file:
        # Ensure log directory exists
        log_dir = Path(log_file).parent
        os.makedirs(log_dir, exist_ok=True)
        
        # Create file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

def get_logger(name):
    """
    Get a logger with default settings
    
    Args:
        name: Name of the logger
        
    Returns:
        Logger instance
    """
    # Get default log file from config
    default_log_file = config.LOGGING_CONFIG['file_handler']['filename']
    
    return setup_logger(name, default_log_file)