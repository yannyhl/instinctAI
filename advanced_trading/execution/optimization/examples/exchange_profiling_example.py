"""
Exchange Profiling and Optimization Example

This example demonstrates how to use the exchange profiling and optimization components
to track exchange performance and optimize execution parameters.
"""

import time
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, Any

from advanced_trading.execution.optimization import (
    get_exchange_registry, get_exchange_profiler,
    ExchangeCapabilities, ExchangePerformance
)

def simulate_api_calls(profiler, exchange_id: str, count: int = 100):
    """Simulate API calls to an exchange and record performance."""
    print(f"Simulating {count} API calls to {exchange_id}...")
    
    # Latency distribution parameters for different exchanges
    latency_params = {
        'exchange_a': (100, 30),  # mean, std
        'exchange_b': (85, 40),
        'exchange_c': (120, 25)
    }
    
    # Error rate parameters
    error_rates = {
        'exchange_a': 0.02,
        'exchange_b': 0.04,
        'exchange_c': 0.01
    }
    
    # Default parameters if exchange not found
    mean_latency = 100
    std_latency = 30
    error_rate = 0.03
    
    # Get parameters for this exchange
    if exchange_id in latency_params:
        mean_latency, std_latency = latency_params[exchange_id]
    
    if exchange_id in error_rates:
        error_rate = error_rates[exchange_id]
    
    # Simulate API calls
    for i in range(count):
        # Simulate latency (ms)
        latency = max(10, np.random.normal(mean_latency, std_latency))
        
        # Simulate success/failure
        success = random.random() > error_rate
        
        # Simulate error type
        error_type = None
        if not success:
            error_types = ['timeout', 'rate_limit', 'internal_error']
            error_type = random.choice(error_types)
        
        # Record API call
        profiler.record_api_call(
            exchange_id=exchange_id,
            latency_ms=latency,
            success=success,
            error_type=error_type
        )
        
        # Small delay between calls
        time.sleep(0.01)
    
    print(f"Completed API call simulation for {exchange_id}")

def simulate_market_orders(profiler, exchange_id: str, symbol: str, count: int = 50):
    """Simulate market order executions and record performance."""
    print(f"Simulating {count} market orders on {exchange_id} for {symbol}...")
    
    # Slippage distribution parameters (basis points)
    slippage_params = {
        'exchange_a': (5.0, 3.0),  # mean, std
        'exchange_b': (3.5, 2.0),
        'exchange_c': (7.0, 4.0)
    }
    
    # Default parameters if exchange not found
    mean_slippage = 5.0
    std_slippage = 3.0
    
    # Get parameters for this exchange
    if exchange_id in slippage_params:
        mean_slippage, std_slippage = slippage_params[exchange_id]
    
    # Base price for the symbol
    base_prices = {
        'BTC/USD': 50000.0,
        'ETH/USD': 3000.0,
        'SOL/USD': 100.0
    }
    
    base_price = base_prices.get(symbol, 1000.0)
    
    # Simulate market orders
    for i in range(count):
        # Simulate expected price with small random fluctuation
        expected_price = base_price * (1 + np.random.normal(0, 0.001))
        
        # Simulate executed price with slippage
        # Slippage is higher for buys, lower for sells
        side = random.choice(['buy', 'sell'])
        
        # Adjust mean slippage based on side
        side_factor = 1.2 if side == 'buy' else 0.8
        order_slippage = np.random.normal(mean_slippage * side_factor, std_slippage)
        
        # Calculate executed price
        if side == 'buy':
            # For buys, executed price is typically higher (positive slippage)
            slippage_factor = order_slippage / 10000  # Convert bps to ratio
            executed_price = expected_price * (1 + slippage_factor)
        else:
            # For sells, executed price is typically lower (positive slippage)
            slippage_factor = order_slippage / 10000  # Convert bps to ratio
            executed_price = expected_price * (1 - slippage_factor)
        
        # Record market order
        profiler.record_market_order(
            exchange_id=exchange_id,
            symbol=symbol,
            expected_price=expected_price,
            executed_price=executed_price,
            side=side
        )
        
        # Small delay between orders
        time.sleep(0.01)
    
    print(f"Completed market order simulation for {exchange_id} on {symbol}")

