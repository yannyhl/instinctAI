"""
Order Type Optimization Module

This module provides functionality to select the optimal order type and parameters
based on market conditions, exchange capabilities, and execution objectives.
"""

from typing import Dict, List, Optional, Tuple, Any, Union

# Import components
from .order_type_optimizer import (
    OrderTypeOptimizer, get_order_type_optimizer,
    OrderTypeCategory, TimeInForceType,
    MarketCondition, OrderTypeParameters, ExecutionPreferences,
    OrderTypeOptimizationRequest, OrderTypeRecommendation
)

# Public API
__all__ = [
    'OrderTypeOptimizer',
    'get_order_type_optimizer',
    'OrderTypeCategory',
    'TimeInForceType',
    'MarketCondition',
    'OrderTypeParameters',
    'ExecutionPreferences',
    'OrderTypeOptimizationRequest',
    'OrderTypeRecommendation'
] 