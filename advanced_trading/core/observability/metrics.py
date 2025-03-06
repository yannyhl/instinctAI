"""
Metrics Management

This module provides metrics collection, storage, and reporting for the Instinct AI trading platform.
"""

import time
import logging
import threading
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Set, Callable, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque

# Local imports
from ..config import config_manager

# Configure logging
logger = logging.getLogger(__name__)

# Try to import prometheus_client, but don't fail if not available
try:
    import prometheus_client
    from prometheus_client import Counter, Gauge, Histogram, Summary
    from prometheus_client.core import REGISTRY
    PROMETHEUS_AVAILABLE = True
except ImportError:
    logger.warning("prometheus_client not available, Prometheus integration disabled")
    PROMETHEUS_AVAILABLE = False
    # Create placeholder classes for type checking
    class Counter:
        def inc(self, amount=1): pass
        def labels(self, **kwargs): return self
    class Gauge:
        def set(self, value): pass
        def inc(self, amount=1): pass
        def dec(self, amount=1): pass
        def labels(self, **kwargs): return self
    class Histogram:
        def observe(self, value): pass
        def labels(self, **kwargs): return self
    class Summary:
        def observe(self, value): pass
        def labels(self, **kwargs): return self


@dataclass
class MetricDefinition:
    """Definition of a metric to be tracked"""
    name: str
    description: str
    unit: str = ""
    metric_type: str = "gauge"  # gauge, counter, histogram, summary
    labels: List[str] = field(default_factory=list)
    buckets: List[float] = field(default_factory=list)  # For histograms