def simulate_limit_orders(profiler, exchange_id: str, symbol: str, count: int = 50):
    """Simulate limit order executions and record performance."""
    print(f"Simulating {count} limit orders on {exchange_id} for {symbol}...")
    
    # Fill rate parameters
    fill_rate_params = {
        'exchange_a': 0.85,
        'exchange_b': 0.92,
        'exchange_c': 0.78
    }
    
    # Fill time parameters (ms)
    fill_time_params = {
        'exchange_a': (2000, 1000),  # mean, std
        'exchange_b': (1500, 800),
        'exchange_c': (3000, 1500)
    }
    
    # Default parameters if exchange not found
    fill_rate = 0.85
    mean_fill_time = 2000
    std_fill_time = 1000
    
    # Get parameters for this exchange
    if exchange_id in fill_rate_params:
        fill_rate = fill_rate_params[exchange_id]
    
    if exchange_id in fill_time_params:
        mean_fill_time, std_fill_time = fill_time_params[exchange_id]
    
    # Simulate limit orders
    for i in range(count):
        # Simulate fill status
        filled = random.random() < fill_rate
        
        # Simulate fill time (only if filled)
        time_to_fill_ms = None
        if filled:
            time_to_fill_ms = max(100, np.random.normal(mean_fill_time, std_fill_time))
        
        # Record limit order
        profiler.record_limit_order(
            exchange_id=exchange_id,
            symbol=symbol,
            filled=filled,
            time_to_fill_ms=time_to_fill_ms
        )
        
        # Small delay between orders
        time.sleep(0.01)
    
    print(f"Completed limit order simulation for {exchange_id} on {symbol}")

def simulate_spread_data(profiler, exchange_id: str, symbol: str, count: int = 100):
    """Simulate spread and liquidity data and record them."""
    print(f"Simulating {count} spread measurements on {exchange_id} for {symbol}...")
    
    # Spread parameters (basis points)
    spread_params = {
        'exchange_a': (8.0, 3.0),  # mean, std
        'exchange_b': (6.0, 2.0),
        'exchange_c': (10.0, 4.0)
    }
    
    # Liquidity depth parameters (USD)
    depth_params = {
        'exchange_a': (2500000, 500000),  # mean, std
        'exchange_b': (3500000, 700000),
        'exchange_c': (1800000, 400000)
    }
    
    # Symbol multipliers
    symbol_spread_multipliers = {
        'BTC/USD': 1.0,
        'ETH/USD': 1.2,
        'SOL/USD': 1.5
    }
    
    symbol_depth_multipliers = {
        'BTC/USD': 1.0,
        'ETH/USD': 0.7,
        'SOL/USD': 0.4
    }
    
    # Default parameters if exchange not found
    mean_spread = 8.0
    std_spread = 3.0
    mean_depth = 2500000
    std_depth = 500000
    
    # Get parameters for this exchange
    if exchange_id in spread_params:
        mean_spread, std_spread = spread_params[exchange_id]
    
    if exchange_id in depth_params:
        mean_depth, std_depth = depth_params[exchange_id]
    
    # Apply symbol multipliers
    spread_multiplier = symbol_spread_multipliers.get(symbol, 1.0)
    depth_multiplier = symbol_depth_multipliers.get(symbol, 1.0)
    
    mean_spread *= spread_multiplier
    mean_depth *= depth_multiplier
    std_depth *= depth_multiplier
    
    # Simulate spread and depth measurements
    for i in range(count):
        # Simulate spread (bps)
        spread_bps = max(1.0, np.random.normal(mean_spread, std_spread))
        
        # Simulate liquidity depth (USD)
        liquidity_depth_usd = max(100000, np.random.normal(mean_depth, std_depth))
        
        # Record spread and depth data
        profiler.record_spread_data(
            exchange_id=exchange_id,
            symbol=symbol,
            spread_bps=spread_bps,
            liquidity_depth_usd=liquidity_depth_usd
        )
        
        # Small delay between measurements
        time.sleep(0.01)
    
    print(f"Completed spread data simulation for {exchange_id} on {symbol}")

