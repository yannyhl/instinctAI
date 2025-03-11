"""
Protection Module for Execution Safety

This module provides components for handling execution failures, monitoring execution
for anomalies, and implementing protection mechanisms that can respond to issues during
the trading process. It works in conjunction with the emergency protocols system to
provide comprehensive safety features for the trading system.

Key components:
- ExecutionFailureHandler: Manages and responds to execution failures
- ExecutionAnomalyMonitor: Monitors execution metrics for anomalies
- ProtectionMechanism: Base class for protection mechanisms
- TradingProtection: Central manager for all protection mechanisms
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from advanced_trading.execution.safety.emergency import EmergencyEvent, EmergencyHandler, EmergencyLevel

logger = logging.getLogger(__name__)


class ExecutionFailureType(Enum):
    """Types of execution failures that can occur during trading."""
    CONNECTION_ERROR = "connection_error"
    TIMEOUT = "timeout"
    REJECTION = "rejection"
    PARTIAL_FILL = "partial_fill"
    PRICE_SLIPPAGE = "price_slippage"
    RATE_LIMIT = "rate_limit"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    INVALID_ORDER = "invalid_order"
    EXCHANGE_ERROR = "exchange_error"
    SYSTEM_ERROR = "system_error"
    UNKNOWN = "unknown"


class ExecutionAnomalyType(Enum):
    """Types of anomalies that can be detected during execution monitoring."""
    UNUSUAL_LATENCY = "unusual_latency"
    EXCESSIVE_REJECTIONS = "excessive_rejections"
    UNUSUAL_FILL_RATE = "unusual_fill_rate"
    UNUSUAL_PRICE_IMPACT = "unusual_price_impact"
    UNUSUAL_ORDER_BOOK_CHANGES = "unusual_order_book_changes"
    LIQUIDITY_IMBALANCE = "liquidity_imbalance"
    UNUSUAL_SPREAD = "unusual_spread"
    UNUSUAL_EXECUTION_COST = "unusual_execution_cost"
    EXCESSIVE_ORDER_CANCELLATIONS = "excessive_order_cancellations"
    UNUSUAL_TRADE_VOLUME = "unusual_trade_volume"


@dataclass
class ExecutionFailure:
    """Represents a failure that occurred during order execution."""
    failure_id: str
    timestamp: float
    failure_type: ExecutionFailureType
    exchange_id: str
    order_id: Optional[str] = None
    symbol: Optional[str] = None
    error_message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    resolved: bool = False
    resolution_time: Optional[float] = None
    resolution_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionAnomaly:
    """Represents an anomaly detected during execution monitoring."""
    anomaly_id: str
    timestamp: float
    anomaly_type: ExecutionAnomalyType
    exchange_id: str
    symbol: Optional[str] = None
    expected_value: Optional[float] = None
    actual_value: Optional[float] = None
    threshold: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)
    severity: float = 0.0  # 0.0 to 1.0, with 1.0 being most severe
    acknowledged: bool = False
    resolved: bool = False
    resolution_time: Optional[float] = None


class ProtectionAction(ABC):
    """
    Base class for actions that can be taken in response to execution failures or anomalies.
    Similar to EmergencyAction but specifically tailored for execution protection.
    """
    
    def __init__(self, name: str, description: Optional[str] = None):
        """
        Initialize a protection action.
        
        Args:
            name: Unique name for this action
            description: Optional description of the action
        """
        self.name = name
        self.description = description or ""
        self.enabled = True
        self.execution_history = []
        self.last_execution_time = None
        
    @abstractmethod
    def execute(self, 
                trigger: Union[ExecutionFailure, ExecutionAnomaly],
                context: Dict[str, Any]) -> bool:
        """
        Execute the protection action in response to a failure or anomaly.
        
        Args:
            trigger: The failure or anomaly that triggered this action
            context: Additional context information for the execution
            
        Returns:
            True if the action was executed successfully, False otherwise
        """
        pass
    
    def record_execution(self, 
                         trigger: Union[ExecutionFailure, ExecutionAnomaly],
                         success: bool, 
                         details: Optional[Dict[str, Any]] = None) -> None:
        """
        Record the execution of this action for auditing and debugging.
        
        Args:
            trigger: The failure or anomaly that triggered this action
            success: Whether the execution was successful
            details: Additional details about the execution
        """
        execution_record = {
            "timestamp": time.time(),
            "trigger_type": "failure" if isinstance(trigger, ExecutionFailure) else "anomaly",
            "trigger_id": trigger.failure_id if isinstance(trigger, ExecutionFailure) else trigger.anomaly_id,
            "success": success,
            "details": details or {}
        }
        
        self.execution_history.append(execution_record)
        self.last_execution_time = execution_record["timestamp"]
        
        if len(self.execution_history) > 100:  # Limit history size
            self.execution_history = self.execution_history[-100:]
            
    def disable(self) -> None:
        """Disable this protection action."""
        self.enabled = False
        
    def enable(self) -> None:
        """Enable this protection action."""
        self.enabled = True
        
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of this protection action."""
        return {
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "last_execution_time": self.last_execution_time,
            "execution_count": len(self.execution_history)
        }