class PrometheusMetricRegistry:
    """Registry for Prometheus metrics"""
    
    def __init__(self, enable_prometheus: bool = True, prefix: str = "instinct_"):
        """
        Initialize the Prometheus metric registry.
        
        Args:
            enable_prometheus: Whether to enable Prometheus integration
            prefix: Prefix for all metric names
        """
        self.metrics: Dict[str, Any] = {}
        self.enable_prometheus = enable_prometheus and PROMETHEUS_AVAILABLE
        self.prefix = prefix
        
        if self.enable_prometheus:
            logger.info("Prometheus integration enabled")
        else:
            logger.info("Prometheus integration disabled")
    
    def register_metric(self, metric_def: MetricDefinition) -> Any:
        """
        Register a metric with Prometheus.
        
        Args:
            metric_def: Metric definition
            
        Returns:
            Prometheus metric object
        """
        if not self.enable_prometheus:
            return None
            
        name = f"{self.prefix}{metric_def.name}"
        
        # Check if metric already exists
        if name in self.metrics:
            logger.warning(f"Metric {name} already registered, returning existing instance")
            return self.metrics[name]
        
        # Create appropriate metric type
        if metric_def.metric_type == "counter":
            metric = Counter(name, metric_def.description, metric_def.labels)
        elif metric_def.metric_type == "gauge":
            metric = Gauge(name, metric_def.description, metric_def.labels)
        elif metric_def.metric_type == "histogram":
            buckets = metric_def.buckets if metric_def.buckets else prometheus_client.Histogram.DEFAULT_BUCKETS
            metric = Histogram(name, metric_def.description, metric_def.labels, buckets=buckets)
        elif metric_def.metric_type == "summary":
            metric = Summary(name, metric_def.description, metric_def.labels)
        else:
            logger.error(f"Unknown metric type: {metric_def.metric_type}")
            return None
        
        self.metrics[name] = metric
        return metric
    
    def get_metric(self, name: str) -> Optional[Any]:
        """
        Get a registered metric.
        
        Args:
            name: Metric name
            
        Returns:
            Prometheus metric or None if not found
        """
        if not self.enable_prometheus:
            return None
            
        name = f"{self.prefix}{name}"
        return self.metrics.get(name)
    
    def record_counter(self, name: str, amount: float = 1, labels: Dict[str, str] = None) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            amount: Amount to increment by
            labels: Optional dimensional labels
        """
        if not self.enable_prometheus:
            return
            
        metric = self.get_metric(name)
        if metric is None:
            logger.warning(f"Metric {name} not registered")
            return
        
        if labels:
            metric.labels(**labels).inc(amount)
        else:
            metric.inc(amount)
    
    def record_gauge(self, name: str, value: float, labels: Dict[str, str] = None) -> None:
        """
        Set a gauge metric value.
        
        Args:
            name: Metric name
            value: Value to set
            labels: Optional dimensional labels
        """
        if not self.enable_prometheus:
            return
            
        metric = self.get_metric(name)
        if metric is None:
            logger.warning(f"Metric {name} not registered")
            return
        
        if labels:
            metric.labels(**labels).set(value)
        else:
            metric.set(value)
    
    def record_histogram(self, name: str, value: float, labels: Dict[str, str] = None) -> None:
        """
        Record a histogram observation.
        
        Args:
            name: Metric name
            value: Value to observe
            labels: Optional dimensional labels
        """
        if not self.enable_prometheus:
            return
            
        metric = self.get_metric(name)
        if metric is None:
            logger.warning(f"Metric {name} not registered")
            return
        
        if labels:
            metric.labels(**labels).observe(value)
        else:
            metric.observe(value)
    
    def record_summary(self, name: str, value: float, labels: Dict[str, str] = None) -> None:
        """
        Record a summary observation.
        
        Args:
            name: Metric name
            value: Value to observe
            labels: Optional dimensional labels
        """
        if not self.enable_prometheus:
            return
            
        metric = self.get_metric(name)
        if metric is None:
            logger.warning(f"Metric {name} not registered")
            return
        
        if labels:
            metric.labels(**labels).observe(value)
        else:
            metric.observe(value)
    
    def start_http_server(self, port: int = 8000) -> None:
        """
        Start the Prometheus HTTP server.
        
        Args:
            port: HTTP port to listen on
        """
        if not self.enable_prometheus:
            logger.warning("Prometheus integration not enabled, cannot start HTTP server")
            return
            
        try:
            prometheus_client.start_http_server(port)
            logger.info(f"Prometheus metrics server started on port {port}")
        except Exception as e:
            logger.error(f"Failed to start Prometheus metrics server: {str(e)}")


class MetricsManager:
    """
    Centralized metrics management for the Instinct AI platform.
    
    Provides:
    - Metric registration and definition
    - Metric recording with dimensional labels
    - Integration with monitoring systems
    - Aggregation and statistical operations
    """
    
    def __init__(self):
        """Initialize the metrics manager"""
        self.metrics = {}
        self.metric_definitions = {}
        
        # Time series storage
        self.time_series = {}
        
        # Circular buffer for each metric to limit memory usage
        self.metric_buffers = defaultdict(lambda: defaultdict(lambda: deque(maxlen=10000)))
        
        # Configuration
        self.max_buffer_size = config_manager.get("observability.metrics.storage_duration_days", 7) * 24 * 60 * 6  # 10-second intervals for N days
        
        # Prometheus integration
        self.enable_prometheus = config_manager.get("observability.metrics.prometheus", False)
        self.prometheus = PrometheusMetricRegistry(enable_prometheus=self.enable_prometheus)
        
        # Metrics flush thread
        self.flush_interval = 60  # seconds
        self.flush_thread = None
        self.stopping = False
        
        # Start metrics flush thread
        self._start_flush_thread()
        
        logger.info("Metrics Manager initialized")
    
    def _start_flush_thread(self):
        """Start the metrics flush thread"""
        if self.flush_thread is not None:
            return
            
        self.stopping = False
        self.flush_thread = threading.Thread(target=self._flush_thread_func, daemon=True)
        self.flush_thread.start()
    
    def _flush_thread_func(self):
        """Metrics flush thread function"""
        while not self.stopping:
            try:
                self._flush_metrics()
            except Exception as e:
                logger.error(f"Error flushing metrics: {str(e)}")
            
            # Sleep for flush interval
            time.sleep(self.flush_interval)
    
    def _flush_metrics(self):
        """Flush metrics to storage"""
        # TODO: Implement long-term metrics storage
        pass
    
    def register_metric(self, metric_def: MetricDefinition) -> None:
        """
        Register a new metric for tracking.
        
        Args:
            metric_def: Metric definition
        """
        self.metric_definitions[metric_def.name] = metric_def
        self.metrics[metric_def.name] = {}
        
        # Register with Prometheus if enabled
        self.prometheus.register_metric(metric_def)
        
        logger.debug(f"Registered metric: {metric_def.name}")
    
    def record_metric(self, name: str, value: Union[int, float], labels: Dict[str, str] = None) -> None:
        """
        Record a metric value.
        
        Args:
            name: Metric name
            value: Metric value
            labels: Optional dimensional labels
        """
        if name not in self.metric_definitions:
            logger.warning(f"Recording undefined metric: {name}")
            
        labels_str = str(labels or {})
        if name not in self.metrics:
            self.metrics[name] = {}
        
        if labels_str not in self.metrics[name]:
            self.metrics[name][labels_str] = []
        
        timestamp = time.time()
        
        # Store in buffer
        self.metric_buffers[name][labels_str].append((timestamp, value))
        
        # Update Prometheus if enabled
        if name in self.metric_definitions:
            metric_def = self.metric_definitions[name]
            
            if metric_def.metric_type == "counter":
                self.prometheus.record_counter(name, value, labels)
            elif metric_def.metric_type == "gauge":
                self.prometheus.record_gauge(name, value, labels)
            elif metric_def.metric_type == "histogram":
                self.prometheus.record_histogram(name, value, labels)
            elif metric_def.metric_type == "summary":
                self.prometheus.record_summary(name, value, labels)
        
        logger.debug(f"Recorded metric {name}: {value} {labels}")
    
    def increment_counter(self, name: str, amount: float = 1, labels: Dict[str, str] = None) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            amount: Amount to increment by
            labels: Optional dimensional labels
        """
        labels_str = str(labels or {})
        
        # Get current value
        current = 0
        if name in self.metrics and labels_str in self.metrics[name] and self.metrics[name][labels_str]:
            current = self.metrics[name][labels_str][-1][1]
        
        # Record new value
        self.record_metric(name, current + amount, labels)
    
    def record_timing(self, name: str, labels: Dict[str, str] = None):
        """
        Create a timing context manager for measuring durations.
        
        Args:
            name: Metric name
            labels: Optional dimensional labels
            
        Returns:
            Context manager for timing
        """
        start_time = time.time()
        
        def end_timing():
            duration = (time.time() - start_time) * 1000  # Convert to ms
            self.record_metric(name, duration, labels)
            return duration
        
        return TimingContext(end_timing)
    
    def get_metric(self, name: str, labels: Dict[str, str] = None, 
                  aggregation: str = "last", lookback: int = None) -> Optional[float]:
        """
        Get the current value of a metric.
        
        Args:
            name: Metric name
            labels: Optional dimensional labels
            aggregation: Aggregation method (last, mean, min, max, sum)
            lookback: Number of most recent samples to consider
            
        Returns:
            Metric value or None if not available
        """
        if name not in self.metrics:
            return None
            
        labels_str = str(labels or {})
        if labels_str not in self.metrics[name]:
            return None
            
        values = self.metric_buffers[name][labels_str]
        if not values:
            return None
            
        if lookback:
            values = list(values)[-lookback:]
            
        # Extract just the values (without timestamps)
        just_values = [v[1] for v in values]
            
        if aggregation == "last":
            return just_values[-1]
        elif aggregation == "mean":
            return sum(just_values) / len(just_values)
        elif aggregation == "min":
            return min(just_values)
        elif aggregation == "max":
            return max(just_values)
        elif aggregation == "sum":
            return sum(just_values)
        else:
            return just_values[-1]  # Default to last
    
    def get_time_series(self, name: str, labels: Dict[str, str] = None, 
                      start_time: Optional[float] = None, end_time: Optional[float] = None) -> List[Tuple[float, float]]:
        """
        Get a time series of metric values.
        
        Args:
            name: Metric name
            labels: Optional dimensional labels
            start_time: Optional start time (timestamp)
            end_time: Optional end time (timestamp)
            
        Returns:
            List of (timestamp, value) tuples
        """
        if name not in self.metrics:
            return []
            
        labels_str = str(labels or {})
        if labels_str not in self.metrics[name]:
            return []
            
        values = list(self.metric_buffers[name][labels_str])
        
        # Filter by time range if specified
        if start_time is not None:
            values = [v for v in values if v[0] >= start_time]
        
        if end_time is not None:
            values = [v for v in values if v[0] <= end_time]
            
        return values
    
    def get_metric_definitions(self) -> Dict[str, MetricDefinition]:
        """
        Get all metric definitions.
        
        Returns:
            Dictionary of metric name to definition
        """
        return self.metric_definitions.copy()
    
    def start_prometheus_server(self, port: Optional[int] = None) -> None:
        """
        Start the Prometheus metrics server.
        
        Args:
            port: Optional port number (default: use configuration)
        """
        if not self.enable_prometheus:
            logger.info("Prometheus integration not enabled, not starting server")
            return
            
        if port is None:
            port = config_manager.get("observability.metrics.port", 8000)
            
        self.prometheus.start_http_server(port)
    
    def shutdown(self) -> None:
        """Shut down the metrics manager"""
        logger.info("Shutting down Metrics Manager")
        self.stopping = True
        
        if self.flush_thread:
            self.flush_thread.join(timeout=2.0)


class TimingContext:
    """Context manager for timing operations"""
    
    def __init__(self, end_func):
        """
        Initialize the timing context.
        
        Args:
            end_func: Function to call at context exit
        """
        self.end_func = end_func
        
    def __enter__(self):
        """Enter the context"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the context and record timing.
        
        Returns:
            False to propagate exceptions
        """
        self.duration = self.end_func()
        return False

# Create singleton instance
metrics_manager = MetricsManager() 