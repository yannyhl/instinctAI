"""
Observability Manager

This module provides a unified interface for observability in the Instinct AI trading platform,
integrating logging, metrics, and tracing into a cohesive system.
"""

import logging
import os
import threading
from typing import Dict, Any, Optional, List, Callable, Union, Tuple

# Local imports
from ..config import config_manager, get_config
from .logging import LoggingManager
from .metrics import MetricsManager
from .tracing import TracingManager

logger = logging.getLogger(__name__)

class ObservabilityManager:
    """
    Unified manager for observability concerns including logging, metrics, and tracing.
    
    This class provides a centralized interface for all observability functions,
    ensuring consistent configuration and integration between different observability systems.
    
    Example:
        obs_manager = ObservabilityManager()
        logger = obs_manager.get_logger("my_component")
        
        with obs_manager.start_span("operation"):
            # Do something
            obs_manager.record_metric("operation_count", 1)
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls, *args, **kwargs):
        """Implement singleton pattern."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ObservabilityManager, cls).__new__(cls)
            return cls._instance
    
    def __init__(self, 
                 log_dir: Optional[str] = None, 
                 log_level: Optional[str] = None,
                 enable_prometheus: bool = True,
                 enable_tracing: bool = True):
        """
        Initialize the observability manager.
        
        Args:
            log_dir: Directory for log files
            log_level: Default log level
            enable_prometheus: Whether to enable Prometheus metrics
            enable_tracing: Whether to enable distributed tracing
        """
        with self._lock:
            # Only initialize once
            if hasattr(self, '_initialized') and self._initialized:
                return
                
            # Get configuration
            if log_dir is None:
                log_dir = get_config('observability.log_dir', 'logs')
            
            if log_level is None:
                log_level = get_config('observability.log_level', 'INFO')
                
            if enable_prometheus is None:
                enable_prometheus = get_config('observability.enable_prometheus', True)
                
            if enable_tracing is None:
                enable_tracing = get_config('observability.enable_tracing', True)
            
            # Initialize managers
            self._logging_manager = LoggingManager(log_dir=log_dir, log_level=log_level)
            self._metrics_manager = MetricsManager()
            self._tracing_manager = TracingManager()
            
            # Configure from settings
            self._configure_from_settings()
            
            self._initialized = True
            logger.info("ObservabilityManager initialized")
    
    def _configure_from_settings(self):
        """Configure observability components from settings."""
        # Configure Prometheus if enabled
        prometheus_port = get_config('observability.prometheus_port', 8000)
        if get_config('observability.enable_prometheus', True):
            try:
                self._metrics_manager.start_prometheus_server(prometheus_port)
                logger.info(f"Started Prometheus server on port {prometheus_port}")
            except Exception as e:
                logger.error(f"Failed to start Prometheus server: {e}")
        
        # Configure OpenTelemetry if enabled
        if get_config('observability.enable_opentelemetry', False):
            service_name = get_config('system.service_name', 'instinct_ai')
            otlp_endpoint = get_config('observability.otlp_endpoint', 'localhost:4317')
            jaeger_endpoint = get_config('observability.jaeger_endpoint', 'localhost:6831')
            
            enable_otlp = get_config('observability.enable_otlp', False)
            enable_jaeger = get_config('observability.enable_jaeger', False)
            
            try:
                self._tracing_manager.configure_opentelemetry(
                    service_name=service_name,
                    enable_otlp=enable_otlp,
                    otlp_endpoint=otlp_endpoint,
                    enable_jaeger=enable_jaeger,
                    jaeger_endpoint=jaeger_endpoint
                )
                logger.info("Configured OpenTelemetry tracing")
            except Exception as e:
                logger.error(f"Failed to configure OpenTelemetry: {e}")
        
        # Configure Sentry if enabled
        if get_config('observability.enable_sentry', False):
            sentry_dsn = get_config('observability.sentry_dsn', '')
            environment = get_config('system.environment', 'development')
            
            if sentry_dsn:
                try:
                    self._logging_manager.configure_sentry(sentry_dsn, environment)
                    logger.info("Configured Sentry integration")
                except Exception as e:
                    logger.error(f"Failed to configure Sentry: {e}")
    
    def get_logger(self, name: str, context: Dict[str, Any] = None) -> logging.Logger:
        """
        Get a logger with the given name and context.
        
        Args:
            name: Logger name
            context: Additional context to include in log records
            
        Returns:
            A configured logger
        """
        return self._logging_manager.get_logger(name, context)
    
    def set_log_level(self, level: str, logger_name: Optional[str] = None) -> None:
        """
        Set the log level for a logger or the root logger.
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            logger_name: Logger name, or None for the root logger
        """
        self._logging_manager.update_log_level(level, logger_name)
    
    def add_global_log_context(self, **context) -> None:
        """
        Add context to all log records.
        
        Args:
            **context: Key-value pairs to add to log context
        """
        self._logging_manager.set_global_context(**context)
    
    def record_metric(self, name: str, value: Union[int, float], labels: Dict[str, Any] = None) -> None:
        """
        Record a metric value.
        
        Args:
            name: Metric name
            value: Metric value
            labels: Additional labels for the metric
        """
        self._metrics_manager.record_metric(name, value, labels)
    
    def increment_counter(self, name: str, amount: float = 1, labels: Dict[str, Any] = None) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Counter name
            amount: Amount to increment by
            labels: Additional labels for the metric
        """
        self._metrics_manager.increment_counter(name, amount, labels)
    
    def start_span(self, name: str, attributes: Dict[str, Any] = None) -> Any:
        """
        Start a new span for tracing.
        
        Args:
            name: Span name
            attributes: Initial span attributes
            
        Returns:
            A trace context manager
        """
        span = self._tracing_manager.start_span(name)
        
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
                
        return span
    
    def start_trace(self, name: str, attributes: Dict[str, Any] = None) -> Any:
        """
        Start a new trace.
        
        Args:
            name: Trace name
            attributes: Initial span attributes
            
        Returns:
            A trace context manager
        """
        trace = self._tracing_manager.start_trace(name)
        
        if attributes:
            for key, value in attributes.items():
                trace.set_attribute(key, value)
                
        return trace
    
    def get_metrics_manager(self) -> MetricsManager:
        """
        Get the metrics manager.
        
        Returns:
            The metrics manager instance
        """
        return self._metrics_manager
    
    def get_logging_manager(self) -> LoggingManager:
        """
        Get the logging manager.
        
        Returns:
            The logging manager instance
        """
        return self._logging_manager
    
    def get_tracing_manager(self) -> TracingManager:
        """
        Get the tracing manager.
        
        Returns:
            The tracing manager instance
        """
        return self._tracing_manager
    
    def shutdown(self) -> None:
        """Shutdown all observability components."""
        try:
            self._metrics_manager.shutdown()
            logger.info("Metrics manager shutdown complete")
        except Exception as e:
            logger.error(f"Error shutting down metrics manager: {e}")
            
        try:
            self._tracing_manager.shutdown()
            logger.info("Tracing manager shutdown complete")
        except Exception as e:
            logger.error(f"Error shutting down tracing manager: {e}")
            
        try:
            self._logging_manager.shutdown()
            logger.info("Logging manager shutdown complete")
        except Exception as e:
            logger.error(f"Error shutting down logging manager: {e}")


# Create a singleton instance
observability_manager = ObservabilityManager()

def get_logger(name: str, context: Dict[str, Any] = None) -> logging.Logger:
    """
    Get a logger with the given name and context.
    
    This is a convenience function that uses the singleton ObservabilityManager instance.
    
    Args:
        name: Logger name
        context: Additional context to include in log records
        
    Returns:
        A configured logger
    """
    return observability_manager.get_logger(name, context)

def set_log_level(level: str, logger_name: Optional[str] = None) -> None:
    """
    Set the log level for a logger or the root logger.
    
    This is a convenience function that uses the singleton ObservabilityManager instance.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        logger_name: Logger name, or None for the root logger
    """
    observability_manager.set_log_level(level, logger_name)

def record_metric(name: str, value: Union[int, float], labels: Dict[str, Any] = None) -> None:
    """
    Record a metric value.
    
    This is a convenience function that uses the singleton ObservabilityManager instance.
    
    Args:
        name: Metric name
        value: Metric value
        labels: Additional labels for the metric
    """
    observability_manager.record_metric(name, value, labels)

def increment_counter(name: str, amount: float = 1, labels: Dict[str, Any] = None) -> None:
    """
    Increment a counter metric.
    
    This is a convenience function that uses the singleton ObservabilityManager instance.
    
    Args:
        name: Counter name
        amount: Amount to increment by
        labels: Additional labels for the metric
    """
    observability_manager.increment_counter(name, amount, labels)

def start_span(name: str, attributes: Dict[str, Any] = None) -> Any:
    """
    Start a new span for tracing.
    
    This is a convenience function that uses the singleton ObservabilityManager instance.
    
    Args:
        name: Span name
        attributes: Initial span attributes
        
    Returns:
        A trace context manager
    """
    return observability_manager.start_span(name, attributes)

def start_trace(name: str, attributes: Dict[str, Any] = None) -> Any:
    """
    Start a new trace.
    
    This is a convenience function that uses the singleton ObservabilityManager instance.
    
    Args:
        name: Trace name
        attributes: Initial span attributes
        
    Returns:
        A trace context manager
    """
    return observability_manager.start_trace(name, attributes) 