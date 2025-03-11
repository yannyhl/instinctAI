"""
Dashboard Models

This module defines the data structures and models used by the execution dashboard.
These models include configuration settings, metrics definitions, and state representations
for the dashboard components.
"""

# Import specific model implementations
from advanced_trading.execution.dashboard.models.config import ExecutionDashboardConfig
from advanced_trading.execution.dashboard.models.metrics import ExecutionMetrics
from advanced_trading.execution.dashboard.models.state import DashboardState

# Public API
__all__ = [
    'ExecutionDashboardConfig',
    'ExecutionMetrics',
    'DashboardState'
] 