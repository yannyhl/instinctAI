"""
Dashboard Configuration

This module defines the configuration for the unified dashboard, including
layout, panel settings, and feature flags.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Any, Optional
from enum import Enum
import json
import os
import logging

logger = logging.getLogger(__name__)


class DashboardTheme(Enum):
    """Available dashboard themes."""
    DARK = "dark"
    LIGHT = "light"
    HIGH_CONTRAST = "high_contrast"
    CUSTOM = "custom"


class LayoutType(Enum):
    """Available dashboard layout types."""
    STANDARD = "standard"  # Fixed panels in predefined positions
    GRID = "grid"          # Grid-based layout with resizable panels
    TABS = "tabs"          # Tabbed interface for switching between views
    COMPACT = "compact"    # Minimalist layout for smaller screens


@dataclass
class PanelSettings:
    """Settings for a dashboard panel."""
    enabled: bool = True
    position: str = "main"  # main, left, right, top, bottom
    size: str = "medium"    # small, medium, large
    order: int = 0
    collapsed: bool = False
    auto_refresh: bool = True
    refresh_interval_ms: int = 5000


@dataclass
class SystemSettings:
    """System-wide settings for the dashboard."""
    log_level: str = "info"
    auto_save_interval_ms: int = 60000  # Auto-save preferences every minute
    enable_notifications: bool = True
    notification_level: str = "warning"  # info, warning, error, critical
    max_history_items: int = 1000        # Max items to keep in history
    data_retention_days: int = 30        # How long to keep historical data


@dataclass
class DashboardConfig:
    """
    Configuration for the unified dashboard.
    
    This class defines the settings for the dashboard's behavior, appearance,
    and functionality. It includes settings for all panels, system-wide
    configurations, and user preferences.
    """
    # General settings
    dashboard_title: str = "Instinct AI Trading System"
    theme: DashboardTheme = DashboardTheme.DARK
    layout_type: LayoutType = LayoutType.STANDARD
    timezone: str = "UTC"
    date_format: str = "YYYY-MM-DD HH:mm:ss"
    enable_animations: bool = True
    
    # Panel settings
    panels: Dict[str, PanelSettings] = field(default_factory=lambda: {
        "strategy": PanelSettings(position="left", order=1),
        "execution": PanelSettings(position="main", order=1),
        "backtest": PanelSettings(position="main", order=2),
        "risk": PanelSettings(position="right", order=1),
        "analytics": PanelSettings(position="main", order=3),
        "system": PanelSettings(position="bottom", order=1, collapsed=True)
    })
    
    # System settings
    system: SystemSettings = field(default_factory=SystemSettings)
    
    # Feature flags
    enable_strategy_management: bool = True
    enable_execution_control: bool = True
    enable_backtest_execution: bool = True
    enable_risk_monitoring: bool = True
    enable_system_administration: bool = True
    enable_real_time_updates: bool = True
    
    # User preferences
    start_page: str = "overview"  # Default page to show on startup
    default_symbol: Optional[str] = None
    default_timeframe: str = "1h"
    favorite_strategies: List[str] = field(default_factory=list)
    recent_executions: List[str] = field(default_factory=list)
    pinned_metrics: List[str] = field(default_factory=list)
    
    @classmethod
    def load(cls, config_path: Optional[str] = None) -> 'DashboardConfig':
        """
        Load dashboard configuration from a file.
        
        Args:
            config_path: Path to the configuration file.
                If None, tries to load from the default location.
                
        Returns:
            Loaded dashboard configuration.
        """
        if config_path is None:
            # Default location: WORKSPACE_DIR/config/dashboard_config.json
            config_path = os.path.join(
                os.environ.get("WORKSPACE_DIR", "."),
                "config",
                "dashboard_config.json"
            )
        
        if not os.path.exists(config_path):
            logger.info(f"Configuration file not found at {config_path}. Using defaults.")
            return cls()
        
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            # Load basic settings
            config = cls(
                dashboard_title=config_data.get("dashboard_title", cls.dashboard_title),
                theme=DashboardTheme(config_data.get("theme", cls.theme.value)),
                layout_type=LayoutType(config_data.get("layout_type", cls.layout_type.value)),
                timezone=config_data.get("timezone", cls.timezone),
                date_format=config_data.get("date_format", cls.date_format),
                enable_animations=config_data.get("enable_animations", cls.enable_animations),
                start_page=config_data.get("start_page", cls.start_page),
                default_symbol=config_data.get("default_symbol"),
                default_timeframe=config_data.get("default_timeframe", cls.default_timeframe)
            )
            
            # Load panel settings
            if "panels" in config_data:
                for panel_name, panel_settings in config_data["panels"].items():
                    config.panels[panel_name] = PanelSettings(
                        enabled=panel_settings.get("enabled", True),
                        position=panel_settings.get("position", "main"),
                        size=panel_settings.get("size", "medium"),
                        order=panel_settings.get("order", 0),
                        collapsed=panel_settings.get("collapsed", False),
                        auto_refresh=panel_settings.get("auto_refresh", True),
                        refresh_interval_ms=panel_settings.get("refresh_interval_ms", 5000)
                    )
            
            # Load system settings
            if "system" in config_data:
                system_data = config_data["system"]
                config.system = SystemSettings(
                    log_level=system_data.get("log_level", cls.system.log_level),
                    auto_save_interval_ms=system_data.get("auto_save_interval_ms", cls.system.auto_save_interval_ms),
                    enable_notifications=system_data.get("enable_notifications", cls.system.enable_notifications),
                    notification_level=system_data.get("notification_level", cls.system.notification_level),
                    max_history_items=system_data.get("max_history_items", cls.system.max_history_items),
                    data_retention_days=system_data.get("data_retention_days", cls.system.data_retention_days)
                )
            
            # Load feature flags
            if "features" in config_data:
                features = config_data["features"]
                config.enable_strategy_management = features.get("enable_strategy_management", cls.enable_strategy_management)
                config.enable_execution_control = features.get("enable_execution_control", cls.enable_execution_control)
                config.enable_backtest_execution = features.get("enable_backtest_execution", cls.enable_backtest_execution)
                config.enable_risk_monitoring = features.get("enable_risk_monitoring", cls.enable_risk_monitoring)
                config.enable_system_administration = features.get("enable_system_administration", cls.enable_system_administration)
                config.enable_real_time_updates = features.get("enable_real_time_updates", cls.enable_real_time_updates)
            
            # Load user preferences
            if "user_preferences" in config_data:
                prefs = config_data["user_preferences"]
                config.favorite_strategies = prefs.get("favorite_strategies", [])
                config.recent_executions = prefs.get("recent_executions", [])
                config.pinned_metrics = prefs.get("pinned_metrics", [])
            
            logger.info(f"Loaded dashboard configuration from {config_path}")
            return config
            
        except Exception as e:
            logger.error(f"Error loading dashboard configuration: {str(e)}")
            return cls()
    
    def save(self, config_path: Optional[str] = None) -> bool:
        """
        Save dashboard configuration to a file.
        
        Args:
            config_path: Path to save the configuration to.
                If None, saves to the default location.
                
        Returns:
            True if successful, False otherwise.
        """
        if config_path is None:
            # Default location: WORKSPACE_DIR/config/dashboard_config.json
            config_dir = os.path.join(
                os.environ.get("WORKSPACE_DIR", "."),
                "config"
            )
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, "dashboard_config.json")
        
        try:
            # Convert to serializable format
            config_data = {
                "dashboard_title": self.dashboard_title,
                "theme": self.theme.value,
                "layout_type": self.layout_type.value,
                "timezone": self.timezone,
                "date_format": self.date_format,
                "enable_animations": self.enable_animations,
                "start_page": self.start_page,
                "default_symbol": self.default_symbol,
                "default_timeframe": self.default_timeframe,
                
                "panels": {
                    name: {
                        "enabled": panel.enabled,
                        "position": panel.position,
                        "size": panel.size,
                        "order": panel.order,
                        "collapsed": panel.collapsed,
                        "auto_refresh": panel.auto_refresh,
                        "refresh_interval_ms": panel.refresh_interval_ms
                    }
                    for name, panel in self.panels.items()
                },
                
                "system": {
                    "log_level": self.system.log_level,
                    "auto_save_interval_ms": self.system.auto_save_interval_ms,
                    "enable_notifications": self.system.enable_notifications,
                    "notification_level": self.system.notification_level,
                    "max_history_items": self.system.max_history_items,
                    "data_retention_days": self.system.data_retention_days
                },
                
                "features": {
                    "enable_strategy_management": self.enable_strategy_management,
                    "enable_execution_control": self.enable_execution_control,
                    "enable_backtest_execution": self.enable_backtest_execution,
                    "enable_risk_monitoring": self.enable_risk_monitoring,
                    "enable_system_administration": self.enable_system_administration,
                    "enable_real_time_updates": self.enable_real_time_updates
                },
                
                "user_preferences": {
                    "favorite_strategies": self.favorite_strategies,
                    "recent_executions": self.recent_executions,
                    "pinned_metrics": self.pinned_metrics
                }
            }
            
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Saved dashboard configuration to {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving dashboard configuration: {str(e)}")
            return False
    
    @classmethod
    def create_minimal(cls) -> 'DashboardConfig':
        """
        Create a minimal dashboard configuration with only essential features enabled.
        
        Returns:
            Minimal dashboard configuration.
        """
        config = cls()
        
        # Disable non-essential panels
        config.panels["analytics"].enabled = False
        config.panels["system"].enabled = False
        
        # Use compact layout
        config.layout_type = LayoutType.COMPACT
        
        # Disable animations
        config.enable_animations = False
        
        # Disable non-essential features
        config.enable_system_administration = False
        
        # Simplify system settings
        config.system.max_history_items = 100
        config.system.data_retention_days = 7
        
        # Set longer refresh intervals to reduce resource usage
        for panel in config.panels.values():
            panel.refresh_interval_ms = 10000  # 10 seconds
        
        return config
    
    def is_feature_enabled(self, feature_name: str) -> bool:
        """
        Check if a specific feature is enabled.
        
        Args:
            feature_name: Name of the feature to check.
            
        Returns:
            True if the feature is enabled, False otherwise.
        """
        feature_attr = f"enable_{feature_name}"
        return getattr(self, feature_attr, False)
    
    def get_enabled_panels(self) -> Dict[str, PanelSettings]:
        """
        Get all enabled panels.
        
        Returns:
            Dictionary of enabled panels, with panel names as keys and settings as values.
        """
        return {name: panel for name, panel in self.panels.items() if panel.enabled}
    
    def get_panels_by_position(self, position: str) -> Dict[str, PanelSettings]:
        """
        Get all panels at a specific position.
        
        Args:
            position: Panel position (main, left, right, top, bottom).
            
        Returns:
            Dictionary of panels at the specified position.
        """
        return {
            name: panel for name, panel in self.panels.items() 
            if panel.enabled and panel.position == position
        }
    
    def get_sorted_panels(self, position: Optional[str] = None) -> List[tuple]:
        """
        Get sorted panels, optionally filtered by position.
        
        Args:
            position: Optional panel position to filter by.
            
        Returns:
            List of (panel_name, panel_settings) tuples, sorted by order.
        """
        if position:
            panels = self.get_panels_by_position(position)
        else:
            panels = self.get_enabled_panels()
        
        return sorted(panels.items(), key=lambda x: x[1].order)


# Public API
__all__ = [
    'DashboardTheme',
    'LayoutType',
    'PanelSettings',
    'SystemSettings',
    'DashboardConfig'
] 