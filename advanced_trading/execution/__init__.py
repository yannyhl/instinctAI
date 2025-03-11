"""
Execution Module

This module provides tools and utilities for order execution in the Instinct AI trading platform, including:
- Exchange connectivity: Interfaces to various exchanges and trading venues
- Execution monitoring: Real-time monitoring of order execution and fills
- Execution optimization: Algorithms to optimize order execution and minimize market impact

The execution module is responsible for turning trading signals into actual orders and
ensuring that they are executed efficiently and with minimal market impact.
"""

from typing import Dict, List, Optional, Union, Callable, Any

# Import exchange components
from .exchange.client import (
    ExchangeClient, connect_exchange, disconnect_exchange,
    get_exchange_info, list_available_exchanges
)
from .exchange.order import (
    create_order, submit_order, cancel_order, modify_order,
    get_order_status, get_order_history, get_open_orders
)
from .exchange.account import (
    get_account_balance, get_account_positions, get_account_info,
    get_order_book, get_ticker, get_market_depth
)

# Import monitoring components
from .monitoring.execution import (
    monitor_execution, get_execution_stats, execution_summary,
    execution_quality, execution_efficiency, slippage_analysis
)
from .monitoring.orders import (
    monitor_orders, track_order_status, order_lifecycle,
    order_fill_rate, order_latency, order_rejection_analysis
)
from .monitoring.market import (
    monitor_market_conditions, get_market_impact, market_liquidity,
    volatility_impact, spread_analysis, depth_analysis
)

# Import optimization components
from .optimization.algorithms import (
    twap_execution, vwap_execution, implementation_shortfall,
    adaptive_execution, smart_order_routing, iceberg_orders
)
from .optimization.parameters import (
    optimize_execution_parameters, estimate_market_impact,
    optimal_order_size, optimal_order_timing, execution_urgency
)
from .optimization.evaluation import (
    evaluate_execution_performance, benchmark_execution,
    execution_cost_analysis, execution_strategy_comparison
)

# Public API
__all__ = [
    # Exchange connectivity
    'ExchangeClient', 'connect_exchange', 'disconnect_exchange',
    'get_exchange_info', 'list_available_exchanges',
    'create_order', 'submit_order', 'cancel_order', 'modify_order',
    'get_order_status', 'get_order_history', 'get_open_orders',
    'get_account_balance', 'get_account_positions', 'get_account_info',
    'get_order_book', 'get_ticker', 'get_market_depth',
    
    # Execution monitoring
    'monitor_execution', 'get_execution_stats', 'execution_summary',
    'execution_quality', 'execution_efficiency', 'slippage_analysis',
    'monitor_orders', 'track_order_status', 'order_lifecycle',
    'order_fill_rate', 'order_latency', 'order_rejection_analysis',
    'monitor_market_conditions', 'get_market_impact', 'market_liquidity',
    'volatility_impact', 'spread_analysis', 'depth_analysis',
    
    # Execution optimization
    'twap_execution', 'vwap_execution', 'implementation_shortfall',
    'adaptive_execution', 'smart_order_routing', 'iceberg_orders',
    'optimize_execution_parameters', 'estimate_market_impact',
    'optimal_order_size', 'optimal_order_timing', 'execution_urgency',
    'evaluate_execution_performance', 'benchmark_execution',
    'execution_cost_analysis', 'execution_strategy_comparison',
]

# Version information
__version__ = '0.1.0' 