def setup_test_exchanges(registry):
    """Set up test exchanges in the registry."""
    print("Setting up test exchanges...")
    
    # Exchange A: General-purpose exchange with good all-around performance
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
        symbols=['BTC/USD', 'ETH/USD', 'SOL/USD']
    )
    
    # Exchange B: High-performance exchange with low fees but fewer features
    registry.register_exchange(
        exchange_id='exchange_b',
        capabilities={
            'maker_fee': 0.0005,
            'taker_fee': 0.001,
            'min_order_size': 0.0005,
            'price_precision': 6,
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
        symbols=['BTC/USD', 'ETH/USD', 'SOL/USD']
    )
    
    # Exchange C: Feature-rich but higher fees and lower performance
    registry.register_exchange(
        exchange_id='exchange_c',
        capabilities={
            'maker_fee': 0.0015,
            'taker_fee': 0.0025,
            'min_order_size': 0.001,
            'price_precision': 4,
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
        symbols=['BTC/USD', 'ETH/USD']  # Doesn't support SOL/USD
    )
    
    print("Test exchanges set up successfully")

def print_exchange_ranking(registry, symbol: str = 'BTC/USD'):
    """Print exchange rankings for a symbol."""
    print(f"\nExchange Rankings for {symbol}")
    print("=" * 50)
    
    criteria_sets = [
        {
            'name': 'Balanced',
            'criteria': {'fees': 0.33, 'latency': 0.33, 'reliability': 0.34}
        },
        {
            'name': 'Low Cost',
            'criteria': {'fees': 0.6, 'latency': 0.2, 'reliability': 0.2}
        },
        {
            'name': 'High Performance',
            'criteria': {'latency': 0.6, 'reliability': 0.3, 'fees': 0.1}
        },
        {
            'name': 'High Reliability',
            'criteria': {'reliability': 0.6, 'latency': 0.3, 'fees': 0.1}
        }
    ]
    
    for criteria_set in criteria_sets:
        print(f"\n{criteria_set['name']} Criteria:")
        rankings = registry.rank_exchanges(symbol, criteria_set['criteria'])
        
        if not rankings:
            print(f"  No exchanges available for {symbol}")
            continue
        
        for i, (exchange_id, score) in enumerate(rankings):
            print(f"  {i+1}. {exchange_id}: {score:.4f}")

def print_execution_parameters(registry):
    """Print optimized execution parameters for different scenarios."""
    print("\nExecution Parameters")
    print("=" * 50)
    
    scenarios = [
        {
            'name': 'Small Market Buy',
            'exchange': 'exchange_a',
            'order_type': 'market',
            'symbol': 'BTC/USD',
            'size_usd': 1000
        },
        {
            'name': 'Large Market Sell',
            'exchange': 'exchange_a',
            'order_type': 'market',
            'symbol': 'BTC/USD',
            'size_usd': 50000
        },
        {
            'name': 'Medium Limit Buy',
            'exchange': 'exchange_b',
            'order_type': 'limit',
            'symbol': 'ETH/USD',
            'size_usd': 10000
        }
    ]
    
    for scenario in scenarios:
        print(f"\n{scenario['name']}:")
        try:
            params = registry.get_execution_parameters(
                exchange_id=scenario['exchange'],
                order_type=scenario['order_type'],
                symbol=scenario['symbol'],
                size_usd=scenario['size_usd']
            )
            
            for key, value in params.items():
                print(f"  {key}: {value}")
        except Exception as e:
            print(f"  Error: {e}")

def print_exchange_metrics(profiler):
    """Print collected exchange metrics."""
    print("\nExchange Metrics")
    print("=" * 50)
    
    exchanges = ['exchange_a', 'exchange_b', 'exchange_c']
    
    for exchange_id in exchanges:
        metrics = profiler.get_exchange_metrics(exchange_id)
        
        if not metrics:
            print(f"\n{exchange_id}: No metrics available")
            continue
        
        print(f"\n{exchange_id}:")
        
        # API Performance
        if 'avg_api_latency_ms' in metrics:
            print(f"  API Latency: {metrics['avg_api_latency_ms']:.2f} ms")
        
        if 'api_error_rate' in metrics:
            print(f"  API Error Rate: {metrics['api_error_rate']*100:.2f}%")
        
        if 'api_reliability_pct' in metrics:
            print(f"  API Reliability: {metrics['api_reliability_pct']:.2f}%")
        
        # Order Execution
        if 'market_order_slippage_bps' in metrics:
            print(f"  Market Order Slippage: {metrics['market_order_slippage_bps']:.2f} bps")
        
        if 'limit_order_fill_rate' in metrics:
            print(f"  Limit Order Fill Rate: {metrics['limit_order_fill_rate']*100:.2f}%")
        
        # Market Quality
        if 'avg_spread_bps' in metrics:
            print(f"  Average Spread: {metrics['avg_spread_bps']:.2f} bps")
        
        if 'avg_liquidity_depth_usd' in metrics:
            print(f"  Average Liquidity Depth: ${metrics['avg_liquidity_depth_usd']:,.2f}")
        
        # Overall score
        if 'exchange_reliability_score' in metrics:
            print(f"  Reliability Score: {metrics['exchange_reliability_score']:.2f}/10")

def plot_exchange_metrics(profiler):
    """Plot collected exchange metrics."""
    # Convert profiler data to a DataFrame
    df = profiler.to_dataframe()
    
    if df.empty:
        print("No data available for plotting")
        return
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle('Exchange Performance Metrics', fontsize=16)
    
    # API Latency
    if 'avg_api_latency_ms' in df.columns:
        axes[0, 0].bar(df['exchange_id'], df['avg_api_latency_ms'])
        axes[0, 0].set_title('API Latency (ms)')
        axes[0, 0].set_ylabel('Milliseconds')
        axes[0, 0].grid(axis='y', linestyle='--', alpha=0.7)
    
    # API Reliability
    if 'api_reliability_pct' in df.columns:
        axes[0, 1].bar(df['exchange_id'], df['api_reliability_pct'])
        axes[0, 1].set_title('API Reliability (%)')
        axes[0, 1].set_ylabel('Percentage')
        axes[0, 1].set_ylim(90, 101)  # Start y-axis at 90% for better comparison
        axes[0, 1].grid(axis='y', linestyle='--', alpha=0.7)
    
    # Market Order Slippage
    if 'market_order_slippage_bps' in df.columns:
        axes[1, 0].bar(df['exchange_id'], df['market_order_slippage_bps'])
        axes[1, 0].set_title('Market Order Slippage (bps)')
        axes[1, 0].set_ylabel('Basis Points')
        axes[1, 0].grid(axis='y', linestyle='--', alpha=0.7)
    
    # Limit Order Fill Rate
    if 'limit_order_fill_rate' in df.columns:
        axes[1, 1].bar(df['exchange_id'], df['limit_order_fill_rate'] * 100)
        axes[1, 1].set_title('Limit Order Fill Rate (%)')
        axes[1, 1].set_ylabel('Percentage')
        axes[1, 1].set_ylim(60, 101)  # Start y-axis at 60% for better comparison
        axes[1, 1].grid(axis='y', linestyle='--', alpha=0.7)
    
    plt.tight_layout(rect=[0, 0, 1, 0.95])  # Adjust layout to make room for title
    plt.show()

def main():
    """Main function to demonstrate exchange profiling and optimization."""
    print("Exchange Profiling and Optimization Example")
    print("=" * 50)
    
    # Get registry and profiler instances
    registry = get_exchange_registry()
    profiler = get_exchange_profiler()
    
    # Set up test exchanges
    setup_test_exchanges(registry)
    
    # Simulate API calls for each exchange
    simulate_api_calls(profiler, 'exchange_a', count=200)
    simulate_api_calls(profiler, 'exchange_b', count=200)
    simulate_api_calls(profiler, 'exchange_c', count=200)
    
    # Simulate market orders for each exchange
    for exchange_id in ['exchange_a', 'exchange_b', 'exchange_c']:
        for symbol in ['BTC/USD', 'ETH/USD']:
            simulate_market_orders(profiler, exchange_id, symbol, count=50)
    
    # Simulate limit orders for each exchange
    for exchange_id in ['exchange_a', 'exchange_b', 'exchange_c']:
        for symbol in ['BTC/USD', 'ETH/USD']:
            simulate_limit_orders(profiler, exchange_id, symbol, count=50)
    
    # Simulate spread data for each exchange
    for exchange_id in ['exchange_a', 'exchange_b', 'exchange_c']:
        for symbol in ['BTC/USD', 'ETH/USD']:
            simulate_spread_data(profiler, exchange_id, symbol, count=100)
    
    # Let profiler process the data
    print("\nWaiting for profiler to process data...")
    time.sleep(2)
    
    # Print exchange rankings
    print_exchange_ranking(registry, 'BTC/USD')
    print_exchange_ranking(registry, 'ETH/USD')
    
    # Print execution parameters
    print_execution_parameters(registry)
    
    # Print exchange metrics
    print_exchange_metrics(profiler)
    
    # Plot exchange metrics
    try:
        plot_exchange_metrics(profiler)
    except Exception as e:
        print(f"Error plotting metrics: {e}")
    
    # Stop the profiler thread
    profiler.stop()
    
    print("\nExample complete!")

if __name__ == "__main__":
    main() 