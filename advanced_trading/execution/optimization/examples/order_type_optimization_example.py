"""
Order Type Optimizer Example

This example demonstrates how to use the Order Type Optimizer to select
optimal order types and parameters based on market conditions.
"""

import time
import random
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Any
from datetime import datetime

from advanced_trading.execution.optimization import (
    # Exchange registry and profiler
    get_exchange_registry, get_exchange_profiler,
    ExchangeCapabilities, ExchangePerformance,
    
    # Order type optimizer
    get_order_type_optimizer, OrderTypeOptimizer,
    MarketCondition, OrderTypeParameters, ExecutionPreferences,
    OrderTypeOptimizationRequest, OrderTypeRecommendation
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
    
    # Record some symbol-specific metrics
    profiler = get_exchange_profiler()
    
    # BTC/USD metrics
    for exchange in ['exchange_a', 'exchange_b']:
        if exchange == 'exchange_a':
            spread_bps = 6.0
            liquidity = 5000000.0
            volume_profile = 0.8
            price_trend = 0.2  # Slight uptrend
            volatility = 0.015  # 1.5% volatility
        else:  # exchange_b
            spread_bps = 5.0
            liquidity = 8000000.0
            volume_profile = 0.9
            price_trend = 0.15  # Slight uptrend
            volatility = 0.018  # 1.8% volatility
        
        profiler.record_spread_data(
            exchange_id=exchange,
            symbol='BTC/USD',
            spread_bps=spread_bps,
            liquidity_depth_usd=liquidity
        )
        
        # We'd normally do this through market data, but for this example
        # we'll use a hack to directly set these metrics
        symbol_metrics = profiler.get_symbol_metrics(exchange, 'BTC/USD')
        if not symbol_metrics:
            symbol_metrics = {}
        
        symbol_metrics['volume_profile'] = volume_profile
        symbol_metrics['price_trend'] = price_trend
        symbol_metrics['price_volatility'] = volatility
        
        # Force update the metrics
        profiler._metrics_by_exchange[exchange]['symbol_metrics']['BTC/USD'] = symbol_metrics
    
    # ETH/USD metrics
    for exchange in ['exchange_a', 'exchange_b']:
        if exchange == 'exchange_a':
            spread_bps = 8.0
            liquidity = 3000000.0
            volume_profile = 0.7
            price_trend = -0.1  # Slight downtrend
            volatility = 0.025  # 2.5% volatility
        else:  # exchange_b
            spread_bps = 7.0
            liquidity = 4000000.0
            volume_profile = 0.75
            price_trend = -0.05  # Slight downtrend
            volatility = 0.028  # 2.8% volatility
        
        profiler.record_spread_data(
            exchange_id=exchange,
            symbol='ETH/USD',
            spread_bps=spread_bps,
            liquidity_depth_usd=liquidity
        )
        
        # We'd normally do this through market data, but for this example
        # we'll use a hack to directly set these metrics
        symbol_metrics = profiler.get_symbol_metrics(exchange, 'ETH/USD')
        if not symbol_metrics:
            symbol_metrics = {}
        
        symbol_metrics['volume_profile'] = volume_profile
        symbol_metrics['price_trend'] = price_trend
        symbol_metrics['price_volatility'] = volatility
        
        # Force update the metrics
        profiler._metrics_by_exchange[exchange]['symbol_metrics']['ETH/USD'] = symbol_metrics
    
    # Let profiler update the registry
    time.sleep(1)
    profiler._update_registry()
    
    print("Test exchanges setup complete")

def test_different_urgency_levels():
    """Test order type optimization with different urgency levels."""
    print("\nTesting different urgency levels...")
    
    # Get optimizer instance
    optimizer = get_order_type_optimizer()
    
    # Test parameters
    base_params = {
        'exchange_id': 'exchange_a',
        'symbol': 'BTC/USD',
        'side': 'buy',
        'size': 1.0,
        'size_usd': 50000.0,
        'reference_price': 50000.0
    }
    
    # Try different urgency levels
    urgency_levels = [
        ('Very Low', 0.1),
        ('Low', 0.3),
        ('Medium', 0.5),
        ('High', 0.7),
        ('Very High', 0.9)
    ]
    
    results = []
    
    for urgency_name, urgency in urgency_levels:
        preferences = ExecutionPreferences(
            urgency=urgency,
            cost_sensitivity=0.5,
            impact_sensitivity=0.5,
            completion_priority=0.5
        )
        
        request = OrderTypeOptimizationRequest(
            **base_params,
            preferences=preferences
        )
        
        recommendation = optimizer.recommend_order_type(request)
        
        print(f"\n{urgency_name} Urgency ({urgency}):")
        print(f"  Recommended Order Type: {recommendation.order_type}")
        print(f"  Parameters: {vars(recommendation.parameters)}")
        print(f"  Expected Fill Probability: {recommendation.expected_fill_probability:.0%}")
        print(f"  Expected Cost: {recommendation.expected_cost_bps:.1f} bps")
        print(f"  Expected Market Impact: {recommendation.expected_market_impact_bps:.1f} bps")
        print(f"  Expected Time to Fill: {recommendation.expected_time_to_fill_ms:.0f} ms")
        print(f"  Reasoning: {recommendation.reasoning}")
        
        if recommendation.alternatives:
            print("  Alternatives:")
            for i, (alt_type, alt_params, alt_score) in enumerate(recommendation.alternatives):
                print(f"    {i+1}. {alt_type} (score: {alt_score:.2f})")
        
        results.append({
            'urgency': urgency_name,
            'urgency_value': urgency,
            'order_type': recommendation.order_type,
            'parameters': recommendation.parameters,
            'fill_probability': recommendation.expected_fill_probability,
            'cost_bps': recommendation.expected_cost_bps,
            'market_impact_bps': recommendation.expected_market_impact_bps,
            'time_to_fill_ms': recommendation.expected_time_to_fill_ms
        })
    
    return results

def test_different_market_conditions():
    """Test order type optimization with different market conditions."""
    print("\nTesting different market conditions...")
    
    # Get optimizer instance
    optimizer = get_order_type_optimizer()
    
    # Test parameters
    base_params = {
        'exchange_id': 'exchange_a',
        'symbol': 'BTC/USD',
        'side': 'buy',
        'size': 1.0,
        'size_usd': 50000.0,
        'reference_price': 50000.0,
        'preferences': ExecutionPreferences(
            urgency=0.5,  # Medium urgency
            cost_sensitivity=0.5,
            impact_sensitivity=0.5,
            completion_priority=0.5
        )
    }
    
    # Define different market conditions
    market_conditions = [
        ('Calm Market', MarketCondition(
            volatility=0.01,
            spread_bps=5.0,
            liquidity_depth_usd=10000000.0,
            price_trend=0.0,
            volume_profile=0.5,
            is_high_volatility=False,
            is_tight_spread=True,
            is_deep_liquidity=True
        )),
        ('Volatile Market', MarketCondition(
            volatility=0.04,
            spread_bps=15.0,
            liquidity_depth_usd=2000000.0,
            price_trend=0.0,
            volume_profile=0.8,
            is_high_volatility=True,
            is_tight_spread=False,
            is_deep_liquidity=True
        )),
        ('Thin Liquidity', MarketCondition(
            volatility=0.02,
            spread_bps=20.0,
            liquidity_depth_usd=500000.0,
            price_trend=0.0,
            volume_profile=0.4,
            is_high_volatility=True,
            is_tight_spread=False,
            is_deep_liquidity=False
        )),
        ('Strong Uptrend', MarketCondition(
            volatility=0.02,
            spread_bps=8.0,
            liquidity_depth_usd=5000000.0,
            price_trend=0.8,
            volume_profile=0.7,
            is_high_volatility=True,
            is_tight_spread=True,
            is_deep_liquidity=True
        )),
        ('Strong Downtrend', MarketCondition(
            volatility=0.025,
            spread_bps=10.0,
            liquidity_depth_usd=3000000.0,
            price_trend=-0.8,
            volume_profile=0.6,
            is_high_volatility=True,
            is_tight_spread=False,
            is_deep_liquidity=True
        ))
    ]
    
    results = []
    
    for condition_name, market_condition in market_conditions:
        request = OrderTypeOptimizationRequest(
            **base_params,
            market_condition=market_condition
        )
        
        recommendation = optimizer.recommend_order_type(request)
        
        print(f"\n{condition_name}:")
        print(f"  Recommended Order Type: {recommendation.order_type}")
        print(f"  Parameters: {vars(recommendation.parameters)}")
        print(f"  Expected Fill Probability: {recommendation.expected_fill_probability:.0%}")
        print(f"  Expected Cost: {recommendation.expected_cost_bps:.1f} bps")
        print(f"  Expected Market Impact: {recommendation.expected_market_impact_bps:.1f} bps")
        print(f"  Expected Time to Fill: {recommendation.expected_time_to_fill_ms:.0f} ms")
        print(f"  Reasoning: {recommendation.reasoning}")
        
        results.append({
            'condition': condition_name,
            'order_type': recommendation.order_type,
            'parameters': recommendation.parameters,
            'fill_probability': recommendation.expected_fill_probability,
            'cost_bps': recommendation.expected_cost_bps,
            'market_impact_bps': recommendation.expected_market_impact_bps,
            'time_to_fill_ms': recommendation.expected_time_to_fill_ms
        })
    
    return results

def test_different_order_sizes():
    """Test order type optimization with different order sizes."""
    print("\nTesting different order sizes...")
    
    # Get optimizer instance
    optimizer = get_order_type_optimizer()
    
    # Test parameters
    base_params = {
        'exchange_id': 'exchange_a',
        'symbol': 'BTC/USD',
        'side': 'buy',
        'reference_price': 50000.0,
        'preferences': ExecutionPreferences(
            urgency=0.5,  # Medium urgency
            cost_sensitivity=0.5,
            impact_sensitivity=0.5,
            completion_priority=0.5
        )
    }
    
    # Test different sizes
    sizes = [
        ('Micro', 0.01, 500.0),
        ('Small', 0.1, 5000.0),
        ('Medium', 1.0, 50000.0),
        ('Large', 5.0, 250000.0),
        ('Very Large', 20.0, 1000000.0)
    ]
    
    results = []
    
    for size_name, size, size_usd in sizes:
        request = OrderTypeOptimizationRequest(
            **base_params,
            size=size,
            size_usd=size_usd
        )
        
        recommendation = optimizer.recommend_order_type(request)
        
        print(f"\n{size_name} Order (${size_usd:,.0f}):")
        print(f"  Recommended Order Type: {recommendation.order_type}")
        print(f"  Parameters: {vars(recommendation.parameters)}")
        print(f"  Expected Fill Probability: {recommendation.expected_fill_probability:.0%}")
        print(f"  Expected Cost: {recommendation.expected_cost_bps:.1f} bps")
        print(f"  Expected Market Impact: {recommendation.expected_market_impact_bps:.1f} bps")
        print(f"  Expected Implementation Shortfall: {recommendation.expected_implementation_shortfall_bps:.1f} bps")
        
        results.append({
            'size_name': size_name,
            'size_usd': size_usd,
            'order_type': recommendation.order_type,
            'parameters': recommendation.parameters,
            'fill_probability': recommendation.expected_fill_probability,
            'cost_bps': recommendation.expected_cost_bps,
            'market_impact_bps': recommendation.expected_market_impact_bps,
            'implementation_shortfall_bps': recommendation.expected_implementation_shortfall_bps
        })
    
    return results

def test_different_preferences():
    """Test order type optimization with different execution preferences."""
    print("\nTesting different execution preferences...")
    
    # Get optimizer instance
    optimizer = get_order_type_optimizer()
    
    # Test parameters
    base_params = {
        'exchange_id': 'exchange_a',
        'symbol': 'BTC/USD',
        'side': 'buy',
        'size': 1.0,
        'size_usd': 50000.0,
        'reference_price': 50000.0
    }
    
    # Define different preference profiles
    preference_profiles = [
        ('Cost Sensitive', ExecutionPreferences(
            urgency=0.3,
            cost_sensitivity=0.9,
            impact_sensitivity=0.5,
            completion_priority=0.3,
            maximize_maker_orders=True
        )),
        ('Execution Speed', ExecutionPreferences(
            urgency=0.8,
            cost_sensitivity=0.2,
            impact_sensitivity=0.3,
            completion_priority=0.7,
            minimize_time=True
        )),
        ('Minimize Impact', ExecutionPreferences(
            urgency=0.4,
            cost_sensitivity=0.5,
            impact_sensitivity=0.9,
            completion_priority=0.4,
            maximize_maker_orders=True
        )),
        ('Guaranteed Fill', ExecutionPreferences(
            urgency=0.6,
            cost_sensitivity=0.4,
            impact_sensitivity=0.4,
            completion_priority=0.9
        )),
        ('Opportunistic', ExecutionPreferences(
            urgency=0.4,
            cost_sensitivity=0.7,
            impact_sensitivity=0.6,
            completion_priority=0.3,
            aggressive_in_favorable_trend=True
        ))
    ]
    
    results = []
    
    for profile_name, preferences in preference_profiles:
        request = OrderTypeOptimizationRequest(
            **base_params,
            preferences=preferences
        )
        
        recommendation = optimizer.recommend_order_type(request)
        
        print(f"\n{profile_name}:")
        print(f"  Recommended Order Type: {recommendation.order_type}")
        print(f"  Parameters: {vars(recommendation.parameters)}")
        print(f"  Expected Fill Probability: {recommendation.expected_fill_probability:.0%}")
        print(f"  Expected Cost: {recommendation.expected_cost_bps:.1f} bps")
        print(f"  Expected Market Impact: {recommendation.expected_market_impact_bps:.1f} bps")
        print(f"  Expected Time to Fill: {recommendation.expected_time_to_fill_ms:.0f} ms")
        
        results.append({
            'profile': profile_name,
            'preferences': preferences,
            'order_type': recommendation.order_type,
            'parameters': recommendation.parameters,
            'fill_probability': recommendation.expected_fill_probability,
            'cost_bps': recommendation.expected_cost_bps,
            'market_impact_bps': recommendation.expected_market_impact_bps,
            'time_to_fill_ms': recommendation.expected_time_to_fill_ms
        })
    
    return results

def plot_urgency_results(urgency_results):
    """Plot the results of testing different urgency levels."""
    print("\nPlotting urgency results...")
    
    # Extract data
    urgency_levels = [result['urgency'] for result in urgency_results]
    fill_probs = [result['fill_probability'] * 100 for result in urgency_results]
    costs = [result['cost_bps'] for result in urgency_results]
    impacts = [result['market_impact_bps'] for result in urgency_results]
    
    # Convert time to fill to a readable scale (seconds)
    times = [min(60, result['time_to_fill_ms'] / 1000) for result in urgency_results]
    
    # Create figure with subplots
    fig, axs = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle('Impact of Urgency on Execution Parameters', fontsize=16)
    
    # Fill probability
    axs[0, 0].bar(urgency_levels, fill_probs, color='skyblue')
    axs[0, 0].set_title('Fill Probability')
    axs[0, 0].set_ylabel('Probability (%)')
    axs[0, 0].set_ylim(0, 105)
    
    # Cost
    axs[0, 1].bar(urgency_levels, costs, color='salmon')
    axs[0, 1].set_title('Expected Cost')
    axs[0, 1].set_ylabel('Cost (bps)')
    
    # Market impact
    axs[1, 0].bar(urgency_levels, impacts, color='lightgreen')
    axs[1, 0].set_title('Market Impact')
    axs[1, 0].set_ylabel('Impact (bps)')
    
    # Time to fill
    axs[1, 1].bar(urgency_levels, times, color='purple')
    axs[1, 1].set_title('Time to Fill')
    axs[1, 1].set_ylabel('Time (seconds)')
    
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.show()

def plot_size_results(size_results):
    """Plot the results of testing different order sizes."""
    print("\nPlotting order size results...")
    
    # Extract data
    size_names = [result['size_name'] for result in size_results]
    costs = [result['cost_bps'] for result in size_results]
    impacts = [result['market_impact_bps'] for result in size_results]
    shortfalls = [result['implementation_shortfall_bps'] for result in size_results]
    
    # Create figure
    plt.figure(figsize=(10, 6))
    
    # Set width of bars
    barWidth = 0.25
    
    # Set positions of the bars on X axis
    r1 = np.arange(len(size_names))
    r2 = [x + barWidth for x in r1]
    r3 = [x + barWidth for x in r2]
    
    # Create bars
    plt.bar(r1, costs, width=barWidth, label='Trading Cost (bps)', color='skyblue')
    plt.bar(r2, impacts, width=barWidth, label='Market Impact (bps)', color='salmon')
    plt.bar(r3, shortfalls, width=barWidth, label='Implementation Shortfall (bps)', color='lightgreen')
    
    # Add labels and title
    plt.xlabel('Order Size')
    plt.ylabel('Basis Points')
    plt.title('Impact of Order Size on Execution Costs')
    plt.xticks([r + barWidth for r in range(len(size_names))], size_names)
    plt.legend()
    
    plt.tight_layout()
    plt.show()

def main():
    """Main function to demonstrate order type optimization."""
    print("Order Type Optimizer Example")
    print("===========================\n")
    
    # Set up test exchanges
    setup_test_exchanges()
    
    # Test with different urgency levels
    urgency_results = test_different_urgency_levels()
    
    # Test with different market conditions
    market_condition_results = test_different_market_conditions()
    
    # Test with different order sizes
    size_results = test_different_order_sizes()
    
    # Test with different execution preferences
    preference_results = test_different_preferences()
    
    # Plot results
    try:
        plot_urgency_results(urgency_results)
        plot_size_results(size_results)
    except Exception as e:
        print(f"Error plotting results: {e}")
    
    print("\nExample complete!")

if __name__ == "__main__":
    main() 