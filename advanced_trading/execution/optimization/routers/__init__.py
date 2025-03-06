"""
Order Routing Module

This module provides smart order routing capabilities that select the optimal exchanges
and order parameters for trade execution based on various criteria like fees, execution
quality, reliability, and liquidity.
"""

from typing import Dict, List, Optional, Union, Tuple, Any

# Import components
from .smart_order_router import (
    SmartOrderRouter, get_smart_order_router,
    OrderRoutingParameters, RoutingDecision, ExchangeRoutingDecision,
    RoutingPriority
)

# Public API
__all__ = [
    'SmartOrderRouter',
    'get_smart_order_router',
    'OrderRoutingParameters', 
    'RoutingDecision',
    'ExchangeRoutingDecision',
    'RoutingPriority'
] 