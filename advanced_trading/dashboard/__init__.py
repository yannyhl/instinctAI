"""
Unified Dashboard for Instinct AI Trading System

This module provides a comprehensive, single-operator interface for controlling 
and monitoring all aspects of the Instinct AI Trading System. The dashboard 
integrates strategy management, execution control, backtesting capabilities, 
risk management, performance analytics, and system administration into a 
cohesive interface.

Key Components:
- Core: Configuration, state management, and central controller
- Panels: Specialized dashboard sections for different aspects of the system
- Views: Visualization components for data presentation
- Widgets: Reusable UI components for building dashboard interfaces

This dashboard serves as a command center for trading operations, enabling 
a single operator to efficiently manage the entire trading pipeline.
"""

from .core import (
    # Core components
    DashboardConfig, DashboardState, DashboardController,
    
    # Config classes
    DashboardTheme, LayoutType, PanelSettings, SystemSettings,
    
    # State classes
    ViewType, NotificationItem, ActiveExecution
)

# Import panel components 
from advanced_trading.dashboard.panels import (
    StrategyPanel,
    ExecutionPanel,
    BacktestPanel,
    RiskPanel,
    AnalyticsPanel,
    SystemPanel
)

# Import views
from advanced_trading.dashboard.views import (
    DashboardView,
    StrategyView,
    BacktestView, 
    ExecutionView
)

# Import widgets
from advanced_trading.dashboard.widgets import (
    StatusWidget,
    ControlWidget,
    MetricsWidget,
    AlertWidget
)

# Import existing execution dashboard functionality 
from advanced_trading.execution.dashboard import (
    ExecutionMetrics,
    ExecutionController,
    MetricsCollector
)

# Public API
__all__ = [
    # Core components
    'DashboardConfig',
    'DashboardState',
    'DashboardController',
    
    # Config classes
    'DashboardTheme',
    'LayoutType',
    'PanelSettings',
    'SystemSettings',
    
    # State classes
    'ViewType',
    'NotificationItem',
    'ActiveExecution',
    
    # Panels
    'StrategyPanel',
    'ExecutionPanel',
    'BacktestPanel',
    'RiskPanel',
    'AnalyticsPanel',
    'SystemPanel',
    
    # Views
    'DashboardView',
    'StrategyView',
    'BacktestView',
    'ExecutionView',
    
    # Widgets
    'StatusWidget',
    'ControlWidget',
    'MetricsWidget',
    'AlertWidget',
    
    # Execution components
    'ExecutionMetrics',
    'ExecutionController',
    'MetricsCollector'
] 