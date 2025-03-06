"""
Dashboard State

This module defines the state model for the execution dashboard.
The state model tracks the current state of the dashboard, including
active executions, selected views, filters, and user preferences.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
import time
from enum import Enum


class DashboardView(Enum):
    """Available dashboard views."""
    OVERVIEW = "overview"
    EXECUTION = "execution"
    HISTORY = "history"
    SETTINGS = "settings"
    CUSTOM = "custom"


@dataclass
class FilterState:
    """State of dashboard filters."""
    symbols: Set[str] = field(default_factory=set)
    strategies: Set[str] = field(default_factory=set)
    statuses: Set[str] = field(default_factory=set)
    exchanges: Set[str] = field(default_factory=set)
    date_range: Optional[Dict[str, float]] = None  # start and end timestamps
    min_size: Optional[float] = None
    max_size: Optional[float] = None
    tags: Set[str] = field(default_factory=set)
    custom_filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DashboardState:
    """
    State of the execution dashboard.
    
    This class tracks the current state of the dashboard, including
    active executions, selected views, filters, and user preferences.
    """
    # Current view state
    current_view: DashboardView = DashboardView.OVERVIEW
    selected_execution_id: Optional[str] = None
    selected_symbol: Optional[str] = None
    selected_strategy_id: Optional[str] = None
    selected_exchange: Optional[str] = None
    
    # Filter state
    filters: FilterState = field(default_factory=FilterState)
    
    # Time range for data display
    time_range_hours: int = 24  # Default to last 24 hours
    
    # User interface state
    expanded_panels: Set[str] = field(default_factory=set)
    auto_refresh: bool = True
    theme: str = "dark"
    chart_type: str = "candlestick"
    
    # User preferences
    user_id: Optional[str] = None
    last_settings: Dict[str, Any] = field(default_factory=dict)
    
    # Dashboard updates
    last_update_time: float = field(default_factory=time.time)
    update_count: int = 0
    
    def update_last_update_time(self) -> None:
        """Update the last update time to now."""
        self.last_update_time = time.time()
        self.update_count += 1
    
    def select_execution(self, execution_id: str) -> None:
        """Select an execution."""
        self.selected_execution_id = execution_id
        self.current_view = DashboardView.EXECUTION
        self.update_last_update_time()
    
    def apply_filter(self, filter_name: str, filter_value: Any) -> None:
        """Apply a filter to the dashboard."""
        if hasattr(self.filters, filter_name):
            setattr(self.filters, filter_name, filter_value)
        else:
            self.filters.custom_filters[filter_name] = filter_value
        self.update_last_update_time()
    
    def clear_filters(self) -> None:
        """Clear all filters."""
        self.filters = FilterState()
        self.update_last_update_time()
    
    def toggle_panel(self, panel_id: str) -> bool:
        """Toggle a panel's expanded state."""
        if panel_id in self.expanded_panels:
            self.expanded_panels.remove(panel_id)
            expanded = False
        else:
            self.expanded_panels.add(panel_id)
            expanded = True
        
        self.update_last_update_time()
        return expanded
    
    def change_view(self, view: DashboardView) -> None:
        """Change the current dashboard view."""
        self.current_view = view
        self.update_last_update_time()
    
    def set_time_range(self, hours: int) -> None:
        """Set the time range for data display."""
        self.time_range_hours = hours
        self.update_last_update_time()
    
    def set_theme(self, theme: str) -> None:
        """Set the dashboard theme."""
        self.theme = theme
        if "theme" not in self.last_settings:
            self.last_settings["theme"] = theme
        self.update_last_update_time()
    
    def save_preferences(self) -> Dict[str, Any]:
        """Save current state as user preferences."""
        preferences = {
            "theme": self.theme,
            "expanded_panels": list(self.expanded_panels),
            "chart_type": self.chart_type,
            "time_range_hours": self.time_range_hours,
            "auto_refresh": self.auto_refresh,
            "last_view": self.current_view.value,
            "last_update": time.time()
        }
        
        self.last_settings = preferences
        return preferences
    
    def load_preferences(self, preferences: Dict[str, Any]) -> None:
        """Load user preferences into the current state."""
        if "theme" in preferences:
            self.theme = preferences["theme"]
        
        if "expanded_panels" in preferences:
            self.expanded_panels = set(preferences["expanded_panels"])
        
        if "chart_type" in preferences:
            self.chart_type = preferences["chart_type"]
        
        if "time_range_hours" in preferences:
            self.time_range_hours = preferences["time_range_hours"]
        
        if "auto_refresh" in preferences:
            self.auto_refresh = preferences["auto_refresh"]
        
        if "last_view" in preferences:
            try:
                self.current_view = DashboardView(preferences["last_view"])
            except ValueError:
                # Invalid view, ignore
                pass
        
        self.last_settings = preferences
        self.update_last_update_time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to a dictionary for serialization."""
        return {
            "current_view": self.current_view.value,
            "selected_execution_id": self.selected_execution_id,
            "selected_symbol": self.selected_symbol,
            "selected_strategy_id": self.selected_strategy_id,
            "selected_exchange": self.selected_exchange,
            "filters": {
                "symbols": list(self.filters.symbols),
                "strategies": list(self.filters.strategies),
                "statuses": list(self.filters.statuses),
                "exchanges": list(self.filters.exchanges),
                "date_range": self.filters.date_range,
                "min_size": self.filters.min_size,
                "max_size": self.filters.max_size,
                "tags": list(self.filters.tags),
                "custom_filters": self.filters.custom_filters
            },
            "time_range_hours": self.time_range_hours,
            "expanded_panels": list(self.expanded_panels),
            "auto_refresh": self.auto_refresh,
            "theme": self.theme,
            "chart_type": self.chart_type,
            "user_id": self.user_id,
            "last_settings": self.last_settings,
            "last_update_time": self.last_update_time,
            "update_count": self.update_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DashboardState':
        """Create state from a dictionary."""
        # Create filter state
        filter_data = data.get("filters", {})
        filters = FilterState(
            symbols=set(filter_data.get("symbols", [])),
            strategies=set(filter_data.get("strategies", [])),
            statuses=set(filter_data.get("statuses", [])),
            exchanges=set(filter_data.get("exchanges", [])),
            date_range=filter_data.get("date_range"),
            min_size=filter_data.get("min_size"),
            max_size=filter_data.get("max_size"),
            tags=set(filter_data.get("tags", [])),
            custom_filters=filter_data.get("custom_filters", {})
        )
        
        # Create dashboard state
        try:
            current_view = DashboardView(data.get("current_view", "overview"))
        except ValueError:
            current_view = DashboardView.OVERVIEW
        
        return cls(
            current_view=current_view,
            selected_execution_id=data.get("selected_execution_id"),
            selected_symbol=data.get("selected_symbol"),
            selected_strategy_id=data.get("selected_strategy_id"),
            selected_exchange=data.get("selected_exchange"),
            filters=filters,
            time_range_hours=data.get("time_range_hours", 24),
            expanded_panels=set(data.get("expanded_panels", [])),
            auto_refresh=data.get("auto_refresh", True),
            theme=data.get("theme", "dark"),
            chart_type=data.get("chart_type", "candlestick"),
            user_id=data.get("user_id"),
            last_settings=data.get("last_settings", {}),
            last_update_time=data.get("last_update_time", time.time()),
            update_count=data.get("update_count", 0)
        )


# Public API
__all__ = [
    'DashboardView',
    'FilterState',
    'DashboardState'
] 