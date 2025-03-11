"""
Execution Optimization Module

This module provides optimization capabilities for order execution, including
exchange-specific optimization, smart order routing, execution algorithms,
and advanced execution strategies.

The optimization module is responsible for improving execution quality
through intelligent order placement, routing decisions, and execution timing.

Examples:
    Example usage can be found in the `examples` subpackage:
    - Exchange profiling and optimization: `examples.exchange_profiling_example`
    - Execution strategies: `examples.execution_strategies_example`
"""

# Import components
from .profiles import (
    ExchangeCapabilities, ExchangePerformance, ExchangeOptimizationParams,
    ExchangeCapabilityRegistry, get_exchange_registry,
    ExchangeProfiler, get_exchange_profiler
)

from .routers import (
    SmartOrderRouter, get_smart_order_router,
    OrderRoutingParameters, RoutingDecision, ExchangeRoutingDecision,
    RoutingPriority
)

from .order_types import (
    OrderTypeOptimizer, get_order_type_optimizer,
    OrderTypeCategory, TimeInForceType,
    MarketCondition as OrderMarketCondition,  # Rename to avoid conflict
    OrderTypeParameters, ExecutionPreferences,
    OrderTypeOptimizationRequest, OrderTypeRecommendation
)

from .strategies import (
    # Base classes
    ExecutionStrategy, ExecutionRequest, ExecutionSchedule, SubOrder,
    ExecutionPriority, ExecutionAlgorithm,
    
    # Strategy implementations
    BasicExecutionStrategy, TWAPStrategy, VWAPStrategy, 
    AdaptiveStrategy, MarketCondition, VolumeProfile
)

# Public API
__all__ = [
    # Exchange profiling and capabilities
    'ExchangeCapabilities',
    'ExchangePerformance', 
    'ExchangeOptimizationParams',
    'ExchangeCapabilityRegistry',
    'get_exchange_registry',
    'ExchangeProfiler',
    'get_exchange_profiler',
    
    # Smart order routing
    'SmartOrderRouter',
    'get_smart_order_router',
    'OrderRoutingParameters',
    'RoutingDecision',
    'ExchangeRoutingDecision',
    'RoutingPriority',
    
    # Order type optimization
    'OrderTypeOptimizer',
    'get_order_type_optimizer',
    'OrderTypeCategory',
    'TimeInForceType',
    'OrderMarketCondition',  # Renamed to avoid conflict
    'OrderTypeParameters',
    'ExecutionPreferences',
    'OrderTypeOptimizationRequest',
    'OrderTypeRecommendation',
    
    # Execution strategies
    'ExecutionStrategy',
    'ExecutionRequest',
    'ExecutionSchedule',
    'SubOrder',
    'ExecutionPriority',
    'ExecutionAlgorithm',
    'BasicExecutionStrategy',
    'TWAPStrategy',
    'VWAPStrategy',
    'AdaptiveStrategy',
    'MarketCondition',
    'VolumeProfile',
] 