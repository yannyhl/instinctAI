"""
Dashboard Services

This module provides services that power the execution dashboard functionality.
These services handle data collection, state management, and interaction with
the underlying execution components.
"""

# Import specific service implementations
from advanced_trading.execution.dashboard.services.metrics_collector import MetricsCollector
from advanced_trading.execution.dashboard.services.dashboard_data import DashboardDataService
from advanced_trading.execution.dashboard.services.execution_controller import ExecutionController

# Public API
__all__ = [
    'MetricsCollector',
    'DashboardDataService',
    'ExecutionController'
] 