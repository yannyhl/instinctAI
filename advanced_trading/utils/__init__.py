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
)

# Import key utilities to make them available at the package level
try:
    from .regime_detection import RegimeClassifier, detect_regime
    from .signal_processing import normalize_signals, generate_ensemble_signal, smooth_signal
    
    __all__ = [
        'RegimeClassifier',
        'detect_regime',
        'normalize_signals',
        'generate_ensemble_signal',
        'smooth_signal',
        'cross_validation',
        'signal_processing',
        'event_detection',
    ]
    
    logger.info("Advanced Trading Utilities module loaded")
    
except ImportError as e:
    logger.warning(f"Some utils components could not be imported: {e}")
    logger.warning("Utils package may not be fully functional")
    __all__ = [] 