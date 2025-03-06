"""
Dashboard Controller

This module defines the central controller for the unified dashboard,
coordinating operations and interaction between various dashboard components.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Set, Tuple, Union
import time
import threading
import uuid

from .config import DashboardConfig
from .state import DashboardState, ViewType, ActiveExecution, NotificationItem

logger = logging.getLogger(__name__)


class DashboardController:
    """
    Central controller for the unified dashboard.
    
    The controller manages the dashboard's state and configuration, coordinates
    operations between components, handles events, and provides an interface for
    UI components to access data and trigger actions.
    """
    
    def __init__(self, config: Optional[DashboardConfig] = None):
        """
        Initialize the dashboard controller.
        
        Args:
            config: Dashboard configuration, or None to use default.
        """
        self.config = config or DashboardConfig()
        self.state = DashboardState()
        
        # Event listeners for state changes
        self._listeners: Dict[str, List[Callable]] = {
            "view_changed": [],
            "panel_selected": [],
            "panel_toggled": [],
            "filters_updated": [],
            "execution_added": [],
            "execution_removed": [],
            "execution_selected": [],
            "execution_updated": [],
            "notification_added": [],
            "notification_status_changed": [],
            "error_set": [],
            "loading_changed": []
        }
        
        # Component registry
        self._data_providers: Dict[str, Any] = {}
        self._ui_components: Dict[str, Any] = {}
        self._service_components: Dict[str, Any] = {}
        
        # Background tasks
        self._running = True
        self._update_thread = None
        self._update_interval = 1.0  # seconds
        self._last_update_time = time.time()
        
        logger.info("Dashboard controller initialized")
    
    def start(self) -> None:
        """Start the dashboard controller's background operations."""
        if self._update_thread is None or not self._update_thread.is_alive():
            self._running = True
            self._update_thread = threading.Thread(target=self._background_update_loop, daemon=True)
            self._update_thread.start()
            logger.info("Dashboard controller started")
    
    def stop(self) -> None:
        """Stop the dashboard controller's background operations."""
        self._running = False
        if self._update_thread and self._update_thread.is_alive():
            self._update_thread.join(timeout=2.0)
            logger.info("Dashboard controller stopped")
    
    def _background_update_loop(self) -> None:
        """Background thread for periodic updates."""
        while self._running:
            try:
                current_time = time.time()
                if current_time - self._last_update_time >= self._update_interval:
                    self._perform_periodic_updates()
                    self._last_update_time = current_time
                time.sleep(0.1)  # Sleep briefly to prevent high CPU usage
            except Exception as e:
                logger.error(f"Error in dashboard background update: {str(e)}")
                time.sleep(1.0)  # Longer sleep on error
    
    def _perform_periodic_updates(self) -> None:
        """Perform periodic updates to refresh dashboard data."""
        # Update active executions status from registered data providers
        for execution_id, execution in list(self.state.active_executions.items()):
            if execution.is_active:
                self._update_execution_status(execution_id)
        
        # Clean up old notifications based on configuration
        if len(self.state.notifications) > self.config.system.max_history_items:
            # Remove oldest dismissed notifications first
            dismissed = [n for n in self.state.notifications if n.dismissed]
            dismissed.sort(key=lambda n: n.timestamp)
            
            # Calculate how many to remove
            to_remove = len(self.state.notifications) - self.config.system.max_history_items
            if to_remove > 0 and dismissed:
                for i in range(min(to_remove, len(dismissed))):
                    self.state.notifications.remove(dismissed[i])
    
    def register_event_listener(self, event_type: str, callback: Callable) -> bool:
        """
        Register a callback for a specific event type.
        
        Args:
            event_type: Type of event to listen for.
            callback: Function to call when the event occurs.
            
        Returns:
            True if registered successfully, False otherwise.
        """
        if event_type in self._listeners:
            self._listeners[event_type].append(callback)
            return True
        return False
    
    def unregister_event_listener(self, event_type: str, callback: Callable) -> bool:
        """
        Unregister a callback for a specific event type.
        
        Args:
            event_type: Type of event.
            callback: Function to unregister.
            
        Returns:
            True if unregistered successfully, False otherwise.
        """
        if event_type in self._listeners and callback in self._listeners[event_type]:
            self._listeners[event_type].remove(callback)
            return True
        return False
    
    def _notify_listeners(self, event_type: str, **kwargs) -> None:
        """
        Notify all listeners for a specific event type.
        
        Args:
            event_type: Type of event that occurred.
            **kwargs: Event data to pass to listeners.
        """
        if event_type in self._listeners:
            for callback in self._listeners[event_type]:
                try:
                    callback(**kwargs)
                except Exception as e:
                    logger.error(f"Error in event listener for {event_type}: {str(e)}")
    
    # Component registration
    
    def register_data_provider(self, provider_name: str, provider: Any) -> None:
        """
        Register a data provider component.
        
        Args:
            provider_name: Name of the provider.
            provider: The provider object.
        """
        self._data_providers[provider_name] = provider
        logger.info(f"Registered data provider: {provider_name}")
    
    def register_ui_component(self, component_name: str, component: Any) -> None:
        """
        Register a UI component.
        
        Args:
            component_name: Name of the component.
            component: The component object.
        """
        self._ui_components[component_name] = component
        logger.info(f"Registered UI component: {component_name}")
    
    def register_service(self, service_name: str, service: Any) -> None:
        """
        Register a service component.
        
        Args:
            service_name: Name of the service.
            service: The service object.
        """
        self._service_components[service_name] = service
        logger.info(f"Registered service: {service_name}")
    
    # View and panel management
    
    def change_view(self, view: Union[ViewType, str]) -> None:
        """
        Change the current view.
        
        Args:
            view: The view to switch to, can be ViewType enum or string.
        """
        if isinstance(view, str):
            try:
                view = ViewType(view)
            except ValueError:
                logger.error(f"Invalid view type: {view}")
                return
        
        self.state.change_view(view)
        self._notify_listeners("view_changed", view=view)
    
    def select_panel(self, panel_name: str) -> None:
        """
        Select a panel.
        
        Args:
            panel_name: Name of the panel to select.
        """
        self.state.select_panel(panel_name)
        self._notify_listeners("panel_selected", panel_name=panel_name)
    
    def toggle_panel(self, panel_name: str) -> bool:
        """
        Toggle a panel's expansion state.
        
        Args:
            panel_name: Name of the panel to toggle.
            
        Returns:
            New expansion state (True if expanded, False if collapsed).
        """
        new_state = self.state.toggle_panel_expansion(panel_name)
        self._notify_listeners("panel_toggled", panel_name=panel_name, expanded=new_state)
        return new_state
    
    def update_panel_settings(self, panel_name: str, **settings) -> bool:
        """
        Update settings for a panel.
        
        Args:
            panel_name: Name of the panel.
            **settings: Settings to update.
            
        Returns:
            True if successful, False otherwise.
        """
        if panel_name not in self.config.panels:
            return False
        
        panel_settings = self.config.panels[panel_name]
        
        if "enabled" in settings:
            panel_settings.enabled = bool(settings["enabled"])
        if "position" in settings:
            panel_settings.position = settings["position"]
        if "size" in settings:
            panel_settings.size = settings["size"]
        if "order" in settings:
            panel_settings.order = int(settings["order"])
        if "auto_refresh" in settings:
            panel_settings.auto_refresh = bool(settings["auto_refresh"])
        if "refresh_interval_ms" in settings:
            panel_settings.refresh_interval_ms = int(settings["refresh_interval_ms"])
        
        return True
    
    # Filter management
    
    def update_filters(self, **filters) -> None:
        """
        Update filter criteria.
        
        Args:
            **filters: Filter criteria to update.
        """
        self.state.update_filters(**filters)
        self._notify_listeners("filters_updated", filters=filters)
    
    def clear_filters(self) -> None:
        """Clear all filter criteria."""
        self.state.clear_filters()
        self._notify_listeners("filters_updated", filters={})
    
    # Execution management
    
    def add_execution(self, strategy_id: str, strategy_name: str, symbol: str, 
                     timeframe: str, **metadata) -> str:
        """
        Add a new execution.
        
        Args:
            strategy_id: ID of the strategy.
            strategy_name: Name of the strategy.
            symbol: Symbol being traded.
            timeframe: Timeframe of the execution.
            **metadata: Additional metadata.
            
        Returns:
            ID of the new execution.
        """
        execution_id = str(uuid.uuid4())
        
        execution = ActiveExecution(
            id=execution_id,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            start_time=time.time(),
            symbol=symbol,
            timeframe=timeframe,
            status="running",
            metadata=metadata
        )
        
        self.state.add_execution(execution)
        self._notify_listeners("execution_added", execution=execution)
        
        # Add notification
        self.add_notification(
            level="info",
            source="Execution",
            message=f"Started execution of {strategy_name} on {symbol} ({timeframe})"
        )
        
        return execution_id
    
    def remove_execution(self, execution_id: str) -> bool:
        """
        Remove an execution.
        
        Args:
            execution_id: ID of the execution to remove.
            
        Returns:
            True if successful, False otherwise.
        """
        execution = self.state.remove_execution(execution_id)
        if execution:
            self._notify_listeners("execution_removed", execution_id=execution_id)
            return True
        return False
    
    def select_execution(self, execution_id: str) -> bool:
        """
        Select an execution.
        
        Args:
            execution_id: ID of the execution to select.
            
        Returns:
            True if successful, False otherwise.
        """
        if self.state.select_execution(execution_id):
            self._notify_listeners("execution_selected", execution_id=execution_id)
            return True
        return False
    
    def update_execution_status(self, execution_id: str, status: str, 
                              progress: Optional[float] = None, 
                              metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update an execution's status.
        
        Args:
            execution_id: ID of the execution to update.
            status: New execution status.
            progress: Optional progress value (0.0 to 1.0).
            metadata: Optional metadata to update.
            
        Returns:
            True if successful, False otherwise.
        """
        if self.state.update_execution_status(execution_id, status, progress, metadata):
            execution = self.state.active_executions.get(execution_id)
            self._notify_listeners("execution_updated", 
                                  execution_id=execution_id, 
                                  status=status, 
                                  execution=execution)
            
            # Add notifications for important status changes
            if status in ["completed", "failed"]:
                level = "info" if status == "completed" else "error"
                self.add_notification(
                    level=level,
                    source="Execution",
                    message=f"{status.capitalize()}: {execution.strategy_name} on {execution.symbol}"
                )
            
            return True
        return False
    
    def _update_execution_status(self, execution_id: str) -> None:
        """
        Update an execution's status from data providers.
        
        Args:
            execution_id: ID of the execution to update.
        """
        execution = self.state.active_executions.get(execution_id)
        if not execution:
            return
        
        # Check if we have an execution data provider
        if "execution" in self._data_providers:
            try:
                data_provider = self._data_providers["execution"]
                status_data = data_provider.get_execution_status(execution_id)
                
                if status_data:
                    self.state.update_execution_status(
                        execution_id,
                        status=status_data.get("status", execution.status),
                        progress=status_data.get("progress"),
                        metadata=status_data.get("metadata")
                    )
            except Exception as e:
                logger.error(f"Error updating execution status: {str(e)}")
    
    def get_execution_details(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about an execution.
        
        Args:
            execution_id: ID of the execution.
            
        Returns:
            Dictionary with execution details, or None if not found.
        """
        execution = self.state.active_executions.get(execution_id)
        if not execution:
            return None
        
        # Basic details
        details = {
            "id": execution.id,
            "strategy_id": execution.strategy_id,
            "strategy_name": execution.strategy_name,
            "symbol": execution.symbol,
            "timeframe": execution.timeframe,
            "status": execution.status,
            "progress": execution.progress,
            "start_time": execution.start_time,
            "duration": execution.duration,
            "metadata": execution.metadata.copy()
        }
        
        # Check if we have an execution data provider for more details
        if "execution" in self._data_providers:
            try:
                data_provider = self._data_providers["execution"]
                additional_details = data_provider.get_execution_details(execution_id)
                if additional_details:
                    details.update(additional_details)
            except Exception as e:
                logger.error(f"Error getting execution details: {str(e)}")
        
        return details
    
    # Notification management
    
    def add_notification(self, level: str, source: str, message: str) -> NotificationItem:
        """
        Add a notification.
        
        Args:
            level: Notification level (info, warning, error, critical).
            source: Source of the notification.
            message: Notification message.
            
        Returns:
            The created notification item.
        """
        notification = self.state.add_notification(level, source, message)
        self._notify_listeners("notification_added", notification=notification)
        return notification
    
    def mark_notification_read(self, notification_id: str) -> bool:
        """
        Mark a notification as read.
        
        Args:
            notification_id: ID of the notification.
            
        Returns:
            True if successful, False otherwise.
        """
        if self.state.mark_notification_read(notification_id):
            self._notify_listeners("notification_status_changed", 
                                  notification_id=notification_id, 
                                  read=True)
            return True
        return False
    
    def mark_all_notifications_read(self) -> int:
        """
        Mark all notifications as read.
        
        Returns:
            Number of notifications marked as read.
        """
        count = self.state.mark_all_notifications_read()
        if count > 0:
            self._notify_listeners("notification_status_changed", all_read=True)
        return count
    
    def dismiss_notification(self, notification_id: str) -> bool:
        """
        Dismiss a notification.
        
        Args:
            notification_id: ID of the notification.
            
        Returns:
            True if successful, False otherwise.
        """
        if self.state.dismiss_notification(notification_id):
            self._notify_listeners("notification_status_changed", 
                                  notification_id=notification_id, 
                                  dismissed=True)
            return True
        return False
    
    def clear_dismissed_notifications(self) -> int:
        """
        Clear all dismissed notifications.
        
        Returns:
            Number of notifications removed.
        """
        count = self.state.clear_dismissed_notifications()
        if count > 0:
            self._notify_listeners("notification_status_changed", cleared_dismissed=True)
        return count
    
    # Error and loading state management
    
    def set_error(self, error_message: Optional[str]) -> None:
        """
        Set or clear the last error message.
        
        Args:
            error_message: Error message, or None to clear.
        """
        self.state.set_error(error_message)
        self._notify_listeners("error_set", error_message=error_message)
        
        if error_message:
            self.add_notification(level="error", source="System", message=error_message)
    
    def set_loading(self, panel: str, is_loading: bool) -> None:
        """
        Set loading state for a panel.
        
        Args:
            panel: Name of the panel.
            is_loading: Whether the panel is loading.
        """
        self.state.set_loading(panel, is_loading)
        self._notify_listeners("loading_changed", panel=panel, is_loading=is_loading)
    
    # Configuration management
    
    def save_config(self, config_path: Optional[str] = None) -> bool:
        """
        Save the current configuration.
        
        Args:
            config_path: Path to save to, or None for default.
            
        Returns:
            True if successful, False otherwise.
        """
        return self.config.save(config_path)
    
    def load_config(self, config_path: Optional[str] = None) -> bool:
        """
        Load configuration from file.
        
        Args:
            config_path: Path to load from, or None for default.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            self.config = DashboardConfig.load(config_path)
            return True
        except Exception as e:
            logger.error(f"Error loading configuration: {str(e)}")
            return False
    
    def reset(self) -> None:
        """Reset the dashboard to initial state."""
        self.state.reset()
        self._notify_listeners("view_changed", view=self.state.current_view)


# Public API
__all__ = ['DashboardController'] 