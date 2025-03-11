"""
Execution Strategies Module

This module provides various execution strategies for optimizing order execution
based on different market conditions, order sizes, and execution goals.

The strategies control when and in what sequence to execute orders, working in
conjunction with the Smart Order Router (which determines where to execute) and
the Order Type Optimizer (which determines how to execute).
"""

from advanced_trading.execution.optimization.strategies.execution_strategy import (
    ExecutionStrategy, 
    ExecutionRequest, 
    ExecutionSchedule, 
    SubOrder, 
    ExecutionPriority,
    ExecutionAlgorithm
)

from advanced_trading.execution.optimization.strategies.basic_strategy import (
    BasicExecutionStrategy
)

from advanced_trading.execution.optimization.strategies.twap_strategy import (
    TWAPStrategy
)

from advanced_trading.execution.optimization.strategies.vwap_strategy import (
    VolumeProfile,
    VWAPStrategy
)

from advanced_trading.execution.optimization.strategies.adaptive_strategy import (
    MarketCondition,
    AdaptiveStrategy
)

# Public API
__all__ = [
    # Base classes
    'ExecutionStrategy',
    'ExecutionRequest',
    'ExecutionSchedule',
    'SubOrder',
    'ExecutionPriority',
    'ExecutionAlgorithm',
    
    # Strategies
    'BasicExecutionStrategy',
    'TWAPStrategy',
    'VolumeProfile',
    'VWAPStrategy',
    'MarketCondition',
    'AdaptiveStrategy',
] 