"""
Backtesting Module
-----------------
This module provides a comprehensive framework for backtesting trading strategies 
with advanced features for accurate performance evaluation and strategy validation.

Key components:
1. Engine - Core backtesting functionality including walk-forward testing
2. Analysis - Tools for analyzing backtest results
3. Performance - Metrics for evaluating strategy performance
4. Visualization - Tools for visualizing backtest results
5. Reporting - Generating reports from backtest results
"""

import logging

# Configure logger
logger = logging.getLogger(__name__)

# Import key components
try:
    # Engine components
    from advanced_trading.backtesting.engine.walk_forward import WalkForwardTest
    
    # Import analysis components if available
    try:
        from advanced_trading.backtesting.analysis import performance_metrics
    except ImportError:
        logger.warning("Performance metrics module not found. Some functionality may be limited.")
    
    __all__ = [
        'WalkForwardTest',
    ]
    
    logger.info("Backtesting module loaded successfully")
except ImportError as e:
    logger.error(f"Error loading backtesting module: {e}")
    
    # Define minimal API to prevent errors
    __all__ = []

# Version information
__version__ = '0.1.0' 