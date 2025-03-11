# Execution Optimization

This module provides optimization capabilities for order execution, including exchange-specific optimization, smart order routing, and execution algorithms.

## Overview

The execution optimization module is designed to improve trading execution quality by:

- Tracking and profiling exchange characteristics
- Making intelligent routing decisions
- Optimizing order parameters
- Analyzing execution performance
- Adapting to changing market conditions

## Components

### Exchange Capability Registry

The `ExchangeCapabilityRegistry` provides a centralized registry for exchange capabilities, performance metrics, and optimization parameters. It's used to make intelligent decisions about order routing, parameter selection, and execution strategies.

```python
from advanced_trading.execution.optimization import (
    get_exchange_registry, ExchangeCapabilities
)

# Get registry instance
registry = get_exchange_registry()

# Register a new exchange
registry.register_exchange(
    exchange_id='binance',
    capabilities={
        'maker_fee': 0.001,
        'taker_fee': 0.001,
        'min_order_size': 0.001,
        'price_precision': 8,
        'supports_market_orders': True,
        'supports_limit_orders': True,
        'supports_post_only': True
    },
    symbols=['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
)

# Get exchange capabilities
binance_caps = registry.get_exchange_capabilities('binance')

# Get execution parameters
params = registry.get_execution_parameters(
    exchange_id='binance',
    order_type='limit',
    symbol='BTC/USDT',
    size_usd=10000
)

# Rank exchanges by criteria
top_exchanges = registry.rank_exchanges(
    symbol='BTC/USDT', 
    criteria={
        'fees': 0.3,
        'latency': 0.3,
        'reliability': 0.4
    }
)
```

### Exchange Profiler

The `ExchangeProfiler` tracks exchange behavior, performance metrics, and reliability in real-time. It continuously monitors and analyzes performance data to optimize execution decisions.

```python
from advanced_trading.execution.optimization import get_exchange_profiler

# Get profiler instance
profiler = get_exchange_profiler()

# Record API call performance
profiler.record_api_call(
    exchange_id='binance',
    latency_ms=120,
    success=True
)

# Record market order execution
profiler.record_market_order(
    exchange_id='binance',
    symbol='BTC/USDT',
    expected_price=50000.0,
    executed_price=50010.0,
    side='buy'
)

# Record limit order execution
profiler.record_limit_order(
    exchange_id='binance',
    symbol='BTC/USDT',
    filled=True,
    time_to_fill_ms=3500
)

# Get exchange metrics
metrics = profiler.get_exchange_metrics('binance')

# Get symbol-specific metrics
symbol_metrics = profiler.get_symbol_metrics('binance', 'BTC/USDT')
```

### Smart Order Router

The `SmartOrderRouter` determines the optimal exchange and routing strategy for order execution. It analyzes exchange capabilities, performance metrics, and current market conditions to make intelligent routing decisions.

```python
from advanced_trading.execution.optimization import (
    get_smart_order_router, OrderRoutingParameters, RoutingPriority
)

# Get router instance
router = get_smart_order_router()

# Create routing parameters
params = OrderRoutingParameters(
    symbol='BTC/USD',
    side='buy',
    size=1.0,
    size_usd=50000.0,
    order_type='market',
    urgency=0.7,  # Higher urgency prioritizes speed and execution quality
    allow_split=True  # Allow splitting orders across exchanges
)

# Get routing decision
decision = router.route_order(params)

# Check if the order was split
if decision.is_split:
    print(f"Order split across {len(decision.exchange_decisions)} exchanges:")
    for exchange_decision in decision.exchange_decisions:
        print(f"  {exchange_decision.exchange_id}: {exchange_decision.size} BTC")
else:
    exchange = decision.exchange_decisions[0].exchange_id
    print(f"Order routed to {exchange}")

# Use custom routing priorities
params = OrderRoutingParameters(
    symbol='BTC/USD',
    side='buy',
    size=1.0,
    size_usd=50000.0,
    order_type='market',
    priority=RoutingPriority.LOWEST_FEES  # Prioritize lowest fees
)

decision = router.route_order(params)
```

### Order Type Optimizer (Coming Soon)

The Order Type Optimizer will select the best order type and parameters for specific market conditions:

- Adaptive parameter selection
- Dynamic time-in-force optimization
- Market/limit switch logic
- Advanced order types utilization

## Integration

The execution optimization module integrates with other system components:

- **Market Microstructure Analysis**: Uses order book analytics to inform execution decisions
- **Risk Management**: Considers position-level and portfolio-level risk metrics
- **Strategy Engine**: Receives execution requests from trading strategies
- **Exchange Connectors**: Sends optimized orders to exchanges
- **Observability**: Provides performance metrics and execution analytics

## Configuration

The optimization components can be configured through the registry:

```python
# Update optimization parameters
registry.update_exchange_metrics(
    exchange_id='binance',
    metrics_update={
        'max_slippage_tolerance_bps': 10.0,
        'default_limit_order_distance_bps': 0.5,
        'use_market_threshold_urgency': 0.75
    }
)

# Save configuration to file
registry.save_to_config('config/exchange_profiles.json')
```

## Performance Considerations

- The profiler runs in a background thread that periodically updates the registry
- Metrics are stored in circular buffers to limit memory usage
- The registry uses thread-safe operations with a read-write lock
- Real-time metrics are available for execution decisions without waiting for periodic updates 

## Examples

The `examples` directory contains sample scripts demonstrating how to use the Exchange Optimization components:

### Exchange Profiling Example

The `exchange_profiling_example.py` script demonstrates:

```python
from advanced_trading.execution.optimization import (
    get_exchange_registry, get_exchange_profiler
)

# Get registry and profiler instances
registry = get_exchange_registry()
profiler = get_exchange_profiler()

# Register exchanges with capabilities
registry.register_exchange(
    exchange_id='exchange_a',
    capabilities={
        'maker_fee': 0.001,
        'taker_fee': 0.002,
        'supports_market_orders': True,
        'supports_limit_orders': True,
        # ... other capabilities
    },
    symbols=['BTC/USD', 'ETH/USD']
)

# Record API call performance
profiler.record_api_call(
    exchange_id='exchange_a',
    latency_ms=120,
    success=True
)

# Record market order execution
profiler.record_market_order(
    exchange_id='exchange_a',
    symbol='BTC/USD',
    expected_price=50000.0,
    executed_price=50010.0,
    side='buy'
)

# Get exchange metrics
metrics = profiler.get_exchange_metrics('exchange_a')

# Rank exchanges by criteria
rankings = registry.rank_exchanges(
    symbol='BTC/USD', 
    criteria={
        'fees': 0.3,
        'latency': 0.3,
        'reliability': 0.4
    }
)
```

To run the example:

```bash
python -m advanced_trading.execution.optimization.examples.exchange_profiling_example
```

See the `examples/README.md` file for more details on available examples and how to run them. 