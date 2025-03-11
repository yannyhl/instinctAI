"""
Dashboard Data Service

This service manages data collection, processing, and storage for the dashboard.
It coordinates data retrieval from various sources and feeds it to the dashboard
components.
"""

import logging
import time
import threading
from typing import Dict, List, Optional, Any, Callable, Set
import json

from advanced_trading.execution.dashboard.models.metrics import ExecutionMetrics
from advanced_trading.execution.dashboard.models.state import DashboardState
from advanced_trading.execution.dashboard.services.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)


class DashboardDataService:
    """
    Service for managing dashboard data and state.
    
    This service coordinates data collection and processing for the dashboard,
    maintains the dashboard state, and provides filtered views of data based
    on user selections.
    """
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        """
        Initialize the dashboard data service.
        
        Args:
            metrics_collector: Optional metrics collector to use
        """
        self.metrics_collector = metrics_collector or MetricsCollector()
        self.dashboard_state = DashboardState()
        
        # Update listeners
        self.state_update_listeners: List[Callable[[DashboardState], None]] = []
        
        # Cache for derived data
        self.data_cache: Dict[str, Any] = {}
        self.cache_timestamp = 0.0
        self.cache_lifetime_seconds = 5.0  # How long to keep cached data
        
        # Register as a listener for execution updates
        self.metrics_collector.add_update_listener(self._handle_execution_update)
        
        logger.info("Dashboard data service initialized")
    
    def start_data_collection(self) -> None:
        """Start the data collection process."""
        self.metrics_collector.start_auto_update()
        logger.info("Dashboard data collection started")
    
    def stop_data_collection(self) -> None:
        """Stop the data collection process."""
        self.metrics_collector.stop_auto_update()
        logger.info("Dashboard data collection stopped")
    
    def add_state_update_listener(self, listener: Callable[[DashboardState], None]) -> None:
        """
        Add a listener for dashboard state updates.
        
        Args:
            listener: Callback function that takes the dashboard state
        """
        if listener not in self.state_update_listeners:
            self.state_update_listeners.append(listener)
    
    def remove_state_update_listener(self, listener: Callable[[DashboardState], None]) -> None:
        """
        Remove a listener for dashboard state updates.
        
        Args:
            listener: Callback function to remove
        """
        if listener in self.state_update_listeners:
            self.state_update_listeners.remove(listener)
    
    def _handle_execution_update(self, execution_id: str, metrics: ExecutionMetrics) -> None:
        """
        Handle an execution update from the metrics collector.
        
        Args:
            execution_id: ID of the updated execution
            metrics: Updated execution metrics
        """
        # Clear data cache since data has changed
        self.clear_cache()
        
        # Notify dashboard if the updated execution is the selected one
        if execution_id == self.dashboard_state.selected_execution_id:
            self._notify_state_update()
    
    def update_dashboard_state(self, updates: Dict[str, Any]) -> None:
        """
        Update the dashboard state with new values.
        
        Args:
            updates: Dictionary of state updates
        """
        for key, value in updates.items():
            if hasattr(self.dashboard_state, key):
                setattr(self.dashboard_state, key, value)
        
        # Clear cache and notify listeners
        self.clear_cache()
        self._notify_state_update()
    
    def _notify_state_update(self) -> None:
        """Notify all state update listeners."""
        self.dashboard_state.update_last_update_time()
        
        for listener in self.state_update_listeners:
            try:
                listener(self.dashboard_state)
            except Exception as e:
                logger.error(f"Error in state update listener: {str(e)}")
    
    def clear_cache(self) -> None:
        """Clear the data cache."""
        self.data_cache = {}
        self.cache_timestamp = 0.0
    
    def apply_filter(self, filter_name: str, filter_value: Any) -> None:
        """
        Apply a filter to the dashboard.
        
        Args:
            filter_name: Name of the filter to apply
            filter_value: Value to set for the filter
        """
        self.dashboard_state.apply_filter(filter_name, filter_value)
        
        # Clear cache and notify listeners
        self.clear_cache()
        self._notify_state_update()
    
    def clear_filters(self) -> None:
        """Clear all dashboard filters."""
        self.dashboard_state.clear_filters()
        
        # Clear cache and notify listeners
        self.clear_cache()
        self._notify_state_update()
    
    def select_execution(self, execution_id: str) -> None:
        """
        Select an execution to view.
        
        Args:
            execution_id: ID of the execution to select
        """
        self.dashboard_state.select_execution(execution_id)
        
        # Get the execution details
        execution = self.metrics_collector.get_execution(execution_id)
        if execution:
            # Update symbol and strategy selections
            self.dashboard_state.selected_symbol = execution.symbol
            self.dashboard_state.selected_strategy_id = execution.strategy_id
        
        # Clear cache and notify listeners
        self.clear_cache()
        self._notify_state_update()
    
    def select_symbol(self, symbol: str) -> None:
        """
        Select a symbol to filter by.
        
        Args:
            symbol: Symbol to select
        """
        self.dashboard_state.selected_symbol = symbol
        
        # Apply filter
        symbols = set()
        if symbol:
            symbols.add(symbol)
        self.dashboard_state.filters.symbols = symbols
        
        # Clear cache and notify listeners
        self.clear_cache()
        self._notify_state_update()
    
    def change_view(self, view_name: str) -> None:
        """
        Change the current dashboard view.
        
        Args:
            view_name: Name of the view to switch to
        """
        from advanced_trading.execution.dashboard.models.state import DashboardView
        
        try:
            view = DashboardView(view_name)
            self.dashboard_state.change_view(view)
            
            # Clear cache and notify listeners
            self.clear_cache()
            self._notify_state_update()
        except ValueError:
            logger.error(f"Invalid dashboard view: {view_name}")
    
    def set_time_range(self, hours: int) -> None:
        """
        Set the time range for data display.
        
        Args:
            hours: Number of hours to display data for
        """
        if hours > 0:
            self.dashboard_state.set_time_range(hours)
            
            # Update date range filter
            end_time = time.time()
            start_time = end_time - (hours * 3600)
            
            self.dashboard_state.filters.date_range = {
                "start": start_time,
                "end": end_time
            }
            
            # Clear cache and notify listeners
            self.clear_cache()
            self._notify_state_update()
    
    def toggle_auto_refresh(self) -> bool:
        """
        Toggle auto-refresh setting.
        
        Returns:
            New auto-refresh state
        """
        self.dashboard_state.auto_refresh = not self.dashboard_state.auto_refresh
        
        # If enabling auto-refresh, start data collection
        if self.dashboard_state.auto_refresh:
            self.start_data_collection()
        else:
            self.stop_data_collection()
        
        # Notify listeners
        self._notify_state_update()
        
        return self.dashboard_state.auto_refresh
    
    def set_theme(self, theme: str) -> None:
        """
        Set the dashboard theme.
        
        Args:
            theme: Theme name ('dark' or 'light')
        """
        if theme in ('dark', 'light'):
            self.dashboard_state.set_theme(theme)
            
            # Notify listeners
            self._notify_state_update()
    
    def save_user_preferences(self) -> Dict[str, Any]:
        """
        Save user preferences to persistent storage.
        
        Returns:
            Dictionary of saved preferences
        """
        preferences = self.dashboard_state.save_preferences()
        
        # Save preferences to file
        try:
            with open('user_preferences.json', 'w') as f:
                json.dump(preferences, f, indent=2)
            logger.info("Saved user preferences")
        except Exception as e:
            logger.error(f"Error saving user preferences: {str(e)}")
        
        return preferences
    
    def load_user_preferences(self) -> None:
        """Load user preferences from persistent storage."""
        try:
            with open('user_preferences.json', 'r') as f:
                preferences = json.load(f)
            
            self.dashboard_state.load_preferences(preferences)
            logger.info("Loaded user preferences")
            
            # Notify listeners
            self._notify_state_update()
        except FileNotFoundError:
            logger.info("No user preferences file found")
        except Exception as e:
            logger.error(f"Error loading user preferences: {str(e)}")
    
    def get_active_executions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get active executions for display.
        
        Args:
            limit: Maximum number of executions to return
            
        Returns:
            List of execution data dictionaries
        """
        # Check cache first
        cache_key = f"active_executions_{limit}"
        if cache_key in self.data_cache and time.time() - self.cache_timestamp < self.cache_lifetime_seconds:
            return self.data_cache[cache_key]
        
        # Get active executions from metrics collector
        active_metrics = self.metrics_collector.get_active_executions()
        
        # Sort by creation time (newest first)
        active_metrics.sort(key=lambda x: x.created_at, reverse=True)
        
        # Apply limit
        if limit:
            active_metrics = active_metrics[:limit]
        
        # Convert to dictionaries for display
        result = [metrics.to_dict() for metrics in active_metrics]
        
        # Cache the result
        self.data_cache[cache_key] = result
        self.cache_timestamp = time.time()
        
        return result
    
    def get_recent_executions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get recent executions for display.
        
        Args:
            limit: Maximum number of executions to return
            
        Returns:
            List of execution data dictionaries
        """
        # Check cache first
        cache_key = f"recent_executions_{limit}"
        if cache_key in self.data_cache and time.time() - self.cache_timestamp < self.cache_lifetime_seconds:
            return self.data_cache[cache_key]
        
        # Apply filters to get recent executions
        filters = self.dashboard_state.filters
        
        # Define filter function
        def filter_func(metrics: ExecutionMetrics) -> bool:
            # Filter by symbol
            if filters.symbols and metrics.symbol not in filters.symbols:
                return False
            
            # Filter by strategy
            if filters.strategies and metrics.strategy_id not in filters.strategies:
                return False
            
            # Filter by status
            if filters.statuses and metrics.status.value not in filters.statuses:
                return False
            
            # Filter by date range
            if filters.date_range:
                start = filters.date_range.get("start", 0)
                end = filters.date_range.get("end", float('inf'))
                if metrics.created_at < start or metrics.created_at > end:
                    return False
            
            # Filter by size
            if filters.min_size is not None and metrics.total_size < filters.min_size:
                return False
            if filters.max_size is not None and metrics.total_size > filters.max_size:
                return False
            
            # Filter by tags
            if filters.tags and not any(tag in filters.tags for tag in metrics.tags):
                return False
            
            # Filter by exchange
            if filters.exchanges and metrics.orders:
                order_exchanges = {order.exchange for order in metrics.orders}
                if not any(exchange in filters.exchanges for exchange in order_exchanges):
                    return False
            
            # Pass all filters
            return True
        
        # Get filtered executions
        filtered_metrics = self.metrics_collector.get_recent_executions(
            limit=limit,
            filter_func=filter_func
        )
        
        # Convert to dictionaries for display
        result = [metrics.to_dict() for metrics in filtered_metrics]
        
        # Cache the result
        self.data_cache[cache_key] = result
        self.cache_timestamp = time.time()
        
        return result
    
    def get_execution_details(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific execution.
        
        Args:
            execution_id: ID of the execution to get details for
            
        Returns:
            Dictionary of execution details or None if not found
        """
        # Check cache first
        cache_key = f"execution_details_{execution_id}"
        if cache_key in self.data_cache and time.time() - self.cache_timestamp < self.cache_lifetime_seconds:
            return self.data_cache[cache_key]
        
        # Get execution from metrics collector
        metrics = self.metrics_collector.get_execution(execution_id)
        if not metrics:
            return None
        
        # Convert to dictionary with full details
        result = metrics.to_dict()
        
        # Cache the result
        self.data_cache[cache_key] = result
        self.cache_timestamp = time.time()
        
        return result
    
    def get_execution_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about executions.
        
        Returns:
            Dictionary of execution statistics
        """
        # Check cache first
        cache_key = "execution_statistics"
        if cache_key in self.data_cache and time.time() - self.cache_timestamp < self.cache_lifetime_seconds:
            return self.data_cache[cache_key]
        
        # Get statistics from metrics collector
        stats = self.metrics_collector.get_statistics()
        
        # Cache the result
        self.data_cache[cache_key] = stats
        self.cache_timestamp = time.time()
        
        return stats
    
    def get_dashboard_state(self) -> Dict[str, Any]:
        """
        Get the current dashboard state.
        
        Returns:
            Dictionary representation of the dashboard state
        """
        return self.dashboard_state.to_dict()
    
    def get_available_symbols(self) -> List[str]:
        """
        Get a list of available symbols.
        
        Returns:
            List of available symbols
        """
        # Check cache first
        cache_key = "available_symbols"
        if cache_key in self.data_cache and time.time() - self.cache_timestamp < self.cache_lifetime_seconds:
            return self.data_cache[cache_key]
        
        # Get all executions and extract unique symbols
        symbols = set()
        for metrics in self.metrics_collector.executions.values():
            symbols.add(metrics.symbol)
        
        result = sorted(list(symbols))
        
        # Cache the result
        self.data_cache[cache_key] = result
        self.cache_timestamp = time.time()
        
        return result
    
    def get_available_strategies(self) -> List[str]:
        """
        Get a list of available strategy IDs.
        
        Returns:
            List of available strategy IDs
        """
        # Check cache first
        cache_key = "available_strategies"
        if cache_key in self.data_cache and time.time() - self.cache_timestamp < self.cache_lifetime_seconds:
            return self.data_cache[cache_key]
        
        # Get all executions and extract unique strategy IDs
        strategies = set()
        for metrics in self.metrics_collector.executions.values():
            strategies.add(metrics.strategy_id)
        
        result = sorted(list(strategies))
        
        # Cache the result
        self.data_cache[cache_key] = result
        self.cache_timestamp = time.time()
        
        return result
    
    def get_performance_metrics(self, time_period_hours: Optional[int] = None) -> Dict[str, Any]:
        """
        Get aggregated performance metrics.
        
        Args:
            time_period_hours: Time period to get metrics for
            
        Returns:
            Dictionary of performance metrics
        """
        # Use dashboard time range if not specified
        if time_period_hours is None:
            time_period_hours = self.dashboard_state.time_range_hours
        
        # Check cache first
        cache_key = f"performance_metrics_{time_period_hours}"
        if cache_key in self.data_cache and time.time() - self.cache_timestamp < self.cache_lifetime_seconds:
            return self.data_cache[cache_key]
        
        # Calculate cutoff time
        cutoff_time = time.time() - (time_period_hours * 3600)
        
        # Filter executions by time period
        recent_executions = [
            metrics for metrics in self.metrics_collector.executions.values()
            if metrics.created_at >= cutoff_time
        ]
        
        # Calculate performance metrics
        total_executed_notional = sum(
            metrics.executed_size * (metrics.average_price or 0)
            for metrics in recent_executions
            if metrics.status == ExecutionStatus.COMPLETED and metrics.average_price is not None
        )
        
        avg_slippage = 0.0
        slippage_count = 0
        for metrics in recent_executions:
            if metrics.performance and metrics.performance.slippage_bps is not None:
                avg_slippage += metrics.performance.slippage_bps
                slippage_count += 1
        
        if slippage_count > 0:
            avg_slippage /= slippage_count
        
        avg_execution_time = 0.0
        execution_time_count = 0
        for metrics in recent_executions:
            if metrics.execution_time_ms is not None:
                avg_execution_time += metrics.execution_time_ms
                execution_time_count += 1
        
        if execution_time_count > 0:
            avg_execution_time /= execution_time_count
        
        # Count executions by quality
        quality_counts = {q.value: 0 for q in ExecutionQuality}
        for metrics in recent_executions:
            if metrics.performance and metrics.performance.quality_rating:
                quality = metrics.performance.quality_rating.value
                quality_counts[quality] = quality_counts.get(quality, 0) + 1
        
        # Build result
        result = {
            "total_executions": len(recent_executions),
            "completed_executions": sum(1 for m in recent_executions if m.status == ExecutionStatus.COMPLETED),
            "active_executions": sum(1 for m in recent_executions if m.status in (ExecutionStatus.ACTIVE, ExecutionStatus.PENDING)),
            "failed_executions": sum(1 for m in recent_executions if m.status in (ExecutionStatus.FAILED, ExecutionStatus.CANCELED)),
            "total_executed_notional": total_executed_notional,
            "average_slippage_bps": avg_slippage,
            "average_execution_time_ms": avg_execution_time,
            "quality_distribution": quality_counts,
            "time_period_hours": time_period_hours
        }
        
        # Cache the result
        self.data_cache[cache_key] = result
        self.cache_timestamp = time.time()
        
        return result


# Public API
__all__ = ['DashboardDataService'] 