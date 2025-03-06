"""
Distributed Tracing Management

This module provides distributed tracing capabilities for the Instinct AI trading platform.
"""

import logging
import time
import uuid
import threading
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable, Tuple, Union
from contextlib import contextmanager

# Local imports
from ..config import config_manager

# Configure logging
logger = logging.getLogger(__name__)

# Try to import OpenTelemetry, but don't fail if not available
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.semconv.resource import ResourceAttributes
    
    # Try to import exporters
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        OTLP_AVAILABLE = True
    except ImportError:
        OTLP_AVAILABLE = False
        
    try:
        from opentelemetry.exporter.jaeger.thrift import JaegerExporter
        JAEGER_AVAILABLE = True
    except ImportError:
        JAEGER_AVAILABLE = False
    
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    logger.warning("OpenTelemetry not available, using internal tracing system only")


class Span:
    """
    Represents a single operation within a trace.
    """
    
    def __init__(self, name: str, trace_id: str, parent_id: Optional[str] = None, 
                otel_span: Optional[Any] = None):
        """
        Initialize a span.
        
        Args:
            name: Span name
            trace_id: Trace identifier
            parent_id: Optional parent span identifier
            otel_span: Optional OpenTelemetry span
        """
        self.name = name
        self.trace_id = trace_id
        self.parent_id = parent_id
        self.span_id = str(uuid.uuid4())
        self.start_time = time.time()
        self.end_time = None
        self.attributes = {}
        self.events = []
        self.otel_span = otel_span
    
    def set_attribute(self, key: str, value: Any):
        """
        Set a span attribute.
        
        Args:
            key: Attribute key
            value: Attribute value
        """
        self.attributes[key] = value
        
        # Also set attribute in OpenTelemetry span if available
        if self.otel_span:
            self.otel_span.set_attribute(key, value)
    
    def add_event(self, name: str, attributes: Dict[str, Any] = None):
        """
        Add an event to the span.
        
        Args:
            name: Event name
            attributes: Optional event attributes
        """
        event_time = time.time()
        
        self.events.append({
            'name': name,
            'timestamp': event_time,
            'attributes': attributes or {}
        })
        
        # Also add event to OpenTelemetry span if available
        if self.otel_span:
            self.otel_span.add_event(name, attributes or {})
    
    def end(self):
        """End the span"""
        self.end_time = time.time()
        
        # Also end the OpenTelemetry span if available
        if self.otel_span:
            self.otel_span.end()
    
    def duration_ms(self) -> float:
        """
        Get the span duration in milliseconds.
        
        Returns:
            Duration in milliseconds or None if span not ended
        """
        if self.end_time is None:
            return None
        
        return (self.end_time - self.start_time) * 1000.0
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert span to dictionary.
        
        Returns:
            Dictionary representation of span
        """
        result = {
            'name': self.name,
            'span_id': self.span_id,
            'trace_id': self.trace_id,
            'start_time': self.start_time,
            'attributes': self.attributes,
            'events': self.events
        }
        
        if self.parent_id:
            result['parent_id'] = self.parent_id
            
        if self.end_time:
            result['end_time'] = self.end_time
            result['duration_ms'] = self.duration_ms()
            
        return result


class TraceContext:
    """
    Context manager for span creation and management.
    """
    
    def __init__(self, span: Span, tracer):
        """
        Initialize trace context.
        
        Args:
            span: Active span
            tracer: Tracer instance
        """
        self.span = span
        self.tracer = tracer
    
    def __enter__(self):
        """Enter the trace context"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the trace context.
        
        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised
        """
        if exc_type:
            self.span.set_attribute('error', True)
            self.span.set_attribute('error.type', exc_type.__name__)
            self.span.set_attribute('error.message', str(exc_val))
        
        self.span.end()
        self.tracer._end_span(self.span)
        return False  # Don't suppress exceptions
    
    def set_attribute(self, key: str, value: Any):
        """
        Set span attribute.
        
        Args:
            key: Attribute key
            value: Attribute value
        """
        self.span.set_attribute(key, value)
    
    def add_event(self, name: str, attributes: Dict[str, Any] = None):
        """
        Add event to span.
        
        Args:
            name: Event name
            attributes: Optional event attributes
        """
        self.span.add_event(name, attributes)


class OpenTelemetryIntegration:
    """Integration with OpenTelemetry when available"""
    
    def __init__(self, service_name: str = "instinct_ai", enable_console: bool = False,
                enable_otlp: bool = False, otlp_endpoint: str = "localhost:4317",
                enable_jaeger: bool = False, jaeger_endpoint: str = "localhost:6831"):
        """
        Initialize OpenTelemetry integration.
        
        Args:
            service_name: Service name
            enable_console: Whether to enable console exporter
            enable_otlp: Whether to enable OTLP exporter
            otlp_endpoint: OTLP endpoint URL
            enable_jaeger: Whether to enable Jaeger exporter
            jaeger_endpoint: Jaeger endpoint URL
        """
        if not OPENTELEMETRY_AVAILABLE:
            self.tracer = None
            return
            
        # Create a resource with service metadata
        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: service_name,
            ResourceAttributes.SERVICE_VERSION: config_manager.get("system.version", "1.0.0"),
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: config_manager.get("system.environment", "development")
        })
        
        # Create a tracer provider with the resource
        provider = TracerProvider(resource=resource)
        
        # Add console exporter if enabled
        if enable_console:
            console_exporter = ConsoleSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(console_exporter))
            logger.info("OpenTelemetry console exporter enabled")
        
        # Add OTLP exporter if enabled and available
        if enable_otlp and OTLP_AVAILABLE:
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"OpenTelemetry OTLP exporter enabled with endpoint {otlp_endpoint}")
        
        # Add Jaeger exporter if enabled and available
        if enable_jaeger and JAEGER_AVAILABLE:
            jaeger_exporter = JaegerExporter(
                agent_host_name=jaeger_endpoint.split(':')[0],
                agent_port=int(jaeger_endpoint.split(':')[1])
            )
            provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
            logger.info(f"OpenTelemetry Jaeger exporter enabled with endpoint {jaeger_endpoint}")
        
        # Set the tracer provider
        trace.set_tracer_provider(provider)
        
        # Create a tracer
        self.tracer = trace.get_tracer(service_name)
        logger.info("OpenTelemetry integration initialized")


class TracingManager:
    """
    Centralized tracing management for the Instinct AI platform.
    
    Provides:
    - Distributed trace creation and management
    - Span management and correlation
    - Integration with OpenTelemetry
    """
    
    def __init__(self):
        """Initialize the tracing manager"""
        self.active_spans = {}
        self.completed_spans = []
        self.listeners = []
        self._context = threading.local()
        
        # Configuration from config manager
        tracing_config = {
            'enabled': config_manager.get("observability.tracing.enabled", True),
            'sampling_rate': config_manager.get("observability.tracing.sampling_rate", 0.1),
            'max_traces': config_manager.get("observability.tracing.max_traces", 1000),
            'service_name': config_manager.get("system.name", "instinct_ai"),
            'enable_console': config_manager.get("observability.tracing.console", False),
            'enable_otlp': config_manager.get("observability.tracing.otlp.enabled", False),
            'otlp_endpoint': config_manager.get("observability.tracing.otlp.endpoint", "localhost:4317"),
            'enable_jaeger': config_manager.get("observability.tracing.jaeger.enabled", False),
            'jaeger_endpoint': config_manager.get("observability.tracing.jaeger.endpoint", "localhost:6831")
        }
        
        # Initialize OpenTelemetry if enabled
        if tracing_config['enabled']:
            self.otel = OpenTelemetryIntegration(
                service_name=tracing_config['service_name'],
                enable_console=tracing_config['enable_console'],
                enable_otlp=tracing_config['enable_otlp'],
                otlp_endpoint=tracing_config['otlp_endpoint'],
                enable_jaeger=tracing_config['enable_jaeger'],
                jaeger_endpoint=tracing_config['jaeger_endpoint']
            )
        else:
            self.otel = None
        
        # Apply trace storage limit
        self.max_traces = tracing_config['max_traces']
        
        # Apply sampling rate
        self.sampling_rate = tracing_config['sampling_rate']
        
        logger.info("Tracing Manager initialized")
    
    def start_trace(self, name: str) -> TraceContext:
        """
        Start a new trace.
        
        Args:
            name: Trace name
            
        Returns:
            Trace context
        """
        trace_id = str(uuid.uuid4())
        return self.start_span(name, trace_id=trace_id)
    
    def start_span(self, name: str, trace_id: Optional[str] = None, 
                 parent_id: Optional[str] = None) -> TraceContext:
        """
        Start a new span.
        
        Args:
            name: Span name
            trace_id: Optional trace identifier (will use current trace if available)
            parent_id: Optional parent span identifier
            
        Returns:
            Trace context
        """
        # Apply sampling
        if self.sampling_rate < 1.0 and self.sampling_rate > 0:
            import random
            if random.random() > self.sampling_rate:
                # Return a dummy span that does nothing
                dummy_span = Span("sampled_out", "sampled_out")
                return TraceContext(dummy_span, self)
        
        # Get active trace_id and parent_id if not provided
        if not trace_id:
            current_span = self.get_current_span()
            if current_span:
                trace_id = current_span.trace_id
                parent_id = current_span.span_id
            else:
                # No active trace, create new
                trace_id = str(uuid.uuid4())
        
        # Create OpenTelemetry span if available
        otel_span = None
        
        if self.otel and hasattr(self.otel, 'tracer') and self.otel.tracer:
            # Convert parent context if needed
            parent_context = None
            
            try:
                # Start span with OpenTelemetry
                otel_span = self.otel.tracer.start_span(name)
                
                # Add basic attributes
                otel_span.set_attribute('trace_id', trace_id)
                if parent_id:
                    otel_span.set_attribute('parent_id', parent_id)
            except Exception as e:
                logger.warning(f"Failed to create OpenTelemetry span: {str(e)}")
                otel_span = None
        
        # Create local span
        span = Span(name, trace_id, parent_id, otel_span)
        
        # Store in active spans
        self.active_spans[span.span_id] = span
        
        # Set as current span for this thread
        self._context.current_span_id = span.span_id
        
        return TraceContext(span, self)
    
    def get_current_span(self) -> Optional[Span]:
        """
        Get the current active span for this thread.
        
        Returns:
            Current span or None if not in a trace
        """
        current_span_id = getattr(self._context, 'current_span_id', None)
        if current_span_id:
            return self.active_spans.get(current_span_id)
        return None
    
    def add_span_listener(self, listener: Callable[[Span], None]):
        """
        Add a listener for completed spans.
        
        Args:
            listener: Callback function that takes a span
        """
        self.listeners.append(listener)
    
    def _end_span(self, span: Span):
        """
        End a span and process it.
        
        Args:
            span: Span to end
        """
        # Skip processing for sampled-out spans
        if span.trace_id == "sampled_out":
            return
            
        # Remove from active spans
        if span.span_id in self.active_spans:
            del self.active_spans[span.span_id]
        
        # Reset current span for this thread if it was current
        current_span_id = getattr(self._context, 'current_span_id', None)
        if current_span_id == span.span_id:
            delattr(self._context, 'current_span_id')
        
        # Add to completed spans
        self.completed_spans.append(span)
        
        # Limit stored spans
        if len(self.completed_spans) > self.max_traces:
            self.completed_spans = self.completed_spans[-self.max_traces:]
        
        # Notify listeners
        for listener in self.listeners:
            try:
                listener(span)
            except Exception as e:
                logger.error(f"Error in span listener: {str(e)}")
    
    def get_trace(self, trace_id: str) -> List[Span]:
        """
        Get all spans for a trace.
        
        Args:
            trace_id: Trace identifier
            
        Returns:
            List of spans in the trace
        """
        # Get active and completed spans for the trace
        spans = []
        
        for span in self.active_spans.values():
            if span.trace_id == trace_id:
                spans.append(span)
                
        for span in self.completed_spans:
            if span.trace_id == trace_id:
                spans.append(span)
                
        return spans
    
    def clear_completed_spans(self):
        """Clear all completed spans"""
        self.completed_spans = []
    
    @contextmanager
    def span(self, name: str):
        """
        Context manager for creating a span.
        
        Args:
            name: Span name
            
        Yields:
            Trace context
        """
        ctx = self.start_span(name)
        try:
            yield ctx
        finally:
            ctx.span.end()
            self._end_span(ctx.span)
            
    def shutdown(self):
        """Shut down the tracing manager"""
        # Any cleanup needed
        logger.info("Tracing Manager shutting down")


# Create singleton instance
tracing_manager = TracingManager() 