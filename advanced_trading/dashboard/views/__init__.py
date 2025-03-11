"""
Dashboard Views

This module provides view components for the dashboard, organizing different
aspects of the trading system into visual representations and interactive
interfaces.

Each view focuses on a specific aspect of the system, such as system status,
portfolio management, market analysis, or strategy monitoring.
"""

# Import views
from .system_view import create_system_view
from .portfolio_view import create_portfolio_view
from .market_view import create_market_view
from .strategy_view import create_strategy_view
from .strategy_monitoring_view import create_strategy_monitoring_view
from .performance_dashboard_view import create_performance_dashboard_view

# Register view callbacks
from . import system_view
from . import portfolio_view
from . import market_view
from . import strategy_view
from . import strategy_monitoring_view
from . import performance_dashboard_view

__all__ = [
    "create_system_view",
    "create_portfolio_view",
    "create_market_view",
    "create_strategy_view",
    "create_strategy_monitoring_view",
    "create_performance_dashboard_view"
] 