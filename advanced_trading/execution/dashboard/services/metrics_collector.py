"""
Metrics Collector Service

This service collects execution metrics from various sources and aggregates them
for display in the dashboard. It handles real-time updates, historical data retrieval,
and performance metric calculations.
"""

import logging
import time
import threading
from typing import Dict, List, Optional, Any, Set, Callable
from collections import deque
import json
import uuid
from datetime import datetime, timedelta

from advanced_trading.execution.dashboard.models.metrics import (
    ExecutionMetrics, OrderMetrics, ExecutionStatus, ExecutionQuality
)

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Service for collecting and managing execution metrics data.
    
    This service collects execution metrics from various sources, processes them,
    and makes them available for the dashboard. It supports real-time updates and
    historical data retrieval.
    """
    
    def __init__(self, 
               max_recent_executions: int = 100,
               history_retention_days: int = 30,
               auto_update_interval_ms: int = 1000):
        """
        Initialize the metrics collector.
        
        Args:
            max_recent_executions: Maximum number of recent executions to keep in memory
            history_retention_days: Number of days to retain historical data
            auto_update_interval_ms: Interval for automatic updates in milliseconds
        """
        self.max_recent_executions = max_recent_executions
        self.history_retention_days = history_retention_days
        self.auto_update_interval_ms = auto_update_interval_ms
        
        # Storage for metrics
        self.executions: Dict[str, ExecutionMetrics] = {}
        self.recent_execution_ids: deque = deque(maxlen=max_recent_executions)
        
        # Listeners for updates
        self.update_listeners: List[Callable[[str, ExecutionMetrics], None]] = []
        
        # Aggregated statistics
        self.stats = {
            "total_executions": 0,
            "active_executions": 0,
            "completed_executions": 0,
            "failed_executions": 0,
            "total_orders": 0,
            "average_slippage_bps": 0.0,
            "average_execution_time_ms": 0.0,
            "total_executed_notional": 0.0,
            "last_update": time.time()
        }
        
        # Auto-update thread
        self._auto_update_running = False
        self._auto_update_thread = None
        
        logger.info("Metrics collector initialized")
    
    def start_auto_update(self) -> None:
        """Start the automatic update thread."""
        if self._auto_update_running:
            return
        
        self._auto_update_running = True
        self._auto_update_thread = threading.Thread(
            target=self._auto_update_worker,
            daemon=True
        )
        self._auto_update_thread.start()
        logger.info("Auto-update thread started")
    
    def stop_auto_update(self) -> None:
        """Stop the automatic update thread."""
        self._auto_update_running = False
        if self._auto_update_thread:
            self._auto_update_thread.join(timeout=2.0)
            self._auto_update_thread = None
        logger.info("Auto-update thread stopped")
    
    def _auto_update_worker(self) -> None:
        """Worker function for the auto-update thread."""
        while self._auto_update_running:
            try:
                self.update_metrics()
            except Exception as e:
                logger.error(f"Error in auto-update: {str(e)}")
            
            # Sleep for the specified interval
            time.sleep(self.auto_update_interval_ms / 1000.0)
    
    def add_update_listener(self, listener: Callable[[str, ExecutionMetrics], None]) -> None:
        """
        Add a listener for execution updates.
        
        Args:
            listener: Callback function that takes execution_id and metrics
        """
        if listener not in self.update_listeners:
            self.update_listeners.append(listener)
    
    def remove_update_listener(self, listener: Callable[[str, ExecutionMetrics], None]) -> None:
        """
        Remove a listener for execution updates.
        
        Args:
            listener: Callback function to remove
        """
        if listener in self.update_listeners:
            self.update_listeners.remove(listener)
    
    def add_execution(self, metrics: ExecutionMetrics) -> str:
        """
        Add or update an execution's metrics.
        
        Args:
            metrics: Execution metrics to add or update
            
        Returns:
            Execution ID
        """
        # Make sure the metrics have an ID
        if not metrics.execution_id:
            metrics.execution_id = str(uuid.uuid4())
        
        execution_id = metrics.execution_id
        
        # Update the metrics summaries
        metrics.update_summary()
        
        # Store the metrics
        self.executions[execution_id] = metrics
        
        # Add to recent executions if not already there
        if execution_id not in self.recent_execution_ids:
            self.recent_execution_ids.append(execution_id)
        
        # Notify listeners
        for listener in self.update_listeners:
            try:
                listener(execution_id, metrics)
            except Exception as e:
                logger.error(f"Error in update listener: {str(e)}")
        
        # Update statistics
        self._update_statistics()
        
        return execution_id
    
    def update_execution(self, execution_id: str, updates: Dict[str, Any]) -> Optional[ExecutionMetrics]:
        """
        Update an existing execution with new data.
        
        Args:
            execution_id: ID of the execution to update
            updates: Dictionary of updates to apply
            
        Returns:
            Updated metrics or None if execution not found
        """
        if execution_id not in self.executions:
            logger.warning(f"Cannot update execution {execution_id}: not found")
            return None
        
        # Get the current metrics
        metrics = self.executions[execution_id]
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(metrics, key):
                setattr(metrics, key, value)
        
        # Update summary data
        metrics.update_summary()
        
        # Store updated metrics
        self.executions[execution_id] = metrics
        
        # Notify listeners
        for listener in self.update_listeners:
            try:
                listener(execution_id, metrics)
            except Exception as e:
                logger.error(f"Error in update listener: {str(e)}")
        
        # Update statistics
        self._update_statistics()
        
        return metrics
    
    def add_order_to_execution(self, execution_id: str, order: OrderMetrics) -> Optional[ExecutionMetrics]:
        """
        Add an order to an existing execution.
        
        Args:
            execution_id: ID of the execution to update
            order: Order metrics to add
            
        Returns:
            Updated metrics or None if execution not found
        """
        if execution_id not in self.executions:
            logger.warning(f"Cannot add order to execution {execution_id}: not found")
            return None
        
        # Get the current metrics
        metrics = self.executions[execution_id]
        
        # Add the order
        metrics.orders.append(order)
        
        # Update summary data
        metrics.update_summary()
        
        # Store updated metrics
        self.executions[execution_id] = metrics
        
        # Notify listeners
        for listener in self.update_listeners:
            try:
                listener(execution_id, metrics)
            except Exception as e:
                logger.error(f"Error in update listener: {str(e)}")
        
        # Update statistics
        self._update_statistics()
        
        return metrics
    
    def get_execution(self, execution_id: str) -> Optional[ExecutionMetrics]:
        """
        Get execution metrics by ID.
        
        Args:
            execution_id: ID of the execution to retrieve
            
        Returns:
            Execution metrics or None if not found
        """
        return self.executions.get(execution_id)
    
    def get_recent_executions(self, 
                           limit: int = None, 
                           filter_func: Callable[[ExecutionMetrics], bool] = None) -> List[ExecutionMetrics]:
        """
        Get a list of recent executions.
        
        Args:
            limit: Maximum number of executions to return (None for all)
            filter_func: Optional function to filter executions
            
        Returns:
            List of execution metrics
        """
        # Get recent execution IDs
        recent_ids = list(self.recent_execution_ids)
        
        # Convert to metrics objects
        executions = [self.executions[id] for id in recent_ids if id in self.executions]
        
        # Apply filter if provided
        if filter_func:
            executions = [m for m in executions if filter_func(m)]
        
        # Apply limit
        if limit is not None:
            executions = executions[:limit]
        
        return executions
    
    def get_active_executions(self) -> List[ExecutionMetrics]:
        """
        Get a list of currently active executions.
        
        Returns:
            List of active execution metrics
        """
        return [
            metrics for metrics in self.executions.values()
            if metrics.status == ExecutionStatus.ACTIVE or metrics.status == ExecutionStatus.PENDING
        ]
    
    def get_executions_by_symbol(self, symbol: str) -> List[ExecutionMetrics]:
        """
        Get executions for a specific symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            List of matching execution metrics
        """
        return [
            metrics for metrics in self.executions.values()
            if metrics.symbol == symbol
        ]
    
    def get_executions_by_status(self, status: ExecutionStatus) -> List[ExecutionMetrics]:
        """
        Get executions with a specific status.
        
        Args:
            status: Execution status to filter by
            
        Returns:
            List of matching execution metrics
        """
        return [
            metrics for metrics in self.executions.values()
            if metrics.status == status
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get aggregated statistics about all executions.
        
        Returns:
            Dictionary of statistics
        """
        return self.stats.copy()
    
    def _update_statistics(self) -> None:
        """Update aggregated statistics based on current executions."""
        # Reset counters
        active_count = 0
        completed_count = 0
        failed_count = 0
        total_orders = 0
        total_slippage = 0.0
        slippage_count = 0
        total_execution_time = 0.0
        execution_time_count = 0
        total_notional = 0.0
        
        # Aggregate statistics
        for metrics in self.executions.values():
            # Count by status
            if metrics.status == ExecutionStatus.COMPLETED:
                completed_count += 1
            elif metrics.status in (ExecutionStatus.ACTIVE, ExecutionStatus.PENDING):
                active_count += 1
            elif metrics.status in (ExecutionStatus.FAILED, ExecutionStatus.CANCELED):
                failed_count += 1
            
            # Count orders
            total_orders += len(metrics.orders)
            
            # Calculate notional
            if metrics.executed_size and metrics.average_price:
                total_notional += metrics.executed_size * metrics.average_price
            
            # Track slippage
            if metrics.performance and metrics.performance.slippage_bps is not None:
                total_slippage += metrics.performance.slippage_bps
                slippage_count += 1
            
            # Track execution time
            if metrics.execution_time_ms is not None:
                total_execution_time += metrics.execution_time_ms
                execution_time_count += 1
        
        # Calculate averages
        avg_slippage = total_slippage / slippage_count if slippage_count > 0 else 0.0
        avg_execution_time = total_execution_time / execution_time_count if execution_time_count > 0 else 0.0
        
        # Update stats
        self.stats.update({
            "total_executions": len(self.executions),
            "active_executions": active_count,
            "completed_executions": completed_count,
            "failed_executions": failed_count,
            "total_orders": total_orders,
            "average_slippage_bps": avg_slippage,
            "average_execution_time_ms": avg_execution_time,
            "total_executed_notional": total_notional,
            "last_update": time.time()
        })
    
    def clear_old_executions(self) -> int:
        """
        Remove executions older than the retention period.
        
        Returns:
            Number of executions removed
        """
        retention_time = time.time() - (self.history_retention_days * 24 * 60 * 60)
        old_ids = [
            execution_id for execution_id, metrics in self.executions.items()
            if metrics.created_at < retention_time
        ]
        
        # Remove old executions
        for execution_id in old_ids:
            if execution_id in self.executions:
                del self.executions[execution_id]
            
            # Also remove from recent IDs if present
            try:
                self.recent_execution_ids.remove(execution_id)
            except ValueError:
                pass
        
        # Update statistics
        if old_ids:
            self._update_statistics()
        
        logger.info(f"Removed {len(old_ids)} old executions")
        return len(old_ids)
    
    def update_metrics(self) -> None:
        """Update metrics from external sources."""
        # This method would integrate with other system components
        # to pull the latest metrics data. Implementation depends
        # on the specific data sources and APIs available.
        pass
    
    def save_metrics(self, file_path: str) -> bool:
        """
        Save metrics to a file.
        
        Args:
            file_path: Path to save the metrics to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert metrics to serializable format
            data = {
                "executions": {
                    id: metrics.to_dict() for id, metrics in self.executions.items()
                },
                "recent_execution_ids": list(self.recent_execution_ids),
                "stats": self.stats,
                "saved_at": time.time()
            }
            
            # Write to file
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved metrics to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving metrics: {str(e)}")
            return False
    
    def load_metrics(self, file_path: str) -> bool:
        """
        Load metrics from a file.
        
        Args:
            file_path: Path to load the metrics from
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Read from file
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Load executions
            executions = {}
            for id, metrics_dict in data.get("executions", {}).items():
                executions[id] = ExecutionMetrics.from_dict(metrics_dict)
            
            # Load recent IDs
            recent_ids = deque(data.get("recent_execution_ids", []), maxlen=self.max_recent_executions)
            
            # Update instance
            self.executions = executions
            self.recent_execution_ids = recent_ids
            
            # Update statistics
            self._update_statistics()
            
            logger.info(f"Loaded metrics from {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error loading metrics: {str(e)}")
            return False


# Public API
__all__ = ['MetricsCollector'] 