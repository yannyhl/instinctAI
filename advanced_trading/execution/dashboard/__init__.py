"""
Execution Dashboard

This module provides a unified dashboard for monitoring and controlling execution
activities in the Instinct AI Trading System. It includes:

1. Real-time visualization of execution status and performance
2. Control interface for managing active executions
3. Analytics panels for execution quality and performance metrics
4. Historical execution data and performance tracking
5. Risk monitoring and visualization components

The dashboard acts as a central hub for execution monitoring and management,
providing visibility and control over the execution process.
"""

# Import core components
from advanced_trading.execution.dashboard.models import (
    ExecutionDashboardConfig,
    ExecutionMetrics,
    DashboardState
)

from advanced_trading.execution.dashboard.services import (
    MetricsCollector,
    DashboardDataService,
    ExecutionController
)

from advanced_trading.execution.dashboard.components import (
    ExecutionStatusPanel,
    RiskVisualization,
    PerformanceMetricsPanel,
    ControlPanel
)

from advanced_trading.execution.dashboard.views import (
    DashboardView,
    ExecutionView,
    HistoricalView,
    SettingsView
)

# Public API
__all__ = [
    # Core models
    'ExecutionDashboardConfig',
    'ExecutionMetrics',
    'DashboardState',
    
    # Services
    'MetricsCollector',
    'DashboardDataService',
    'ExecutionController',
    
    # Components
    'ExecutionStatusPanel',
    'RiskVisualization',
    'PerformanceMetricsPanel',
    'ControlPanel',
    
    # Views
    'DashboardView',
    'ExecutionView',
    'HistoricalView',
    'SettingsView'
] 