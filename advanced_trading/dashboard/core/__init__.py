"""
Dashboard Core Module

This module provides core functionality for the unified dashboard, including
configuration, state management, and central control.
"""

from .config import DashboardConfig, DashboardTheme, LayoutType, PanelSettings, SystemSettings
from .state import DashboardState, ViewType, NotificationItem, ActiveExecution
from .controller import DashboardController

# Public API
__all__ = [
    'DashboardConfig',
    'DashboardTheme',
    'LayoutType',
    'PanelSettings',
    'SystemSettings',
    'DashboardState',
    'ViewType',
    'NotificationItem',
    'ActiveExecution',
    'DashboardController'
] 