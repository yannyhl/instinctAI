"""
Observability Module

This module provides observability capabilities for the Instinct AI trading platform,
including logging, metrics, and tracing.
"""

# Import individual components
from .logging import LoggingManager
from .metrics import MetricsManager
from .tracing import TracingManager

# Import unified manager
from .observability_manager import (
    ObservabilityManager,
    observability_manager,
    get_logger,
    set_log_level,
    record_metric,
    increment_counter,
    start_span,
    start_trace
)

# Convenience functions from individual components
from .logging import add_log_handler, remove_log_handler
from .metrics import counter, gauge, histogram, summary

__all__ = [
    # Managers
    'ObservabilityManager',
    'LoggingManager',
    'MetricsManager',
    'TracingManager',
    'observability_manager',
    
    # Unified API
    'get_logger',
    'set_log_level',
    'record_metric',
    'increment_counter',
    'start_span',
    'start_trace',
    
    # Additional logging functions
    'add_log_handler',
    'remove_log_handler',
    
    # Additional metrics functions
    'counter',
    'gauge',
    'histogram',
    'summary'
] 