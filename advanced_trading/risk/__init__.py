"""
Risk Management Module

This module provides tools and utilities for managing risk across different levels
of the trading system:

- Position Risk: Tools for managing risk at the individual position level
- Portfolio Risk: Tools for managing risk at the portfolio level
- Market Risk: Tools for assessing and managing market-wide risks

The risk module integrates with the execution and strategy modules to enforce
risk limits and implement risk management strategies.
"""

# Import public API from submodules
from advanced_trading.risk.position import (
    calculate_position_size,
    max_position_size,
    optimal_position_size,
    adjust_position_size,
    PositionSizingEngine,
    calculate_stop_loss,
    volatility_based_stop,
    trailing_stop,
    time_based_stop,
    StopManager
)

from advanced_trading.risk.portfolio import (
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown,
    calculate_var,
    calculate_cvar
)

from advanced_trading.risk.market import (
    calculate_market_volatility,
    calculate_correlation_matrix,
    identify_market_regime,
    calculate_systemic_risk,
    get_risk_factors
)

# Define public API
__all__ = [
    # Position risk functions
    "calculate_position_size",
    "max_position_size",
    "optimal_position_size",
    "adjust_position_size",
    "PositionSizingEngine",
    "calculate_stop_loss",
    "volatility_based_stop",
    "trailing_stop",
    "time_based_stop",
    "StopManager",
    
    # Portfolio risk functions
    "calculate_sharpe_ratio",
    "calculate_sortino_ratio",
    "calculate_max_drawdown",
    "calculate_var",
    "calculate_cvar",
    
    # Market risk functions
    "calculate_market_volatility",
    "calculate_correlation_matrix",
    "identify_market_regime",
    "calculate_systemic_risk",
    "get_risk_factors"
]

__version__ = '0.1.0' 