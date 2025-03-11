"""
Health Checker Module

This module provides health checking capabilities for system components,
allowing the system to monitor the health of various components and
take appropriate action when issues are detected.
"""

import os
import time
import logging
import datetime
import threading
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
from collections import deque

from advanced_trading.core.observability.logging import setup_logger

logger = logging.getLogger('advanced_trading.core.monitoring.health_checker')


class HealthStatus(Enum):
    """Health status values."""
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheckResult:
    """
    Represents the result of a health check.
    
    Attributes:
        component: Name of the component checked
        status: Health status of the component
        message: Detailed message about the health status
        timestamp: When the check was performed
        metadata: Additional information about the check
        check_duration_ms: How long the check took to perform
    """
    
    def __init__(self, 
               component: str,
               status: HealthStatus,
               message: str,
               metadata: Optional[Dict[str, Any]] = None,
               check_duration_ms: Optional[float] = None):
        """
        Initialize a health check result.
        
        Args:
            component: Name of the component checked
            status: Health status of the component
            message: Detailed message about the health status
            metadata: Additional information about the check
            check_duration_ms: How long the check took to perform
        """
        self.component = component
        self.status = status
        self.message = message
        self.timestamp = datetime.datetime.now()
        self.metadata = metadata or {}
        self.check_duration_ms = check_duration_ms
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a dictionary."""
        return {
            'component': self.component,
            'status': self.status.value,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            'check_duration_ms': self.check_duration_ms
        }


class HealthCheck:
    """
    Represents a health check for a specific component.
    
    A health check is a function that checks the health of a component
    and returns a HealthCheckResult.
    """
    
    def __init__(self, 
               component: str,
               check_function: Callable[[], HealthCheckResult],
               interval_seconds: int = 60,
               timeout_seconds: int = 10,
               description: str = ""):
        """
        Initialize a health check.
        
        Args:
            component: Name of the component to check
            check_function: Function that performs the health check
            interval_seconds: How often to perform the check in seconds
            timeout_seconds: Maximum time allowed for the check in seconds
            description: Description of the health check
        """
        self.component = component
        self.check_function = check_function
        self.interval_seconds = interval_seconds
        self.timeout_seconds = timeout_seconds
        self.description = description
        self.last_result: Optional[HealthCheckResult] = None
        self.last_check_time: Optional[datetime.datetime] = None
        self.error_count = 0
        self.success_count = 0
    
    def run(self) -> HealthCheckResult:
        """
        Run the health check and return the result.
        
        Returns:
            The result of the health check
        """
        start_time = time.time()
        
        try:
            # Run the check function with timeout
            result = self._run_with_timeout()
            
            # Update stats
            if result.status == HealthStatus.HEALTHY:
                self.success_count += 1
                self.error_count = 0  # Reset error count on success
            else:
                self.error_count += 1
            
            # Update result
            self.last_result = result
            self.last_check_time = datetime.datetime.now()
            
            return result
        
        except Exception as e:
            logger.error(f"Health check failed for {self.component}: {str(e)}")
            
            # Create error result
            duration_ms = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                component=self.component,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                check_duration_ms=duration_ms
            )
            
            # Update stats
            self.error_count += 1
            
            # Update result
            self.last_result = result
            self.last_check_time = datetime.datetime.now()
            
            return result
    
    def _run_with_timeout(self) -> HealthCheckResult:
        """Run the check function with a timeout."""
        start_time = time.time()
        
        try:
            result = self.check_function()
            duration_ms = (time.time() - start_time) * 1000
            
            # Add duration to result if not already set
            if result.check_duration_ms is None:
                result.check_duration_ms = duration_ms
            
            return result
        
        except TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component=self.component,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check timed out after {self.timeout_seconds} seconds",
                check_duration_ms=duration_ms
            )


class HealthChecker:
    """
    Manages health checks for system components.
    
    The HealthChecker is responsible for:
    1. Registering health checks for components
    2. Running health checks on a schedule
    3. Maintaining health check results
    4. Providing overall system health status
    """
    
    def __init__(self, 
               default_interval_seconds: int = 60,
               default_timeout_seconds: int = 10,
               history_size: int = 100):
        """
        Initialize the HealthChecker.
        
        Args:
            default_interval_seconds: Default interval for health checks in seconds
            default_timeout_seconds: Default timeout for health checks in seconds
            history_size: Number of historical check results to keep per component
        """
        self.checks: Dict[str, HealthCheck] = {}
        self.default_interval_seconds = default_interval_seconds
        self.default_timeout_seconds = default_timeout_seconds
        self.history_size = history_size
        self.check_history: Dict[str, deque] = {}
        self.running = False
        self.check_thread = None
        
        logger.info(f"HealthChecker initialized with default interval {default_interval_seconds}s, "
                   f"default timeout {default_timeout_seconds}s")
    
    def register_check(self, 
                     component: str,
                     check_function: Callable[[], HealthCheckResult],
                     interval_seconds: Optional[int] = None,
                     timeout_seconds: Optional[int] = None,
                     description: str = "") -> None:
        """
        Register a health check for a component.
        
        Args:
            component: Name of the component to check
            check_function: Function that performs the health check
            interval_seconds: How often to perform the check in seconds
            timeout_seconds: Maximum time allowed for the check in seconds
            description: Description of the health check
        """
        interval = interval_seconds or self.default_interval_seconds
        timeout = timeout_seconds or self.default_timeout_seconds
        
        health_check = HealthCheck(
            component=component,
            check_function=check_function,
            interval_seconds=interval,
            timeout_seconds=timeout,
            description=description
        )
        
        self.checks[component] = health_check
        self.check_history[component] = deque(maxlen=self.history_size)
        
        logger.info(f"Registered health check for component {component} "
                   f"with interval {interval}s, timeout {timeout}s")
    
    def start(self) -> None:
        """Start the health checking thread."""
        if self.running:
            logger.warning("HealthChecker is already running")
            return
        
        self.running = True
        self.check_thread = threading.Thread(target=self._check_loop, daemon=True)
        self.check_thread.start()
        
        logger.info("HealthChecker started")
    
    def stop(self) -> None:
        """Stop the health checking thread."""
        if not self.running:
            logger.warning("HealthChecker is not running")
            return
        
        self.running = False
        
        if self.check_thread:
            self.check_thread.join(timeout=5.0)
            if self.check_thread.is_alive():
                logger.warning("HealthChecker thread did not terminate gracefully")
        
        logger.info("HealthChecker stopped")
    
    def check_component(self, component: str) -> HealthCheckResult:
        """
        Run a health check for a specific component immediately.
        
        Args:
            component: Name of the component to check
            
        Returns:
            The result of the health check
            
        Raises:
            ValueError: If the component does not have a registered health check
        """
        if component not in self.checks:
            raise ValueError(f"No health check registered for component {component}")
        
        health_check = self.checks[component]
        result = health_check.run()
        
        # Add to history
        self.check_history[component].append(result)
        
        return result
    
    def check_all_components(self) -> Dict[str, HealthCheckResult]:
        """
        Run health checks for all registered components immediately.
        
        Returns:
            Dictionary mapping component names to health check results
        """
        results = {}
        
        for component, health_check in self.checks.items():
            result = health_check.run()
            results[component] = result
            
            # Add to history
            self.check_history[component].append(result)
        
        return results
    
    def get_component_status(self, component: str) -> Optional[HealthCheckResult]:
        """
        Get the latest health status for a specific component.
        
        Args:
            component: Name of the component
            
        Returns:
            The latest health check result for the component, or None if no checks have been run
        """
        if component not in self.checks:
            return None
        
        health_check = self.checks[component]
        return health_check.last_result
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get the overall health status of the system.
        
        Returns:
            Dictionary with system health information including overall status and component statuses
        """
        component_statuses = {}
        overall_status = HealthStatus.HEALTHY
        
        for component, health_check in self.checks.items():
            if health_check.last_result is None:
                component_statuses[component] = HealthStatus.UNKNOWN.value
                if overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.UNKNOWN
            else:
                component_status = health_check.last_result.status
                component_statuses[component] = component_status.value
                
                # Update overall status based on component status
                if component_status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif component_status == HealthStatus.DEGRADED and overall_status != HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.DEGRADED
        
        return {
            'overall_status': overall_status.value,
            'component_statuses': component_statuses,
            'timestamp': datetime.datetime.now().isoformat()
        }
    
    def get_component_history(self, component: str) -> List[Dict[str, Any]]:
        """
        Get the health check history for a specific component.
        
        Args:
            component: Name of the component
            
        Returns:
            List of health check results for the component, or empty list if no history exists
        """
        if component not in self.check_history:
            return []
        
        return [result.to_dict() for result in self.check_history[component]]
    
    def _check_loop(self) -> None:
        """Main health checking loop."""
        next_check_time = {}
        
        while self.running:
            current_time = time.time()
            
            for component, health_check in self.checks.items():
                # Initialize next check time if not set
                if component not in next_check_time:
                    next_check_time[component] = current_time
                
                # Check if it's time to run this check
                if current_time >= next_check_time[component]:
                    try:
                        result = health_check.run()
                        
                        # Add to history
                        self.check_history[component].append(result)
                        
                        # Schedule next check
                        next_check_time[component] = current_time + health_check.interval_seconds
                        
                        logger.debug(f"Health check for {component}: {result.status.value} - {result.message}")
                    except Exception as e:
                        logger.error(f"Error running health check for {component}: {str(e)}")
                        next_check_time[component] = current_time + health_check.interval_seconds
            
            # Sleep for a short time before checking again
            time.sleep(1.0) 