class ExecutionFailureHandler:
    """
    Handles execution failures by applying appropriate protection actions
    and coordinating with the emergency system when needed.
    """
    
    def __init__(self, emergency_handler: Optional[EmergencyHandler] = None):
        """
        Initialize an execution failure handler.
        
        Args:
            emergency_handler: Optional emergency handler for escalating severe failures
        """
        self.failure_history: List[ExecutionFailure] = []
        self.failure_counts: Dict[str, int] = {}  # counts by exchange + failure type
        self.actions: Dict[ExecutionFailureType, List[ProtectionAction]] = {
            failure_type: [] for failure_type in ExecutionFailureType
        }
        self.emergency_handler = emergency_handler
        self.emergency_thresholds: Dict[ExecutionFailureType, Tuple[int, EmergencyLevel]] = {}
        self.enabled = True
        
    def register_action(self, failure_type: ExecutionFailureType, action: ProtectionAction) -> None:
        """
        Register a protection action for a specific failure type.
        
        Args:
            failure_type: The type of failure to register the action for
            action: The protection action to register
        """
        if failure_type not in self.actions:
            self.actions[failure_type] = []
            
        if action not in self.actions[failure_type]:
            self.actions[failure_type].append(action)
            
    def set_emergency_threshold(self, 
                              failure_type: ExecutionFailureType, 
                              count: int, 
                              level: EmergencyLevel) -> None:
        """
        Set a threshold for when to trigger an emergency for a specific failure type.
        
        Args:
            failure_type: The type of failure to set a threshold for
            count: The number of failures of this type to trigger an emergency
            level: The emergency level to trigger
        """
        self.emergency_thresholds[failure_type] = (count, level)
        
    def handle_failure(self, failure: ExecutionFailure, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an execution failure by applying registered protection actions
        and potentially triggering an emergency.
        
        Args:
            failure: The execution failure to handle
            context: Additional context information
            
        Returns:
            Dict containing results of handling the failure
        """
        if not self.enabled:
            logger.warning(f"Execution failure handler is disabled. Failure {failure.failure_id} not handled.")
            return {"handled": False, "reason": "handler_disabled"}
        
        # Add to history
        self.failure_history.append(failure)
        if len(self.failure_history) > 1000:  # Limit history size
            self.failure_history = self.failure_history[-1000:]
            
        # Update counts
        key = f"{failure.exchange_id}:{failure.failure_type.value}"
        self.failure_counts[key] = self.failure_counts.get(key, 0) + 1
        
        # Execute actions
        action_results = []
        if failure.failure_type in self.actions:
            for action in self.actions[failure.failure_type]:
                if action.enabled:
                    try:
                        success = action.execute(failure, context)
                        action.record_execution(failure, success)
                        action_results.append({
                            "action": action.name,
                            "success": success
                        })
                    except Exception as e:
                        logger.error(f"Error executing protection action {action.name}: {e}")
                        action_results.append({
                            "action": action.name,
                            "success": False,
                            "error": str(e)
                        })
        
        # Check emergency thresholds
        emergency_triggered = False
        if self.emergency_handler and failure.failure_type in self.emergency_thresholds:
            threshold, level = self.emergency_thresholds[failure.failure_type]
            if self.failure_counts[key] >= threshold:
                # Create emergency event
                event = self.emergency_handler.create_event(
                    level=level,
                    source="execution_failure_handler",
                    description=f"Threshold exceeded for {failure.failure_type.value} failures on {failure.exchange_id}",
                    details={
                        "failure_type": failure.failure_type.value,
                        "exchange_id": failure.exchange_id,
                        "count": self.failure_counts[key],
                        "threshold": threshold,
                        "recent_failure": {
                            "failure_id": failure.failure_id,
                            "timestamp": failure.timestamp,
                            "error_message": failure.error_message
                        }
                    },
                    affected_components=["execution_system", failure.exchange_id],
                    requires_acknowledgment=True
                )
                
                # Handle the emergency event
                self.emergency_handler.handle_event(event)
                emergency_triggered = True
                
        return {
            "handled": True,
            "failure_id": failure.failure_id,
            "action_results": action_results,
            "emergency_triggered": emergency_triggered
        }
        
    def resolve_failure(self, failure_id: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark a failure as resolved.
        
        Args:
            failure_id: The ID of the failure to resolve
            details: Optional details about the resolution
            
        Returns:
            True if the failure was found and resolved, False otherwise
        """
        for failure in self.failure_history:
            if failure.failure_id == failure_id and not failure.resolved:
                failure.resolved = True
                failure.resolution_time = time.time()
                failure.resolution_details = details or {}
                return True
        return False
    
    def get_active_failures(self, 
                          exchange_id: Optional[str] = None,
                          failure_type: Optional[ExecutionFailureType] = None) -> List[ExecutionFailure]:
        """
        Get a list of active (unresolved) failures, optionally filtered.
        
        Args:
            exchange_id: Optional exchange ID to filter by
            failure_type: Optional failure type to filter by
            
        Returns:
            List of active failures matching the filters
        """
        active_failures = [f for f in self.failure_history if not f.resolved]
        
        if exchange_id:
            active_failures = [f for f in active_failures if f.exchange_id == exchange_id]
            
        if failure_type:
            active_failures = [f for f in active_failures if f.failure_type == failure_type]
            
        return active_failures
    
    def get_failure_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about failures handled by this handler.
        
        Returns:
            Dictionary with failure statistics
        """
        total_failures = len(self.failure_history)
        active_failures = len([f for f in self.failure_history if not f.resolved])
        
        by_type = {}
        for failure_type in ExecutionFailureType:
            failures = [f for f in self.failure_history if f.failure_type == failure_type]
            active = [f for f in failures if not f.resolved]
            by_type[failure_type.value] = {
                "total": len(failures),
                "active": len(active)
            }
            
        by_exchange = {}
        unique_exchanges = set(f.exchange_id for f in self.failure_history)
        for exchange in unique_exchanges:
            failures = [f for f in self.failure_history if f.exchange_id == exchange]
            active = [f for f in failures if not f.resolved]
            by_exchange[exchange] = {
                "total": len(failures),
                "active": len(active)
            }
            
        return {
            "total_failures": total_failures,
            "active_failures": active_failures,
            "by_type": by_type,
            "by_exchange": by_exchange
        }
        
    def disable(self) -> None:
        """Disable this failure handler."""
        self.enabled = False
        
    def enable(self) -> None:
        """Enable this failure handler."""
        self.enabled = True


class ExecutionAnomalyMonitor:
    """
    Monitors execution metrics for anomalies and triggers protection actions
    when anomalies are detected.
    """
    
    def __init__(self, emergency_handler: Optional[EmergencyHandler] = None):
        """
        Initialize an execution anomaly monitor.
        
        Args:
            emergency_handler: Optional emergency handler for escalating severe anomalies
        """
        self.anomaly_history: List[ExecutionAnomaly] = []
        self.thresholds: Dict[ExecutionAnomalyType, Dict[str, float]] = {}
        self.baseline_metrics: Dict[str, Dict[str, float]] = {}  # exchange:symbol:metric:value
        self.actions: Dict[ExecutionAnomalyType, List[ProtectionAction]] = {
            anomaly_type: [] for anomaly_type in ExecutionAnomalyType
        }
        self.emergency_handler = emergency_handler
        self.emergency_thresholds: Dict[ExecutionAnomalyType, Tuple[float, EmergencyLevel]] = {}
        self.enabled = True
        
    def register_action(self, anomaly_type: ExecutionAnomalyType, action: ProtectionAction) -> None:
        """
        Register a protection action for a specific anomaly type.
        
        Args:
            anomaly_type: The type of anomaly to register the action for
            action: The protection action to register
        """
        if anomaly_type not in self.actions:
            self.actions[anomaly_type] = []
            
        if action not in self.actions[anomaly_type]:
            self.actions[anomaly_type].append(action)
            
    def set_threshold(self, 
                    anomaly_type: ExecutionAnomalyType, 
                    threshold: float,
                    exchange_id: Optional[str] = None,
                    symbol: Optional[str] = None) -> None:
        """
        Set a threshold for detecting a specific type of anomaly.
        
        Args:
            anomaly_type: The type of anomaly to set a threshold for
            threshold: The threshold value for this anomaly type
            exchange_id: Optional exchange ID to limit this threshold to
            symbol: Optional symbol to limit this threshold to
        """
        key = f"{exchange_id or '*'}:{symbol or '*'}"
        
        if anomaly_type not in self.thresholds:
            self.thresholds[anomaly_type] = {}
            
        self.thresholds[anomaly_type][key] = threshold
        
    def set_emergency_threshold(self, 
                              anomaly_type: ExecutionAnomalyType, 
                              severity: float, 
                              level: EmergencyLevel) -> None:
        """
        Set a threshold for when to trigger an emergency for a specific anomaly type.
        
        Args:
            anomaly_type: The type of anomaly to set a threshold for
            severity: The severity threshold (0.0 to 1.0) to trigger an emergency
            level: The emergency level to trigger
        """
        self.emergency_thresholds[anomaly_type] = (severity, level)
        
    def update_baseline(self, 
                       exchange_id: str, 
                       symbol: str, 
                       metric: str, 
                       value: float) -> None:
        """
        Update the baseline value for a specific metric.
        
        Args:
            exchange_id: The exchange ID
            symbol: The trading symbol
            metric: The metric name
            value: The baseline value for this metric
        """
        exchange_key = f"{exchange_id}:{symbol}"
        
        if exchange_key not in self.baseline_metrics:
            self.baseline_metrics[exchange_key] = {}
            
        self.baseline_metrics[exchange_key][metric] = value
        
    def check_metric(self, 
                    exchange_id: str,
                    symbol: str, 
                    metric: str, 
                    value: float,
                    anomaly_type: ExecutionAnomalyType,
                    context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check a metric value against its baseline and thresholds.
        
        Args:
            exchange_id: The exchange ID
            symbol: The trading symbol
            metric: The metric name
            value: The current value of the metric
            anomaly_type: The type of anomaly to check for
            context: Additional context information
            
        Returns:
            None if no anomaly detected, or a dictionary with anomaly information
        """
        if not self.enabled:
            return None
            
        # Get baseline value
        exchange_key = f"{exchange_id}:{symbol}"
        baseline = None
        if exchange_key in self.baseline_metrics and metric in self.baseline_metrics[exchange_key]:
            baseline = self.baseline_metrics[exchange_key][metric]
        
        # Get threshold
        threshold = None
        if anomaly_type in self.thresholds:
            # Try specific threshold first, then more general ones
            key_specific = f"{exchange_id}:{symbol}"
            key_exchange = f"{exchange_id}:*"
            key_symbol = f"*:{symbol}"
            key_general = "*:*"
            
            if key_specific in self.thresholds[anomaly_type]:
                threshold = self.thresholds[anomaly_type][key_specific]
            elif key_exchange in self.thresholds[anomaly_type]:
                threshold = self.thresholds[anomaly_type][key_exchange]
            elif key_symbol in self.thresholds[anomaly_type]:
                threshold = self.thresholds[anomaly_type][key_symbol]
            elif key_general in self.thresholds[anomaly_type]:
                threshold = self.thresholds[anomaly_type][key_general]
                
        if threshold is None:
            return None  # No threshold defined for this anomaly type
            
        # Check for anomaly
        anomaly_detected = False
        severity = 0.0
        expected_value = baseline
        
        if baseline is not None:
            # Calculate percent difference from baseline
            percent_diff = abs((value - baseline) / baseline) if baseline != 0 else abs(value)
            
            # Anomaly if difference exceeds threshold
            if percent_diff > threshold:
                anomaly_detected = True
                # Severity grows with the extent to which threshold is exceeded
                severity = min(1.0, percent_diff / threshold - 1.0)
        else:
            # No baseline, just check absolute value against threshold
            if abs(value) > threshold:
                anomaly_detected = True
                severity = min(1.0, abs(value) / threshold - 1.0)
                
        if not anomaly_detected:
            return None
            
        # Create anomaly record
        anomaly = ExecutionAnomaly(
            anomaly_id=f"{exchange_id}:{symbol}:{anomaly_type.value}:{int(time.time())}",
            timestamp=time.time(),
            anomaly_type=anomaly_type,
            exchange_id=exchange_id,
            symbol=symbol,
            expected_value=expected_value,
            actual_value=value,
            threshold=threshold,
            details={
                "metric": metric,
                "context": context
            },
            severity=severity
        )
        
        self.anomaly_history.append(anomaly)
        if len(self.anomaly_history) > 1000:  # Limit history size
            self.anomaly_history = self.anomaly_history[-1000:]
            
        # Execute actions
        action_results = []
        if anomaly.anomaly_type in self.actions:
            for action in self.actions[anomaly.anomaly_type]:
                if action.enabled:
                    try:
                        success = action.execute(anomaly, context)
                        action.record_execution(anomaly, success)
                        action_results.append({
                            "action": action.name,
                            "success": success
                        })
                    except Exception as e:
                        logger.error(f"Error executing protection action {action.name}: {e}")
                        action_results.append({
                            "action": action.name,
                            "success": False,
                            "error": str(e)
                        })
        
        # Check emergency thresholds
        emergency_triggered = False
        if self.emergency_handler and anomaly.anomaly_type in self.emergency_thresholds:
            threshold, level = self.emergency_thresholds[anomaly.anomaly_type]
            if anomaly.severity >= threshold:
                # Create emergency event
                event = self.emergency_handler.create_event(
                    level=level,
                    source="execution_anomaly_monitor",
                    description=f"{anomaly.anomaly_type.value} detected on {exchange_id} for {symbol}",
                    details={
                        "anomaly_type": anomaly.anomaly_type.value,
                        "exchange_id": exchange_id,
                        "symbol": symbol,
                        "metric": metric,
                        "actual_value": value,
                        "expected_value": expected_value,
                        "threshold": threshold,
                        "severity": severity
                    },
                    affected_components=["execution_system", exchange_id],
                    requires_acknowledgment=True
                )
                
                # Handle the emergency event
                self.emergency_handler.handle_event(event)
                emergency_triggered = True
                
        return {
            "anomaly": anomaly,
            "action_results": action_results,
            "emergency_triggered": emergency_triggered
        }
        
    def resolve_anomaly(self, anomaly_id: str) -> bool:
        """
        Mark an anomaly as resolved.
        
        Args:
            anomaly_id: The ID of the anomaly to resolve
            
        Returns:
            True if the anomaly was found and resolved, False otherwise
        """
        for anomaly in self.anomaly_history:
            if anomaly.anomaly_id == anomaly_id and not anomaly.resolved:
                anomaly.resolved = True
                anomaly.resolution_time = time.time()
                return True
        return False
    
    def get_active_anomalies(self, 
                           exchange_id: Optional[str] = None,
                           symbol: Optional[str] = None,
                           anomaly_type: Optional[ExecutionAnomalyType] = None,
                           min_severity: float = 0.0) -> List[ExecutionAnomaly]:
        """
        Get a list of active (unresolved) anomalies, optionally filtered.
        
        Args:
            exchange_id: Optional exchange ID to filter by
            symbol: Optional symbol to filter by
            anomaly_type: Optional anomaly type to filter by
            min_severity: Minimum severity threshold
            
        Returns:
            List of active anomalies matching the filters
        """
        active_anomalies = [a for a in self.anomaly_history if not a.resolved]
        
        if exchange_id:
            active_anomalies = [a for a in active_anomalies if a.exchange_id == exchange_id]
            
        if symbol:
            active_anomalies = [a for a in active_anomalies if a.symbol == symbol]
            
        if anomaly_type:
            active_anomalies = [a for a in active_anomalies if a.anomaly_type == anomaly_type]
            
        if min_severity > 0:
            active_anomalies = [a for a in active_anomalies if a.severity >= min_severity]
            
        return active_anomalies
    
    def disable(self) -> None:
        """Disable this anomaly monitor."""
        self.enabled = False
        
    def enable(self) -> None:
        """Enable this anomaly monitor."""
        self.enabled = True


class TradingProtection:
    """
    Central manager for all protection mechanisms, including failure handling
    and anomaly monitoring.
    """
    
    def __init__(self, emergency_handler: Optional[EmergencyHandler] = None):
        """
        Initialize a trading protection manager.
        
        Args:
            emergency_handler: Optional emergency handler for escalating severe issues
        """
        self.emergency_handler = emergency_handler
        self.failure_handler = ExecutionFailureHandler(emergency_handler)
        self.anomaly_monitor = ExecutionAnomalyMonitor(emergency_handler)
        self.protection_actions: Dict[str, ProtectionAction] = {}
        self.enabled = True
        
    def register_protection_action(self, action: ProtectionAction) -> None:
        """
        Register a protection action that can be used by both the failure handler
        and the anomaly monitor.
        
        Args:
            action: The protection action to register
        """
        self.protection_actions[action.name] = action
        
    def configure_failure_protection(self, 
                                  failure_type: ExecutionFailureType, 
                                  action_name: str) -> None:
        """
        Configure a protection action for a specific failure type.
        
        Args:
            failure_type: The type of failure to configure protection for
            action_name: The name of the protection action to use
        """
        if action_name in self.protection_actions:
            self.failure_handler.register_action(failure_type, self.protection_actions[action_name])
        else:
            logger.warning(f"Protection action '{action_name}' not found.")
            
    def configure_anomaly_protection(self, 
                                   anomaly_type: ExecutionAnomalyType, 
                                   action_name: str) -> None:
        """
        Configure a protection action for a specific anomaly type.
        
        Args:
            anomaly_type: The type of anomaly to configure protection for
            action_name: The name of the protection action to use
        """
        if action_name in self.protection_actions:
            self.anomaly_monitor.register_action(anomaly_type, self.protection_actions[action_name])
        else:
            logger.warning(f"Protection action '{action_name}' not found.")
            
    def report_failure(self, 
                     failure_type: ExecutionFailureType,
                     exchange_id: str,
                     error_message: str,
                     order_id: Optional[str] = None,
                     symbol: Optional[str] = None,
                     details: Optional[Dict[str, Any]] = None,
                     context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Report an execution failure and handle it.
        
        Args:
            failure_type: The type of failure
            exchange_id: The ID of the exchange where the failure occurred
            error_message: The error message from the failure
            order_id: Optional order ID associated with the failure
            symbol: Optional symbol associated with the failure
            details: Optional additional details about the failure
            context: Optional context information for handling the failure
            
        Returns:
            Dictionary with results of handling the failure
        """
        if not self.enabled:
            logger.warning("Trading protection is disabled. Failure not handled.")
            return {"handled": False, "reason": "protection_disabled"}
            
        failure = ExecutionFailure(
            failure_id=f"{exchange_id}:{failure_type.value}:{int(time.time())}",
            timestamp=time.time(),
            failure_type=failure_type,
            exchange_id=exchange_id,
            order_id=order_id,
            symbol=symbol,
            error_message=error_message,
            details=details or {}
        )
        
        return self.failure_handler.handle_failure(failure, context or {})
        
    def check_metric(self, 
                    exchange_id: str,
                    symbol: str, 
                    metric: str, 
                    value: float,
                    anomaly_type: ExecutionAnomalyType,
                    context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Check a metric for anomalies.
        
        Args:
            exchange_id: The exchange ID
            symbol: The trading symbol
            metric: The metric name
            value: The current value of the metric
            anomaly_type: The type of anomaly to check for
            context: Optional additional context information
            
        Returns:
            None if no anomaly detected, or a dictionary with anomaly information
        """
        if not self.enabled:
            return None
            
        return self.anomaly_monitor.check_metric(
            exchange_id=exchange_id,
            symbol=symbol,
            metric=metric,
            value=value,
            anomaly_type=anomaly_type,
            context=context or {}
        )
        
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the trading protection system.
        
        Returns:
            Dictionary with status information
        """
        actions_status = {name: action.get_status() for name, action in self.protection_actions.items()}
        
        active_failures = len(self.failure_handler.get_active_failures())
        active_anomalies = len(self.anomaly_monitor.get_active_anomalies())
        
        return {
            "enabled": self.enabled,
            "active_failures": active_failures,
            "active_anomalies": active_anomalies,
            "protection_actions": actions_status
        }
        
    def disable(self) -> None:
        """Disable the trading protection system."""
        self.enabled = False
        self.failure_handler.disable()
        self.anomaly_monitor.disable()
        
    def enable(self) -> None:
        """Enable the trading protection system."""
        self.enabled = True
        self.failure_handler.enable()
        self.anomaly_monitor.enable()


# Common protection actions

class PauseExchangeTradingAction(ProtectionAction):
    """Protection action that pauses trading on a specific exchange."""
    
    def __init__(self, name: str = "pause_exchange_trading", description: Optional[str] = None):
        """
        Initialize a pause exchange trading action.
        
        Args:
            name: Unique name for this action
            description: Optional description of the action
        """
        super().__init__(name, description or "Temporarily pause trading on an exchange")
        
    def execute(self, 
                trigger: Union[ExecutionFailure, ExecutionAnomaly],
                context: Dict[str, Any]) -> bool:
        """
        Execute the protection action to pause trading on an exchange.
        
        Args:
            trigger: The failure or anomaly that triggered this action
            context: Additional context information for the execution
            
        Returns:
            True if the action was executed successfully, False otherwise
        """
        exchange_id = trigger.exchange_id
        logger.warning(f"Pausing trading on exchange {exchange_id} due to protection action")
        
        # Implementation would depend on the exchange manager component
        # For now, we'll just log the action
        logger.info(f"PROTECTION ACTION: Paused trading on {exchange_id}")
        
        return True


class RateThrottlingAction(ProtectionAction):
    """Protection action that reduces the rate of order submissions."""
    
    def __init__(self, 
               name: str = "rate_throttling", 
               description: Optional[str] = None,
               throttle_factor: float = 0.5,
               min_delay_ms: int = 500):
        """
        Initialize a rate throttling action.
        
        Args:
            name: Unique name for this action
            description: Optional description of the action
            throttle_factor: Factor to reduce order submission rate by (0.5 = half the rate)
            min_delay_ms: Minimum delay between orders in milliseconds
        """
        super().__init__(name, description or "Reduce order submission rate")
        self.throttle_factor = throttle_factor
        self.min_delay_ms = min_delay_ms
        
    def execute(self, 
                trigger: Union[ExecutionFailure, ExecutionAnomaly],
                context: Dict[str, Any]) -> bool:
        """
        Execute the protection action to throttle order submission rate.
        
        Args:
            trigger: The failure or anomaly that triggered this action
            context: Additional context information for the execution
            
        Returns:
            True if the action was executed successfully, False otherwise
        """
        exchange_id = trigger.exchange_id
        logger.warning(f"Throttling order submission rate for {exchange_id} due to protection action")
        
        # Implementation would depend on the order submission component
        # For now, we'll just log the action
        logger.info(f"PROTECTION ACTION: Throttled order rate on {exchange_id} to factor {self.throttle_factor}")
        
        return True


class OrderSizeReductionAction(ProtectionAction):
    """Protection action that reduces the size of orders."""
    
    def __init__(self, 
               name: str = "order_size_reduction", 
               description: Optional[str] = None,
               reduction_factor: float = 0.5,
               min_orders: int = 2):
        """
        Initialize an order size reduction action.
        
        Args:
            name: Unique name for this action
            description: Optional description of the action
            reduction_factor: Factor to reduce order sizes by (0.5 = half the size)
            min_orders: Minimum number of orders to split into
        """
        super().__init__(name, description or "Reduce order sizes and split into smaller orders")
        self.reduction_factor = reduction_factor
        self.min_orders = min_orders
        
    def execute(self, 
                trigger: Union[ExecutionFailure, ExecutionAnomaly],
                context: Dict[str, Any]) -> bool:
        """
        Execute the protection action to reduce order sizes.
        
        Args:
            trigger: The failure or anomaly that triggered this action
            context: Additional context information for the execution
            
        Returns:
            True if the action was executed successfully, False otherwise
        """
        exchange_id = trigger.exchange_id
        symbol = getattr(trigger, "symbol", None)
        target = f"{exchange_id}" + (f":{symbol}" if symbol else "")
        
        logger.warning(f"Reducing order sizes for {target} due to protection action")
        
        # Implementation would depend on the order generation component
        # For now, we'll just log the action
        logger.info(f"PROTECTION ACTION: Reduced order sizes on {target} to factor {self.reduction_factor}")
        
        return True


# Public API
__all__ = [
    'ExecutionFailureType',
    'ExecutionAnomalyType',
    'ExecutionFailure',
    'ExecutionAnomaly',
    'ProtectionAction',
    'ExecutionFailureHandler',
    'ExecutionAnomalyMonitor',
    'TradingProtection',
    'PauseExchangeTradingAction',
    'RateThrottlingAction',
    'OrderSizeReductionAction',
] 