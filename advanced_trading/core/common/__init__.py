"""
Common Utilities

This module provides common utilities for the Instinct AI trading platform.
"""

# Basic validators
from .validators import validate_numeric_range, validate_string_choice, validate_list_length, validate_type, validate_url, validate_email

# Advanced validation framework
from .validation import (
    Validator, 
    ValidationResult, 
    ValidationError, 
    validator, 
    validate_ip_address, 
    validate_date, 
    validate_dict_schema
)

# Serialization utilities
from .serialization import (
    serialize,
    deserialize,
    serialize_to_json,
    deserialize_from_json,
    serialize_to_pickle,
    deserialize_from_pickle,
    serialize_to_file,
    deserialize_from_file,
    serialize_to_base64,
    deserialize_from_base64,
    compress_data,
    decompress_data,
    calculate_hash,
    SerializationFormat,
    SerializationError,
    DeserializationError
)

# Time utilities
from .time_utils import (
    format_time, 
    timestamp_to_datetime, 
    datetime_to_timestamp, 
    floor_dt_to_interval, 
    ceil_dt_to_interval, 
    time_interval_to_seconds, 
    get_current_timestamp, 
    get_current_datetime
)

# Math utilities
from .math_utils import (
    safe_divide, 
    exponential_moving_average, 
    simple_moving_average, 
    zscore, 
    calculate_sharpe_ratio, 
    calculate_sortino_ratio, 
    calculate_max_drawdown, 
    linear_regression
)

# Component registry
from .component_registry import (
    ComponentRegistry, 
    register_component, 
    get_component, 
    list_components, 
    clear_registry, 
    register_component_factory
)

__all__ = [
    # Basic validators
    'validate_numeric_range',
    'validate_string_choice',
    'validate_list_length',
    'validate_type',
    'validate_url',
    'validate_email',
    
    # Advanced validation framework
    'Validator',
    'ValidationResult',
    'ValidationError',
    'validator',
    'validate_ip_address',
    'validate_date',
    'validate_dict_schema',
    
    # Serialization utilities
    'serialize',
    'deserialize',
    'serialize_to_json',
    'deserialize_from_json',
    'serialize_to_pickle',
    'deserialize_from_pickle',
    'serialize_to_file',
    'deserialize_from_file',
    'serialize_to_base64',
    'deserialize_from_base64',
    'compress_data',
    'decompress_data',
    'calculate_hash',
    'SerializationFormat',
    'SerializationError',
    'DeserializationError',
    
    # Time utilities
    'format_time',
    'timestamp_to_datetime',
    'datetime_to_timestamp',
    'floor_dt_to_interval',
    'ceil_dt_to_interval',
    'time_interval_to_seconds',
    'get_current_timestamp',
    'get_current_datetime',
    
    # Math utilities
    'safe_divide',
    'exponential_moving_average',
    'simple_moving_average',
    'zscore',
    'calculate_sharpe_ratio',
    'calculate_sortino_ratio',
    'calculate_max_drawdown',
    'linear_regression',
    
    # Component registry
    'ComponentRegistry',
    'register_component',
    'register_component_factory',
    'get_component',
    'list_components',
    'clear_registry'
] 