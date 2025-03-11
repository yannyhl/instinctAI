"""
Advanced Trading Utilities
-------------------------
This module provides utility functions and classes for the Advanced Trading system.

Modules:
- cross_validation: Time series cross-validation for backtesting
- signal_processing: Signal filtering and processing utilities
- event_detection: Market event identification and analysis
- regime_detection: Market regime classification
- technical_indicators: Technical analysis indicators
- statistical_tests: Statistical tests for financial time series
- data_preprocessing: Data cleaning and preparation
- metrics: Performance and risk metrics
- visualization: Plotting and visualization utilities
"""

import logging
from typing import Dict, List, Any, Optional, Union, Tuple

# Configure logger
logger = logging.getLogger(__name__)

# Import and expose key modules
from advanced_trading.utils import (
    cross_validation,
    signal_processing,
    event_detection,
    technical_indicators,
    statistical_tests,
)

# Import key utilities to make them available at the package level
try:
    from .regime_detection import RegimeClassifier, detect_regime
    from .signal_processing import normalize_signals, generate_ensemble_signal, smooth_signal
    from .statistical_tests import (
        stationarity_analysis, 
        normality_analysis, 
        cointegration_analysis,
        causality_analysis,
        time_series_diagnostics
    )
    from .data_preprocessing import (
        handle_missing_values,
        handle_outliers,
        normalize_data,
        apply_log_transform,
        apply_box_cox_transform,
        apply_differencing,
        create_lag_features,
        create_rolling_features,
        extract_date_features,
        split_time_series_data
    )
    
    __all__ = [
        'RegimeClassifier',
        'detect_regime',
        'normalize_signals',
        'generate_ensemble_signal',
        'smooth_signal',
        'stationarity_analysis',
        'normality_analysis',
        'cointegration_analysis',
        'causality_analysis',
        'time_series_diagnostics',
        'handle_missing_values',
        'handle_outliers',
        'normalize_data',
        'apply_log_transform',
        'apply_box_cox_transform',
        'apply_differencing',
        'create_lag_features',
        'create_rolling_features',
        'extract_date_features',
        'split_time_series_data',
        'cross_validation',
        'signal_processing',
        'event_detection',
        'technical_indicators',
        'statistical_tests',
    ]
    
    logger.info("Advanced Trading Utilities module loaded")
    
except ImportError as e:
    logger.warning(f"Some utils components could not be imported: {e}")
    logger.warning("Utils package may not be fully functional")
    __all__ = [] 