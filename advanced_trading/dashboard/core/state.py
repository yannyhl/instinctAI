"""
Dashboard State

This module defines the state management for the unified dashboard,
tracking active executions, selected views, filters, and user preferences.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Any, Optional
from enum import Enum
import json
import time
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class ViewType(Enum):
    """Types of views available in the dashboard."""
    OVERVIEW = "overview"
    STRATEGY = "strategy"
    EXECUTION = "execution"
    BACKTEST = "backtest"
    RISK = "risk"
    ANALYTICS = "analytics"
    SYSTEM = "system"


@dataclass
class NotificationItem:
    """A notification item in the dashboard."""
    id: str
    timestamp: float
    level: str  # info, warning, error, critical
    source: str
    message: str
    read: bool = False
    dismissed: bool = False
    
    def __post_init__(self):
        if not hasattr(self, 'id') or not self.id:
            self.id = str(uuid.uuid4())
        if not hasattr(self, 'timestamp') or not self.timestamp:
            self.timestamp = time.time()
    
    @property
    def formatted_time(self) -> str:
        """Get formatted timestamp string."""
        return datetime.fromtimestamp(self.timestamp).strftime('%Y-%m-%d %H:%M:%S')


@dataclass
class ActiveExecution:
    """Represents an active execution in the system."""
    id: str
    strategy_id: str
    strategy_name: str
    start_time: float
    symbol: str
    timeframe: str
    status: str  # running, paused, stopping, completed, failed
    progress: float = 0.0  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def formatted_start_time(self) -> str:
        """Get formatted start time string."""
        return datetime.fromtimestamp(self.start_time).strftime('%Y-%m-%d %H:%M:%S')
    
    @property
    def is_active(self) -> bool:
        """Check if execution is currently active."""
        return self.status in ["running", "paused"]
    
    @property
    def duration(self) -> float:
        """Get duration in seconds."""
        if self.status in ["completed", "failed"]:
            if "end_time" in self.metadata:
                return self.metadata["end_time"] - self.start_time
            return 0.0
        return time.time() - self.start_time


@dataclass
class DashboardState:
    """
    Tracks the current state of the unified dashboard.
    
    This class maintains the runtime state of the dashboard, including
    active executions, selected views, filter criteria, and temporary user
    preferences. The state is volatile and is not persisted between sessions,
    unlike configuration which is stored permanently.
    """
    # Current view state
    current_view: ViewType = ViewType.OVERVIEW
    selected_panel: Optional[str] = None
    expanded_panels: Set[str] = field(default_factory=set)
    
    # Filters
    selected_symbol: Optional[str] = None
    selected_timeframe: Optional[str] = None
    selected_strategy: Optional[str] = None
    date_range_start: Optional[float] = None
    date_range_end: Optional[float] = None
    
    # Status tracking
    active_executions: Dict[str, ActiveExecution] = field(default_factory=dict)
    selected_execution_id: Optional[str] = None
    
    # UI state
    notifications: List[NotificationItem] = field(default_factory=list)
    unread_notification_count: int = 0
    is_loading: Dict[str, bool] = field(default_factory=lambda: {
        "overview": False,
        "strategy": False,
        "execution": False,
        "backtest": False,
        "risk": False,
        "analytics": False,
        "system": False
    })
    last_error: Optional[str] = None
    
    # Time tracking
    session_start_time: float = field(default_factory=time.time)
    last_update_time: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """Initialize counter for unread notifications."""
        self.unread_notification_count = sum(1 for n in self.notifications if not n.read)
    
    def change_view(self, new_view: ViewType) -> None:
        """
        Change the current view.
        
        Args:
            new_view: The view to switch to.
        """
        logger.info(f"Changing view from {self.current_view} to {new_view}")
        self.current_view = new_view
        self.last_update_time = time.time()
    
    def select_panel(self, panel_name: str) -> None:
        """
        Select a panel to focus on.
        
        Args:
            panel_name: Name of the panel to select.
        """
        self.selected_panel = panel_name
        self.last_update_time = time.time()
    
    def toggle_panel_expansion(self, panel_name: str) -> bool:
        """
        Toggle expansion state of a panel.
        
        Args:
            panel_name: Name of the panel to toggle.
            
        Returns:
            New expansion state (True if expanded, False if collapsed).
        """
        if panel_name in self.expanded_panels:
            self.expanded_panels.remove(panel_name)
            expanded = False
        else:
            self.expanded_panels.add(panel_name)
            expanded = True
        
        self.last_update_time = time.time()
        return expanded
    
    def update_filters(self, **filters) -> None:
        """
        Update filter criteria.
        
        Args:
            **filters: Keyword arguments for filter criteria.
        """
        if "symbol" in filters:
            self.selected_symbol = filters["symbol"]
        if "timeframe" in filters:
            self.selected_timeframe = filters["timeframe"]
        if "strategy" in filters:
            self.selected_strategy = filters["strategy"]
        if "date_range_start" in filters:
            self.date_range_start = filters["date_range_start"]
        if "date_range_end" in filters:
            self.date_range_end = filters["date_range_end"]
        
        self.last_update_time = time.time()
    
    def clear_filters(self) -> None:
        """Clear all filter criteria."""
        self.selected_symbol = None
        self.selected_timeframe = None
        self.selected_strategy = None
        self.date_range_start = None
        self.date_range_end = None
        self.last_update_time = time.time()
    
    def add_execution(self, execution: ActiveExecution) -> None:
        """
        Add or update an active execution.
        
        Args:
            execution: The execution to add or update.
        """
        self.active_executions[execution.id] = execution
        self.last_update_time = time.time()
    
    def remove_execution(self, execution_id: str) -> Optional[ActiveExecution]:
        """
        Remove an execution from active executions.
        
        Args:
            execution_id: ID of the execution to remove.
            
        Returns:
            The removed execution, or None if not found.
        """
        execution = self.active_executions.pop(execution_id, None)
        
        if execution and self.selected_execution_id == execution_id:
            self.selected_execution_id = None
        
        self.last_update_time = time.time()
        return execution
    
    def select_execution(self, execution_id: str) -> bool:
        """
        Select an execution to focus on.
        
        Args:
            execution_id: ID of the execution to select.
            
        Returns:
            True if successful, False if execution not found.
        """
        if execution_id in self.active_executions:
            self.selected_execution_id = execution_id
            self.last_update_time = time.time()
            return True
        return False
    
    def update_execution_status(self, execution_id: str, status: str, progress: float = None,
                               metadata: Dict[str, Any] = None) -> bool:
        """
        Update the status of an active execution.
        
        Args:
            execution_id: ID of the execution to update.
            status: New status.
            progress: Optional new progress value.
            metadata: Optional metadata to update.
            
        Returns:
            True if successful, False if execution not found.
        """
        if execution_id not in self.active_executions:
            return False
        
        execution = self.active_executions[execution_id]
        execution.status = status
        
        if progress is not None:
            execution.progress = max(0.0, min(1.0, progress))
        
        if metadata:
            execution.metadata.update(metadata)
        
        # Add end_time to metadata if the execution is completed or failed
        if status in ["completed", "failed"] and "end_time" not in execution.metadata:
            execution.metadata["end_time"] = time.time()
        
        self.last_update_time = time.time()
        return True
    
    def add_notification(self, level: str, source: str, message: str) -> NotificationItem:
        """
        Add a notification to the dashboard.
        
        Args:
            level: Notification level (info, warning, error, critical).
            source: Source of the notification.
            message: Notification message.
            
        Returns:
            The created notification item.
        """
        notification = NotificationItem(
            id=str(uuid.uuid4()),
            timestamp=time.time(),
            level=level,
            source=source,
            message=message
        )
        
        self.notifications.append(notification)
        self.unread_notification_count += 1
        self.last_update_time = time.time()
        
        return notification
    
    def mark_notification_read(self, notification_id: str) -> bool:
        """
        Mark a notification as read.
        
        Args:
            notification_id: ID of the notification to mark as read.
            
        Returns:
            True if successful, False if notification not found.
        """
        for notification in self.notifications:
            if notification.id == notification_id and not notification.read:
                notification.read = True
                self.unread_notification_count -= 1
                self.last_update_time = time.time()
                return True
        return False
    
    def mark_all_notifications_read(self) -> int:
        """
        Mark all notifications as read.
        
        Returns:
            Number of notifications marked as read.
        """
        count = 0
        for notification in self.notifications:
            if not notification.read:
                notification.read = True
                count += 1
        
        self.unread_notification_count = 0
        self.last_update_time = time.time()
        return count
    
    def dismiss_notification(self, notification_id: str) -> bool:
        """
        Dismiss a notification.
        
        Args:
            notification_id: ID of the notification to dismiss.
            
        Returns:
            True if successful, False if notification not found.
        """
        for notification in self.notifications:
            if notification.id == notification_id:
                notification.dismissed = True
                if not notification.read:
                    notification.read = True
                    self.unread_notification_count -= 1
                self.last_update_time = time.time()
                return True
        return False
    
    def clear_dismissed_notifications(self) -> int:
        """
        Remove all dismissed notifications.
        
        Returns:
            Number of notifications removed.
        """
        original_count = len(self.notifications)
        
        # Update unread count for dismissed but unread notifications
        for notification in self.notifications:
            if notification.dismissed and not notification.read:
                self.unread_notification_count -= 1
        
        # Remove dismissed notifications
        self.notifications = [n for n in self.notifications if not n.dismissed]
        
        removed_count = original_count - len(self.notifications)
        if removed_count > 0:
            self.last_update_time = time.time()
        
        return removed_count
    
    def set_loading(self, panel: str, is_loading: bool) -> None:
        """
        Set loading state for a panel.
        
        Args:
            panel: Name of the panel.
            is_loading: Whether the panel is loading.
        """
        if panel in self.is_loading:
            self.is_loading[panel] = is_loading
            self.last_update_time = time.time()
    
    def set_error(self, error_message: Optional[str]) -> None:
        """
        Set the last error message.
        
        Args:
            error_message: Error message to set, or None to clear.
        """
        self.last_error = error_message
        self.last_update_time = time.time()
    
    def get_session_duration(self) -> float:
        """
        Get the current session duration in seconds.
        
        Returns:
            Session duration in seconds.
        """
        return time.time() - self.session_start_time
    
    def get_active_execution_count(self) -> int:
        """
        Get the number of currently active executions.
        
        Returns:
            Number of active executions.
        """
        return sum(1 for e in self.active_executions.values() if e.is_active)
    
    def get_notification_stats(self) -> Dict[str, int]:
        """
        Get notification statistics by level.
        
        Returns:
            Dictionary with notification counts by level.
        """
        stats = {"info": 0, "warning": 0, "error": 0, "critical": 0}
        for notification in self.notifications:
            if notification.level in stats:
                stats[notification.level] += 1
        
        stats["total"] = len(self.notifications)
        stats["unread"] = self.unread_notification_count
        
        return stats
    
    def reset(self) -> None:
        """Reset the dashboard state to initial values."""
        self.current_view = ViewType.OVERVIEW
        self.selected_panel = None
        self.expanded_panels = set()
        
        self.selected_symbol = None
        self.selected_timeframe = None
        self.selected_strategy = None
        self.date_range_start = None
        self.date_range_end = None
        
        self.active_executions = {}
        self.selected_execution_id = None
        
        self.notifications = []
        self.unread_notification_count = 0
        self.is_loading = {key: False for key in self.is_loading}
        self.last_error = None
        
        self.session_start_time = time.time()
        self.last_update_time = time.time()


# Public API
__all__ = [
    'ViewType',
    'NotificationItem',
    'ActiveExecution',
    'DashboardState'
] 