"""
Backtesting Engine Module
-----------------------
This module provides the core components for backtesting trading strategies.

Key components:
1. WalkForwardTest - Framework for walk-forward optimization and testing
2. TimeSeriesCV Integration - Proper temporal validation of trading strategies
3. Performance Evaluation - Accurate measurement of strategy performance
"""

import logging

# Configure logger
logger = logging.getLogger(__name__)

# Import core components
try:
    from advanced_trading.backtesting.engine.walk_forward import WalkForwardTest
    
    __all__ = [
        'WalkForwardTest',
    ]
    
    logger.info("Backtesting Engine module loaded successfully")
except ImportError as e:
    logger.error(f"Error loading backtesting engine module: {e}")
    
    # Define minimal API to prevent errors
    __all__ = [] 