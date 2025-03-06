"""
Position Risk Management

This module provides tools and utilities for managing risk at the individual position level,
including position sizing, stop loss calculation, and risk limits.

Position sizing determines the appropriate size of a position based on risk parameters,
account size, and market conditions.
"""

from typing import Dict, List, Optional, Union, Callable, Any

# Import submodules
from .sizing import (
    calculate_position_size, max_position_size, 
    optimal_position_size, adjust_position_size,
    PositionSizingEngine
)
from .stops import (
    calculate_stop_loss, trailing_stop, 
    volatility_based_stop, time_based_stop,
    StopManager
)
from .limits import (
    calculate_risk_limit, validate_position_risk, 
    position_risk_metrics, position_exposure
)

# Public API
__all__ = [
    # Position sizing
    'calculate_position_size', 'max_position_size',
    'optimal_position_size', 'adjust_position_size',
    'PositionSizingEngine',
    
    # Stop management
    'calculate_stop_loss', 'trailing_stop',
    'volatility_based_stop', 'time_based_stop',
    'StopManager',
    
    # Risk limits
    'calculate_risk_limit', 'validate_position_risk',
    'position_risk_metrics', 'position_exposure',
] 