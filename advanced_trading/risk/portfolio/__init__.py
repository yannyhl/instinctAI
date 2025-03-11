"""
Portfolio Risk Management

This module provides tools and utilities for managing risk at the portfolio level,
including performance metrics, correlation analysis, and portfolio allocation.

Portfolio risk management aims to optimize the risk-adjusted performance of the entire
portfolio by considering the interactions between positions and overall exposure.

Key components:
- PortfolioRiskController: Main controller for portfolio risk management
- Allocation: Tools for portfolio allocation and weighting
- Correlation: Analysis of correlations between assets
- Metrics: Calculation of portfolio performance and risk metrics
"""

from typing import Dict, List, Optional, Union, Callable, Any

# Import submodules
from .allocation import (
    calculate_equal_weights,
    calculate_risk_parity_weights,
    calculate_hrp_weights,
    calculate_minvar_weights,
    calculate_portfolio_weights,
    rebalance_portfolio,
    max_portfolio_exposure,
    optimal_portfolio_allocation
)

from .correlation import (
    calculate_correlation_matrix,
    detect_correlation_changes,
    identify_correlation_clusters,
    calculate_portfolio_diversification,
    calculate_beta
)

from .metrics import (
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown,
    calculate_value_at_risk as calculate_var,
    calculate_conditional_value_at_risk as calculate_cvar
)

# Import the controller
from .controller import PortfolioRiskController

# Public API
__all__ = [
    # Main controller
    'PortfolioRiskController',
    
    # Portfolio allocation
    'calculate_equal_weights',
    'calculate_risk_parity_weights',
    'calculate_hrp_weights',
    'calculate_minvar_weights',
    'calculate_portfolio_weights',
    'rebalance_portfolio',
    'max_portfolio_exposure',
    'optimal_portfolio_allocation',
    
    # Correlation analysis
    'calculate_correlation_matrix',
    'detect_correlation_changes',
    'identify_correlation_clusters',
    'calculate_portfolio_diversification',
    'calculate_beta',
    
    # Risk metrics
    'calculate_sharpe_ratio',
    'calculate_sortino_ratio',
    'calculate_max_drawdown',
    'calculate_var',
    'calculate_cvar',
]