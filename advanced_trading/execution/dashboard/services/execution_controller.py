"""
Execution Controller Service

This service provides control functionality for the dashboard, allowing users to
interact with and control active executions. It enables operations like starting,
pausing, resuming, and canceling executions.
"""

import logging
import time
import uuid
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import threading

from advanced_trading.execution.dashboard.models.metrics import (
    ExecutionMetrics, OrderMetrics, ExecutionStatus, ExecutionQuality
)
from advanced_trading.execution.dashboard.services.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)


class ControlAction(Enum):
    """Types of control actions for executions."""
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"
    MODIFY = "modify"
    EMERGENCY_STOP = "emergency_stop"


class ExecutionController:
    """
    Service for controlling execution operations.
    
    This service provides the ability to start, pause, resume, and cancel
    executions, as well as modify execution parameters.
    """
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        """
        Initialize the execution controller.
        
        Args:
            metrics_collector: Optional metrics collector to use
        """
        self.metrics_collector = metrics_collector or MetricsCollector()
        
        # Track execution controllers
        self.active_controllers: Dict[str, Any] = {}
        
        # Execution and control hooks
        self.execution_hooks: Dict[str, Callable] = {}
        
        # Control locks to prevent concurrent control actions
        self.control_locks: Dict[str, threading.Lock] = {}
        
        # Action history for auditing
        self.action_history: List[Dict[str, Any]] = []
        
        logger.info("Execution controller initialized")
    
    def register_execution_hook(self, action_type: str, hook: Callable) -> None:
        """
        Register a hook for execution actions.
        
        Args:
            action_type: Type of action to hook into
            hook: Callback function for the action
        """
        self.execution_hooks[action_type] = hook
        logger.info(f"Registered execution hook for {action_type}")
    
    def create_execution(self, 
                      symbol: str,
                      strategy_id: str,
                      account_id: str,
                      params: Dict[str, Any]) -> str:
        """
        Create a new execution.
        
        Args:
            symbol: Symbol to execute on
            strategy_id: ID of the strategy to use
            account_id: ID of the account to use
            params: Additional execution parameters
            
        Returns:
            ID of the created execution
        """
        # Generate a new execution ID
        execution_id = str(uuid.uuid4())
        
        # Create base metrics
        metrics = ExecutionMetrics(
            execution_id=execution_id,
            symbol=symbol,
            strategy_id=strategy_id,
            account_id=account_id,
            status=ExecutionStatus.PENDING,
            tags=params.get("tags", [])
        )
        
        # Add to metrics collector
        self.metrics_collector.add_execution(metrics)
        
        # Create control lock
        self.control_locks[execution_id] = threading.Lock()
        
        # Record action
        self._record_action(execution_id, ControlAction.START, params)
        
        # Call execution hook if registered
        if "create" in self.execution_hooks:
            try:
                self.execution_hooks["create"](execution_id, symbol, strategy_id, account_id, params)
            except Exception as e:
                logger.error(f"Error in create execution hook: {str(e)}")
        
        logger.info(f"Created execution {execution_id} for {symbol} using strategy {strategy_id}")
        return execution_id
    
    def control_execution(self, 
                       execution_id: str,
                       action: ControlAction,
                       params: Optional[Dict[str, Any]] = None) -> bool:
        """
        Control an active execution.
        
        Args:
            execution_id: ID of the execution to control
            action: Control action to perform
            params: Additional parameters for the action
            
        Returns:
            True if the action was successful, False otherwise
        """
        if execution_id not in self.metrics_collector.executions:
            logger.warning(f"Cannot control execution {execution_id}: not found")
            return False
        
        # Get lock for this execution
        if execution_id not in self.control_locks:
            self.control_locks[execution_id] = threading.Lock()
        
        lock = self.control_locks[execution_id]
        
        # Execute with lock to prevent concurrent actions
        with lock:
            # Get current metrics
            metrics = self.metrics_collector.get_execution(execution_id)
            
            # Check if action is valid for current status
            if not self._is_action_valid(metrics.status, action):
                logger.warning(f"Invalid action {action.value} for execution {execution_id} in status {metrics.status.value}")
                return False
            
            # Prepare updates based on action
            updates = {}
            
            if action == ControlAction.START:
                updates["status"] = ExecutionStatus.ACTIVE
            elif action == ControlAction.PAUSE:
                updates["status"] = ExecutionStatus.PENDING
            elif action == ControlAction.RESUME:
                updates["status"] = ExecutionStatus.ACTIVE
            elif action == ControlAction.CANCEL:
                updates["status"] = ExecutionStatus.CANCELED
            elif action == ControlAction.EMERGENCY_STOP:
                updates["status"] = ExecutionStatus.CANCELED
            
            # Update metrics
            self.metrics_collector.update_execution(execution_id, updates)
            
            # Record action
            self._record_action(execution_id, action, params)
            
            # Call execution hook if registered
            hook_name = action.value
            if hook_name in self.execution_hooks:
                try:
                    self.execution_hooks[hook_name](execution_id, params)
                except Exception as e:
                    logger.error(f"Error in {hook_name} execution hook: {str(e)}")
                    return False
            
            logger.info(f"Executed {action.value} on execution {execution_id}")
            return True
    
    def modify_execution_params(self, 
                             execution_id: str,
                             modifications: Dict[str, Any]) -> bool:
        """
        Modify parameters for an active execution.
        
        Args:
            execution_id: ID of the execution to modify
            modifications: Parameter modifications to apply
            
        Returns:
            True if the modifications were successful, False otherwise
        """
        return self.control_execution(
            execution_id,
            ControlAction.MODIFY,
            params=modifications
        )
    
    def emergency_stop_all(self) -> Dict[str, bool]:
        """
        Emergency stop all active executions.
        
        Returns:
            Dictionary mapping execution IDs to success status
        """
        active_executions = self.metrics_collector.get_active_executions()
        results = {}
        
        for metrics in active_executions:
            success = self.control_execution(
                metrics.execution_id,
                ControlAction.EMERGENCY_STOP,
                params={"reason": "emergency_stop_all"}
            )
            results[metrics.execution_id] = success
        
        logger.warning(f"Emergency stopped all active executions: {len(active_executions)} executions")
        return results
    
    def add_order(self, 
                execution_id: str,
                order: OrderMetrics) -> bool:
        """
        Add an order to an execution.
        
        Args:
            execution_id: ID of the execution to add the order to
            order: Order to add
            
        Returns:
            True if the order was added successfully, False otherwise
        """
        if execution_id not in self.metrics_collector.executions:
            logger.warning(f"Cannot add order to execution {execution_id}: not found")
            return False
        
        # Add order to execution
        self.metrics_collector.add_order_to_execution(execution_id, order)
        logger.info(f"Added order {order.order_id} to execution {execution_id}")
        return True
    
    def update_order(self, 
                   execution_id: str,
                   order_id: str,
                   updates: Dict[str, Any]) -> bool:
        """
        Update an order in an execution.
        
        Args:
            execution_id: ID of the execution containing the order
            order_id: ID of the order to update
            updates: Updates to apply to the order
            
        Returns:
            True if the order was updated successfully, False otherwise
        """
        if execution_id not in self.metrics_collector.executions:
            logger.warning(f"Cannot update order in execution {execution_id}: not found")
            return False
        
        # Get execution
        metrics = self.metrics_collector.get_execution(execution_id)
        
        # Find the order
        order_idx = None
        for i, order in enumerate(metrics.orders):
            if order.order_id == order_id:
                order_idx = i
                break
        
        if order_idx is None:
            logger.warning(f"Cannot update order {order_id} in execution {execution_id}: order not found")
            return False
        
        # Update the order
        for key, value in updates.items():
            if hasattr(metrics.orders[order_idx], key):
                setattr(metrics.orders[order_idx], key, value)
        
        # Update the execution
        metrics.update_summary()
        self.metrics_collector.add_execution(metrics)
        
        logger.info(f"Updated order {order_id} in execution {execution_id}")
        return True
    
    def get_action_history(self, 
                        execution_id: Optional[str] = None,
                        limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get action history for auditing.
        
        Args:
            execution_id: Optional ID to filter by
            limit: Maximum number of actions to return
            
        Returns:
            List of action history entries
        """
        # Filter by execution ID if provided
        if execution_id:
            history = [entry for entry in self.action_history if entry["execution_id"] == execution_id]
        else:
            history = self.action_history.copy()
        
        # Sort by timestamp (newest first)
        history.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Apply limit
        if limit:
            history = history[:limit]
        
        return history
    
    def _is_action_valid(self, status: ExecutionStatus, action: ControlAction) -> bool:
        """
        Check if an action is valid for the current status.
        
        Args:
            status: Current execution status
            action: Action to check
            
        Returns:
            True if the action is valid, False otherwise
        """
        # Emergency stop is always valid
        if action == ControlAction.EMERGENCY_STOP:
            return True
        
        # Modify is valid for pending and active executions
        if action == ControlAction.MODIFY:
            return status in (ExecutionStatus.PENDING, ExecutionStatus.ACTIVE)
        
        # Start is only valid for pending executions
        if action == ControlAction.START:
            return status == ExecutionStatus.PENDING
        
        # Pause is only valid for active executions
        if action == ControlAction.PAUSE:
            return status == ExecutionStatus.ACTIVE
        
        # Resume is only valid for pending executions
        if action == ControlAction.RESUME:
            return status == ExecutionStatus.PENDING
        
        # Cancel is valid for pending and active executions
        if action == ControlAction.CANCEL:
            return status in (ExecutionStatus.PENDING, ExecutionStatus.ACTIVE)
        
        # Unknown action
        return False
    
    def _record_action(self, 
                    execution_id: str,
                    action: ControlAction,
                    params: Optional[Dict[str, Any]] = None) -> None:
        """
        Record an action in the history.
        
        Args:
            execution_id: ID of the execution
            action: Action that was performed
            params: Parameters for the action
        """
        self.action_history.append({
            "execution_id": execution_id,
            "action": action.value,
            "params": params or {},
            "timestamp": time.time(),
            "success": True
        })
        
        # Keep history to a reasonable size
        if len(self.action_history) > 1000:
            self.action_history = self.action_history[-1000:]


# Public API
__all__ = [
    'ControlAction',
    'ExecutionController'
] 