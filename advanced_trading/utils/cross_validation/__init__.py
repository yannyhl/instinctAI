"""
Cross-Validation Module for Time Series Data
-------------------------------------------
This module provides advanced cross-validation utilities specifically designed for time series data,
with a focus on financial applications. It includes methods to prevent look-ahead bias and ensure
proper temporal validation of models.

The module implements:
1. TimeSeriesCV - Cross-validation for time series with various window types
2. Purged cross-validation - Prevent data leakage between train and test sets
3. Embargo periods - Simulate implementation delays in backtesting
4. Visualization utilities - Plot cross-validation schemes
"""

import logging

# Configure logger
logger = logging.getLogger(__name__)

# Import main classes and functions to expose at the module level
from advanced_trading.utils.cross_validation.time_series_cv import (
    TimeSeriesCV, 
    purged_cross_val_score, 
    plot_purged_cv_results
)

__all__ = [
    'TimeSeriesCV',
    'purged_cross_val_score',
    'plot_purged_cv_results'
]

logger.info("Cross-validation module loaded") 