"""
Observability Module

This module provides observability capabilities for the Instinct AI trading platform,
including logging, metrics, and tracing.
"""

from .logging import get_logger, set_log_level, add_log_handler, remove_log_handler
from .metrics import get_metrics_client, counter, gauge, histogram, summary
from .tracing import get_tracer, start_span, end_span, add_event

__all__ = [
    # Logging
    'get_logger',
    'set_log_level',
    'add_log_handler',
    'remove_log_handler',
    
    # Metrics
    'get_metrics_client',
    'counter',
    'gauge',
    'histogram',
    'summary',
    
    # Tracing
    'get_tracer',
    'start_span',
    'end_span',
    'add_event'
] 