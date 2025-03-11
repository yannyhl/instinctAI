"""
Logging Management

This module provides structured logging capabilities for the Instinct AI trading platform.
"""

import os
import logging
import json
import sys
import time
import traceback
import socket
import threading
from typing import Dict, Any, Optional, List, Union, Callable
from datetime import datetime
from logging.handlers import RotatingFileHandler, QueueHandler, QueueListener
from queue import Queue

# Local imports
from ..config import config_manager

# Try to import third-party logging libraries
try:
    import pythonjsonlogger
    from pythonjsonlogger import jsonlogger
    JSON_LOGGER_AVAILABLE = True
except ImportError:
    JSON_LOGGER_AVAILABLE = False

try:
    import structlog
    STRUCTLOG_AVAILABLE = True
except ImportError:
    STRUCTLOG_AVAILABLE = False

try:
    import sentry_sdk
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False


class StructuredFormatter(logging.Formatter):
    """
    Formatter for structured JSON logging.
    """
    
    def format(self, record):
        """
        Format log record as JSON.
        
        Args:
            record: Log record
            
        Returns:
            Formatted JSON string
        """
        log_data = {
            'timestamp': datetime.utcfromtimestamp(record.created).isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'line': record.lineno,
            'process': record.process,
            'thread': record.thread,
            'host': socket.gethostname()
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key.startswith('ctx_') and key != 'ctx_info':
                log_data[key[4:]] = value
        
        # Add context info if present
        if hasattr(record, 'ctx_info') and record.ctx_info:
            for key, value in record.ctx_info.items():
                # Don't overwrite existing keys
                if key not in log_data:
                    log_data[key] = value
        
        # Add thread name if present
        if hasattr(threading, 'current_thread'):
            log_data['thread_name'] = threading.current_thread().name
            
        return json.dumps(log_data)


class ContextAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds context to log records.
    """
    
    def process(self, msg, kwargs):
        """
        Process the log record by adding context.
        
        Args:
            msg: Log message
            kwargs: Logging keyword arguments
            
        Returns:
            Processed message and kwargs
        """
        # Add context info to the extra dict
        kwargs.setdefault('extra', {}).update({'ctx_info': self.extra})
        return msg, kwargs


class JsonLoggerFactory:
    """Factory for creating JSON loggers when python-json-logger is available"""
    
    @staticmethod
    def create_formatter():
        """Create a JSON formatter"""
        if not JSON_LOGGER_AVAILABLE:
            return StructuredFormatter()
            
        # Use python-json-logger when available
        return jsonlogger.JsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            rename_fields={
                'levelname': 'level',
                'asctime': 'timestamp'
            },
            timestamp=True
        )


class StructlogIntegration:
    """Integration with structlog when available"""
    
    @staticmethod
    def configure():
        """Configure structlog integration"""
        if not STRUCTLOG_AVAILABLE:
            return None
            
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        return structlog


class SentryIntegration:
    """Integration with Sentry for error reporting"""
    
    @staticmethod
    def configure(dsn: str, environment: str = "development"):
        """
        Configure Sentry integration.
        
        Args:
            dsn: Sentry DSN
            environment: Environment name
        """
        if not SENTRY_AVAILABLE or not dsn:
            return
            
        # Initialize Sentry SDK
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=0.1
        )


class AsyncLogDispatcher:
    """
    Asynchronous log dispatcher for non-blocking logging.
    """
    
    def __init__(self):
        """Initialize the dispatcher"""
        self.log_queue = Queue()
        self.listeners = []
    
    def create_handler(self, handler):
        """
        Create a QueueHandler for a handler.
        
        Args:
            handler: The handler to wrap
            
        Returns:
            QueueHandler instance
        """
        queue_handler = QueueHandler(self.log_queue)
        self.listeners.append(handler)
        return queue_handler
    
    def start(self):
        """Start the queue listener"""
        self.listener = QueueListener(self.log_queue, *self.listeners, respect_handler_level=True)
        self.listener.start()
        
    def stop(self):
        """Stop the queue listener"""
        if hasattr(self, 'listener'):
            self.listener.stop()


class LoggingManager:
    """
    Centralized logging management for the Instinct AI platform.
    
    Provides:
    - Structured JSON logging
    - Context-aware logging
    - Configurable output destinations
    - Integration with observability systems
    """
    
    def __init__(self, log_dir: str = None, log_level: str = None):
        """
        Initialize the logging manager.
        
        Args:
            log_dir: Directory for log files (default: advanced_trading/logs)
            log_level: Default log level (default: from config)
        """
        # Load configuration
        self.log_dir = log_dir or config_manager.get(
            "system.directories.logs", 
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs')
        )
        
        # Ensure log directory exists
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Set log level
        if log_level is None:
            log_level = config_manager.get("system.log_level", "INFO")
        
        # Configure logging settings from config
        self.console_logging = config_manager.get("observability.logging.console", True)
        self.file_logging = config_manager.get("observability.logging.file", True)
        self.structured_logging = config_manager.get("observability.logging.structured", True)
        self.async_logging = config_manager.get("observability.logging.async", True)
        self.max_file_size_mb = config_manager.get("observability.logging.max_file_size_mb", 10)
        self.max_files = config_manager.get("observability.logging.max_files", 5)
        
        # Initialize async dispatcher if needed
        self.dispatcher = AsyncLogDispatcher() if self.async_logging else None
        
        # Configure root logger
        self.configure_root_logger(log_level)
        
        # Context for all loggers
        self.global_context = {}
        
        # Track all created loggers
        self.loggers = {}
        
        # Initialize structlog if available
        self.structlog = StructlogIntegration.configure()
        
        # Initialize Sentry if configured
        sentry_dsn = config_manager.get("observability.logging.sentry_dsn", None)
        if sentry_dsn:
            SentryIntegration.configure(
                dsn=sentry_dsn,
                environment=config_manager.get("system.environment", "development")
            )
        
        # Initialize logger for this component
        self.logger = logging.getLogger(__name__)
        self.logger.info("Logging Manager initialized")
        
        # Start async dispatcher if enabled
        if self.dispatcher:
            self.dispatcher.start()
    
    def configure_root_logger(self, log_level: str):
        """
        Configure the root logger.
        
        Args:
            log_level: Default log level
        """
        # Convert string level to numeric
        numeric_level = getattr(logging, log_level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f"Invalid log level: {log_level}")
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(numeric_level)
        
        # Remove any existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Create formatters
        if self.structured_logging:
            formatter = JsonLoggerFactory.create_formatter()
        else:
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        
        # Create console handler
        if self.console_logging:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            
            if self.dispatcher:
                root_logger.addHandler(self.dispatcher.create_handler(console_handler))
            else:
                root_logger.addHandler(console_handler)
        
        # Create file handler
        if self.file_logging:
            log_file = os.path.join(self.log_dir, 'instinct_ai.log')
            file_handler = RotatingFileHandler(
                log_file, 
                maxBytes=self.max_file_size_mb * 1024 * 1024, 
                backupCount=self.max_files
            )
            file_handler.setFormatter(formatter)
            
            if self.dispatcher:
                root_logger.addHandler(self.dispatcher.create_handler(file_handler))
            else:
                root_logger.addHandler(file_handler)
    
    def get_logger(self, name: str, context: Dict[str, Any] = None) -> logging.Logger:
        """
        Get a logger with context.
        
        Args:
            name: Logger name
            context: Optional context to add to all logs
            
        Returns:
            Logger with context
        """
        # Get base logger
        logger = logging.getLogger(name)
        
        # Combine global and local context
        combined_context = self.global_context.copy()
        if context:
            combined_context.update(context)
        
        # Create adapter with context
        adapter = ContextAdapter(logger, combined_context)
        
        # Store for tracking
        self.loggers[name] = adapter
        
        return adapter
    
    def get_structlog_logger(self, name: str, **context) -> Any:
        """
        Get a structlog logger with context.
        
        Args:
            name: Logger name
            **context: Context key-value pairs
            
        Returns:
            Structlog logger or None if not available
        """
        if not self.structlog:
            self.logger.warning("structlog not available, falling back to standard logger")
            return self.get_logger(name, context)
            
        # Combine global and local context
        combined_context = self.global_context.copy()
        combined_context.update(context)
        
        # Create structlog logger
        logger = self.structlog.get_logger(name).bind(**combined_context)
        
        # Store for tracking (as standard logger)
        self.loggers[name] = logger
        
        return logger
    
    def set_global_context(self, **kwargs):
        """
        Set global context for all loggers.
        
        Args:
            **kwargs: Context key-value pairs
        """
        self.global_context.update(kwargs)
        
        # Update all existing loggers
        for name, logger in self.loggers.items():
            if hasattr(logger, 'extra'):  # Standard logger adapter
                combined_context = self.global_context.copy()
                # Only update with original context to avoid duplication
                original_context = {k: v for k, v in logger.extra.items() 
                                   if k not in self.global_context}
                combined_context.update(original_context)
                logger.extra = combined_context
            elif hasattr(logger, 'bind'):  # Structlog logger
                # Re-bind with global context
                logger = logger.bind(**self.global_context)
                self.loggers[name] = logger
    
    def update_log_level(self, log_level: str):
        """
        Update the log level.
        
        Args:
            log_level: New log level
        """
        # Convert string level to numeric
        numeric_level = getattr(logging, log_level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f"Invalid log level: {log_level}")
        
        # Update root logger
        logging.getLogger().setLevel(numeric_level)
        self.logger.info(f"Updated log level to {log_level}")
    
    def shutdown(self):
        """Shut down the logging manager"""
        if self.dispatcher:
            self.dispatcher.stop()
        
        self.logger.info("Logging Manager shutdown")


# Create singleton instance
logging_manager = LoggingManager() 