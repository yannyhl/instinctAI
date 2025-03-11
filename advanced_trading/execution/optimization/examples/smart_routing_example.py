"""
Smart Order Router Example

This example demonstrates how to use the Smart Order Router to select
optimal exchanges for order execution based on various criteria.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Any
from datetime import datetime, timedelta

from advanced_trading.execution.optimization import (
    # Exchange registry and profiler
    get_exchange_registry, get_exchange_profiler,
    ExchangeCapabilities, ExchangePerformance,
    
    # Smart order router
    get_smart_order_router, SmartOrderRouter,
    OrderRoutingParameters, RoutingPriority
)

def setup_test_exchanges():
    """Set up test exchanges with different capabilities and performance metrics."""
    print("Setting up test exchanges...")
    
    # Get registry instance
    registry = get_exchange_registry()
    
    # Exchange A: General purpose exchange with balanced performance
    registry.register_exchange(
        exchange_id='exchange_a',
        capabilities={
            'maker_fee': 0.001,
            'taker_fee': 0.002,
            'min_order_size': 0.001,
            'price_precision': 5,
            'quantity_precision': 8,
            'supports_market_orders': True,
            'supports_limit_orders': True,
            'supports_stop_orders': True,
            'supports_post_only': True,
            'supports_fill_or_kill': True,
            'supports_immediate_or_cancel': True,
            'supports_reduce_only': True,
            'max_leverage': 10.0,
            'base_api_limit': 300
        },
        performance_data={
            'avg_api_latency_ms': 100.0,
            'api_error_rate': 0.01,
            'avg_fill_time_ms': 500.0,
            'market_order_slippage_bps': 5.0,
            'limit_order_fill_rate': 0.9,
            'avg_spread_bps': 10.0,
            'avg_liquidity_depth_usd': 2500000.0,
            'api_reliability_pct': 99.8,
            'exchange_reliability_score': 8.7
        },
        symbols=['BTC/USD', 'ETH/USD', 'SOL/USD', 'DOGE/USD']
    )
    
    # Exchange B: Low fee exchange with faster execution but less features
    registry.register_exchange(
        exchange_id='exchange_b',
        capabilities={
            'maker_fee': 0.0005,
            'taker_fee': 0.001,
            'min_order_size': 0.0005,
            'price_precision': 5,
            'quantity_precision': 6,
            'supports_market_orders': True,
            'supports_limit_orders': True,
            'supports_stop_orders': False,
            'supports_post_only': True,
            'supports_fill_or_kill': False,
            'supports_immediate_or_cancel': True,
            'supports_reduce_only': True,
            'max_leverage': 20.0,
            'base_api_limit': 200
        },
        performance_data={
            'avg_api_latency_ms': 80.0,
            'api_error_rate': 0.015,
            'avg_fill_time_ms': 350.0,
            'market_order_slippage_bps': 6.5,
            'limit_order_fill_rate': 0.85,
            'avg_spread_bps': 8.0,
            'avg_liquidity_depth_usd': 3500000.0,
            'api_reliability_pct': 99.5,
            'exchange_reliability_score': 8.2
        },
        symbols=['BTC/USD', 'ETH/USD', 'SOL/USD']
    )
    
    # Exchange C: High reliability exchange with higher fees
    registry.register_exchange(
        exchange_id='exchange_c',
        capabilities={
            'maker_fee': 0.0015,
            'taker_fee': 0.0025,
            'min_order_size': 0.001,
            'price_precision': 5,
            'quantity_precision': 8,
            'supports_market_orders': True,
            'supports_limit_orders': True,
            'supports_stop_orders': True,
            'supports_post_only': True,
            'supports_fill_or_kill': True,
            'supports_immediate_or_cancel': True,
            'supports_reduce_only': True,
            'supports_trailing_stop': True,
            'max_leverage': 5.0,
            'base_api_limit': 150
        },
        performance_data={
            'avg_api_latency_ms': 120.0,
            'api_error_rate': 0.005,
            'avg_fill_time_ms': 600.0,
            'market_order_slippage_bps': 4.0,
            'limit_order_fill_rate': 0.95,
            'avg_spread_bps': 12.0,
            'avg_liquidity_depth_usd': 2000000.0,
            'api_reliability_pct': 99.95,
            'exchange_reliability_score': 9.5
        },
        symbols=['BTC/USD', 'ETH/USD']
    )
    
    # Exchange D: Deep liquidity but higher latency
    registry.register_exchange(
        exchange_id='exchange_d',
        capabilities={
            'maker_fee': 0.0010,
            'taker_fee': 0.0018,
            'min_order_size': 0.001,
            'price_precision': 5,
            'quantity_precision': 8,
            'supports_market_orders': True,
            'supports_limit_orders': True,
            'supports_stop_orders': True,
            'supports_post_only': True,
            'supports_fill_or_kill': False,
            'supports_immediate_or_cancel': True,
            'supports_reduce_only': False,
            'max_leverage': 3.0,
            'base_api_limit': 120
        },
        performance_data={
            'avg_api_latency_ms': 150.0,
            'api_error_rate': 0.008,
            'avg_fill_time_ms': 800.0,
            'market_order_slippage_bps': 3.5,
            'limit_order_fill_rate': 0.92,
            'avg_spread_bps': 7.0,
            'avg_liquidity_depth_usd': 5000000.0,
            'api_reliability_pct': 99.7,
            'exchange_reliability_score': 8.8
        },
        symbols=['BTC/USD', 'ETH/USD', 'SOL/USD']
    )
    
    # Record some symbol-specific metrics
    profiler = get_exchange_profiler()
    
    # BTC/USD metrics
    for exchange in ['exchange_a', 'exchange_b', 'exchange_c', 'exchange_d']:
        if exchange == 'exchange_a':
            spread_bps = 6.0
            liquidity = 5000000.0
        elif exchange == 'exchange_b':
            spread_bps = 5.0
            liquidity = 8000000.0
        elif exchange == 'exchange_c':
            spread_bps = 7.0
            liquidity = 4000000.0
        else:  # exchange_d
            spread_bps = 4.0
            liquidity = 12000000.0
        
        profiler.record_spread_data(
            exchange_id=exchange,
            symbol='BTC/USD',
            spread_bps=spread_bps,
            liquidity_depth_usd=liquidity
        )
    
    # ETH/USD metrics
    for exchange in ['exchange_a', 'exchange_b', 'exchange_c', 'exchange_d']:
        if exchange == 'exchange_a':
            spread_bps = 8.0
            liquidity = 3000000.0
        elif exchange == 'exchange_b':
            spread_bps = 7.0
            liquidity = 4000000.0
        elif exchange == 'exchange_c':
            spread_bps = 9.0
            liquidity = 2500000.0
        else:  # exchange_d
            spread_bps = 5.5
            liquidity = 6000000.0
        
        profiler.record_spread_data(
            exchange_id=exchange,
            symbol='ETH/USD',
            spread_bps=spread_bps,
            liquidity_depth_usd=liquidity
        )
    
    # SOL/USD metrics (not all exchanges support this)
    for exchange in ['exchange_a', 'exchange_b', 'exchange_d']:
        if exchange == 'exchange_a':
            spread_bps = 12.0
            liquidity = 1000000.0
        elif exchange == 'exchange_b':
            spread_bps = 10.0
            liquidity = 1500000.0
        else:  # exchange_d
            spread_bps = 9.0
            liquidity = 2000000.0
        
        profiler.record_spread_data(
            exchange_id=exchange,
            symbol='SOL/USD',
            spread_bps=spread_bps,
            liquidity_depth_usd=liquidity
        )
    
    # DOGE/USD metrics (only exchange_a supports this)
    profiler.record_spread_data(
        exchange_id='exchange_a',
        symbol='DOGE/USD',
        spread_bps=20.0,
        liquidity_depth_usd=500000.0
    )
    
    # Let profiler update the registry
    time.sleep(1)
    profiler._update_registry()
    
    print("Test exchanges setup complete")

def test_routing_with_different_priorities():
    """Test routing decisions with different priorities."""
    print("\nTesting different routing priorities...")
    
    # Get router instance
    router = get_smart_order_router()
    
    # Test parameters
    base_params = {
        'symbol': 'BTC/USD',
        'side': 'buy',
        'size': 1.0,
        'size_usd': 50000.0,
        'order_type': 'market'
    }
    
    # Try different priorities
    priorities = [
        ('LOWEST_FEES', RoutingPriority.LOWEST_FEES),
        ('BEST_EXECUTION', RoutingPriority.BEST_EXECUTION),
        ('FASTEST_EXECUTION', RoutingPriority.FASTEST_EXECUTION),
        ('HIGHEST_RELIABILITY', RoutingPriority.HIGHEST_RELIABILITY),
        ('BEST_LIQUIDITY', RoutingPriority.BEST_LIQUIDITY),
        ('BALANCED', RoutingPriority.BALANCED)
    ]
    
    results = []
    
    for priority_name, priority in priorities:
        params = OrderRoutingParameters(
            **base_params,
            priority=priority
        )
        
        decision = router.route_order(params)
        
        if not decision.exchange_decisions:
            print(f"  {priority_name}: No eligible exchanges")
            continue
        
        best_exchange = decision.exchange_decisions[0].exchange_id
        score = decision.exchange_decisions[0].score
        
        print(f"  {priority_name}: Best exchange is {best_exchange} with score {score:.2f}")
        
        results.append({
            'priority': priority_name,
            'best_exchange': best_exchange,
            'score': score,
            'is_split': decision.is_split
        })
    
    return results

def test_routing_with_different_sizes():
    """Test routing decisions with different order sizes."""
    print("\nTesting different order sizes...")
    
    # Get router instance
    router = get_smart_order_router()
    
    # Test different sizes
    sizes = [
        ('Small', 0.1, 5000.0),
        ('Medium', 1.0, 50000.0),
        ('Large', 10.0, 500000.0),
        ('Very Large', 100.0, 5000000.0)
    ]
    
    results = []
    
    for size_name, size, size_usd in sizes:
        params = OrderRoutingParameters(
            symbol='BTC/USD',
            side='buy',
            size=size,
            size_usd=size_usd,
            order_type='market',
            allow_split=True
        )
        
        decision = router.route_order(params)
        
        if not decision.exchange_decisions:
            print(f"  {size_name} order (${size_usd:,.0f}): No eligible exchanges")
            continue
        
        if decision.is_split:
            exchanges = [ed.exchange_id for ed in decision.exchange_decisions]
            sizes = [ed.size for ed in decision.exchange_decisions]
            print(f"  {size_name} order (${size_usd:,.0f}): Split across {len(exchanges)} exchanges:")
            for i, (ex, sz) in enumerate(zip(exchanges, sizes)):
                print(f"    {i+1}. {ex}: {sz} BTC")
        else:
            best_exchange = decision.exchange_decisions[0].exchange_id
            print(f"  {size_name} order (${size_usd:,.0f}): Routed to {best_exchange}")
        
        results.append({
            'size_name': size_name,
            'size_usd': size_usd,
            'is_split': decision.is_split,
            'num_exchanges': len(decision.exchange_decisions),
            'exchanges': [ed.exchange_id for ed in decision.exchange_decisions]
        })
    
    return results

def test_routing_with_different_urgency():
    """Test routing decisions with different urgency levels."""
    print("\nTesting different urgency levels...")
    
    # Get router instance
    router = get_smart_order_router()
    
    # Test different urgency levels
    urgency_levels = [
        ('Very Low', 0.1),
        ('Low', 0.3),
        ('Medium', 0.5),
        ('High', 0.7),
        ('Very High', 0.9)
    ]
    
    results = []
    
    for urgency_name, urgency in urgency_levels:
        params = OrderRoutingParameters(
            symbol='BTC/USD',
            side='buy',
            size=1.0,
            size_usd=50000.0,
            order_type='market',
            urgency=urgency
        )
        
        decision = router.route_order(params)
        
        if not decision.exchange_decisions:
            print(f"  {urgency_name} urgency ({urgency}): No eligible exchanges")
            continue
        
        best_exchange = decision.exchange_decisions[0].exchange_id
        score = decision.exchange_decisions[0].score
        
        print(f"  {urgency_name} urgency ({urgency}): Best exchange is {best_exchange} with score {score:.2f}")
        
        results.append({
            'urgency': urgency_name,
            'urgency_value': urgency,
            'best_exchange': best_exchange,
            'score': score,
            'is_split': decision.is_split
        })
    
    return results

def test_routing_with_different_order_types():
    """Test routing decisions with different order types."""
    print("\nTesting different order types...")
    
    # Get router instance
    router = get_smart_order_router()
    
    # Test different order types
    order_types = [
        ('Market', 'market', None),
        ('Limit', 'limit', 50000.0),
        ('Post-Only Limit', 'limit', 50000.0, True, False),
        ('IOC', 'limit', 50000.0, False, False, 'immediate_or_cancel')
    ]
    
    results = []
    
    for type_params in order_types:
        if len(type_params) == 3:
            type_name, order_type, price = type_params
            post_only = False
            reduce_only = False
            time_in_force = 'good_till_cancel'
        elif len(type_params) == 5:
            type_name, order_type, price, post_only, reduce_only = type_params
            time_in_force = 'good_till_cancel'
        else:
            type_name, order_type, price, post_only, reduce_only, time_in_force = type_params
        
        params = OrderRoutingParameters(
            symbol='BTC/USD',
            side='buy',
            size=1.0,
            size_usd=50000.0,
            order_type=order_type,
            price=price,
            post_only=post_only,
            reduce_only=reduce_only,
            time_in_force=time_in_force
        )
        
        decision = router.route_order(params)
        
        if not decision.exchange_decisions:
            print(f"  {type_name}: No eligible exchanges")
            continue
        
        best_exchange = decision.exchange_decisions[0].exchange_id
        expected_fee = decision.exchange_decisions[0].expected_fee
        expected_slippage = decision.exchange_decisions[0].expected_slippage
        
        print(f"  {type_name}: Best exchange is {best_exchange}")
        print(f"    Expected fee: ${expected_fee:.2f}")
        
        if order_type == 'market':
            print(f"    Expected slippage: {expected_slippage:.2f} bps")
        
        results.append({
            'order_type': type_name,
            'best_exchange': best_exchange,
            'expected_fee': expected_fee,
            'expected_slippage': expected_slippage if order_type == 'market' else 0.0
        })
    
    return results

def test_routing_with_different_symbols():
    """Test routing decisions with different symbols."""
    print("\nTesting different symbols...")
    
    # Get router instance
    router = get_smart_order_router()
    
    # Test different symbols
    symbols = ['BTC/USD', 'ETH/USD', 'SOL/USD', 'DOGE/USD']
    
    results = []
    
    for symbol in symbols:
        params = OrderRoutingParameters(
            symbol=symbol,
            side='buy',
            size=1.0,
            size_usd=50000.0,
            order_type='market'
        )
        
        decision = router.route_order(params)
        
        if not decision.exchange_decisions:
            print(f"  {symbol}: No eligible exchanges")
            continue
        
        eligible_exchanges = [ed.exchange_id for ed in decision.exchange_decisions]
        best_exchange = eligible_exchanges[0]
        
        print(f"  {symbol}: Best exchange is {best_exchange}")
        if decision.is_split:
            print(f"    Split across: {', '.join(eligible_exchanges)}")
        
        results.append({
            'symbol': symbol,
            'eligible_exchanges': eligible_exchanges,
            'best_exchange': best_exchange,
            'is_split': decision.is_split
        })
    
    return results

def plot_exchange_scores(priority_results):
    """Plot exchange scores for different routing priorities."""
    print("\nPlotting exchange scores...")
    
    # Prepare data
    priorities = []
    exchanges = set()
    scores_by_exchange = {}
    
    for result in priority_results:
        priorities.append(result['priority'])
        exchange = result['best_exchange']
        exchanges.add(exchange)
        
        if exchange not in scores_by_exchange:
            scores_by_exchange[exchange] = []
        
        # Ensure scores_by_exchange[exchange] has the right length
        while len(scores_by_exchange[exchange]) < len(priorities) - 1:
            scores_by_exchange[exchange].append(0)
        
        scores_by_exchange[exchange].append(result['score'])
    
    # Make sure all exchanges have scores for all priorities
    for exchange in exchanges:
        while len(scores_by_exchange[exchange]) < len(priorities):
            scores_by_exchange[exchange].append(0)
    
    # Plot
    plt.figure(figsize=(12, 6))
    bar_width = 0.15
    index = np.arange(len(priorities))
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    
    for i, (exchange, scores) in enumerate(scores_by_exchange.items()):
        plt.bar(index + i * bar_width, scores, bar_width,
                label=exchange, color=colors[i % len(colors)])
    
    plt.xlabel('Routing Priority')
    plt.ylabel('Exchange Score')
    plt.title('Exchange Scores by Routing Priority')
    plt.xticks(index + bar_width * (len(exchanges) - 1) / 2, priorities)
    plt.legend()
    plt.tight_layout()
    plt.show()

def main():
    """Main function to demonstrate smart order routing."""
    print("Smart Order Router Example")
    print("=========================\n")
    
    # Set up test exchanges
    setup_test_exchanges()
    
    # Run tests with different priorities
    priority_results = test_routing_with_different_priorities()
    
    # Test with different order sizes
    size_results = test_routing_with_different_sizes()
    
    # Test with different urgency levels
    urgency_results = test_routing_with_different_urgency()
    
    # Test with different order types
    order_type_results = test_routing_with_different_order_types()
    
    # Test with different symbols
    symbol_results = test_routing_with_different_symbols()
    
    # Plot results
    try:
        plot_exchange_scores(priority_results)
    except Exception as e:
        print(f"Error plotting results: {e}")
    
    print("\nExample complete!")

if __name__ == "__main__":
    main() 