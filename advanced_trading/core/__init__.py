"""
Core Module

This module provides core functionality for the Instinct AI trading platform.
It includes:

1. Configuration Management
2. Observability Framework
3. Common Utilities
4. Performance Optimization Framework
"""

from . import config
from . import observability
from . import common
from . import performance

__all__ = [
    'config',
    'observability',
    'common',
    'performance'
] 