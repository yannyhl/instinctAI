"""
Dashboard Configuration

This module defines the configuration settings for the execution dashboard.
These settings control the behavior, appearance, and functionality of the dashboard.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any


@dataclass
class WidgetConfig:
    """Configuration for a dashboard widget."""
    enabled: bool = True
    position: str = "main"  # main, sidebar, header, footer
    size: str = "medium"  # small, medium, large
    refresh_interval_ms: int = 5000  # How often to update, in milliseconds
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PanelConfig:
    """Configuration for a dashboard panel."""
    enabled: bool = True
    title: str = ""
    widgets: Dict[str, WidgetConfig] = field(default_factory=dict)
    collapsed: bool = False
    order: int = 0


@dataclass
class AlertConfig:
    """Configuration for dashboard alerts."""
    enabled: bool = True
    visual_alerts: bool = True
    sound_alerts: bool = False
    sound_file: str = "alert.wav"
    email_alerts: bool = False
    email_recipients: List[str] = field(default_factory=list)
    min_severity: str = "warning"  # info, warning, error, critical


@dataclass
class DataConfig:
    """Configuration for dashboard data sources."""
    execution_data_retention_hours: int = 24
    performance_metrics_retention_days: int = 30
    max_executions_displayed: int = 100
    historical_data_chunk_size: int = 1000
    real_time_update_ms: int = 1000
    enable_data_caching: bool = True


@dataclass
class ViewConfig:
    """Configuration for a dashboard view."""
    default_view: str = "overview"
    available_views: List[str] = field(default_factory=lambda: ["overview", "execution", "history", "settings"])
    custom_views: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    view_permissions: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class ExecutionDashboardConfig:
    """
    Configuration settings for the execution dashboard.
    
    This class defines the settings that control the behavior, appearance, and
    functionality of the execution dashboard. It includes settings for panels,
    data sources, alerts, and other dashboard features.
    """
    # General settings
    dashboard_title: str = "Instinct AI Execution Dashboard"
    refresh_interval_ms: int = 1000
    theme: str = "dark"  # dark, light
    timezone: str = "UTC"
    date_format: str = "YYYY-MM-DD HH:mm:ss"
    enable_animations: bool = True
    
    # Panel configurations
    panels: Dict[str, PanelConfig] = field(default_factory=lambda: {
        "execution_status": PanelConfig(
            enabled=True,
            title="Execution Status",
            order=1
        ),
        "risk_visualization": PanelConfig(
            enabled=True,
            title="Risk Visualization",
            order=2
        ),
        "performance_metrics": PanelConfig(
            enabled=True,
            title="Performance Metrics",
            order=3
        ),
        "control_panel": PanelConfig(
            enabled=True,
            title="Control Panel",
            order=4
        ),
        "historical_executions": PanelConfig(
            enabled=True,
            title="Historical Executions",
            order=5
        )
    })
    
    # Widget configurations
    widgets: Dict[str, WidgetConfig] = field(default_factory=lambda: {
        "active_executions": WidgetConfig(
            enabled=True,
            position="main",
            refresh_interval_ms=1000
        ),
        "execution_quality": WidgetConfig(
            enabled=True,
            position="main",
            refresh_interval_ms=5000
        ),
        "risk_indicators": WidgetConfig(
            enabled=True,
            position="sidebar",
            refresh_interval_ms=2000
        ),
        "order_book_visualization": WidgetConfig(
            enabled=True,
            position="main",
            refresh_interval_ms=1000
        ),
        "execution_controls": WidgetConfig(
            enabled=True,
            position="sidebar",
            refresh_interval_ms=1000
        ),
        "performance_charts": WidgetConfig(
            enabled=True,
            position="main",
            refresh_interval_ms=5000
        ),
        "execution_history": WidgetConfig(
            enabled=True,
            position="main",
            refresh_interval_ms=10000
        )
    })
    
    # Data settings
    data_config: DataConfig = field(default_factory=DataConfig)
    
    # Alert settings
    alert_config: AlertConfig = field(default_factory=AlertConfig)
    
    # View settings
    view_config: ViewConfig = field(default_factory=ViewConfig)
    
    # User settings
    enable_user_customization: bool = True
    save_user_preferences: bool = True
    
    # Feature flags
    enable_real_time_updates: bool = True
    enable_historical_view: bool = True
    enable_risk_visualization: bool = True
    enable_performance_tracking: bool = True
    enable_execution_controls: bool = True
    
    @classmethod
    def create_default(cls) -> 'ExecutionDashboardConfig':
        """Create a default dashboard configuration."""
        return cls()
    
    @classmethod
    def create_minimal(cls) -> 'ExecutionDashboardConfig':
        """Create a minimal dashboard configuration with only essential features."""
        config = cls()
        
        # Disable non-essential panels
        config.panels["historical_executions"].enabled = False
        
        # Disable non-essential widgets
        config.widgets["performance_charts"].enabled = False
        config.widgets["order_book_visualization"].enabled = False
        config.widgets["execution_history"].enabled = False
        
        # Set minimal refresh intervals
        config.refresh_interval_ms = 2000
        for widget_name, widget in config.widgets.items():
            if widget.enabled:
                widget.refresh_interval_ms = max(widget.refresh_interval_ms, 2000)
        
        # Disable animations
        config.enable_animations = False
        
        # Minimal data retention
        config.data_config.execution_data_retention_hours = 8
        config.data_config.performance_metrics_retention_days = 7
        
        return config
    
    def get_enabled_panels(self) -> Dict[str, PanelConfig]:
        """Get the configuration for all enabled panels."""
        return {name: panel for name, panel in self.panels.items() if panel.enabled}
    
    def get_enabled_widgets(self) -> Dict[str, WidgetConfig]:
        """Get the configuration for all enabled widgets."""
        return {name: widget for name, widget in self.widgets.items() if widget.enabled}
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a specific feature is enabled."""
        feature_flag = f"enable_{feature_name}"
        return getattr(self, feature_flag, False)


# Public API
__all__ = [
    'WidgetConfig',
    'PanelConfig',
    'AlertConfig',
    'DataConfig',
    'ViewConfig',
    'ExecutionDashboardConfig'
] 