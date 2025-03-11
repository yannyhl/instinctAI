"""
Basic Usage Example for Market Microstructure Analysis

This example demonstrates how to use the market microstructure analysis
components to analyze order book data and execute trades.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Any
from datetime import datetime, timedelta

from advanced_trading.analysis.market_microstructure import (
    OrderBookAnalyzer, OrderFlowAnalyzer, LiquidityProfiler
)

def create_sample_order_book(mid_price: float = 1000.0, depth: int = 10,
                           bid_skew: float = 0.0, ask_skew: float = 0.0) -> Dict[str, Any]:
    """
    Create a sample order book for testing.
    
    Args:
        mid_price: Mid price
        depth: Number of levels to generate
        bid_skew: Positive values increase bid volume, negative decrease
        ask_skew: Positive values increase ask volume, negative decrease
        
    Returns:
        Dict with bids and asks
    """
    # Calculate spreads
    spread_pct = 0.0005  # 5 basis points
    spread = mid_price * spread_pct
    
    best_bid = mid_price - spread / 2
    best_ask = mid_price + spread / 2
    
    # Create bids (price descending)
    bids = []
    for i in range(depth):
        price = best_bid - (i * mid_price * 0.0001)  # Each level 1bp away
        # Base volume decreases with distance from mid
        base_volume = np.random.normal(1.0, 0.2) * (1.0 / (1.0 + i * 0.2))
        # Apply skew
        volume = base_volume * (1.0 + bid_skew * (1.0 - i * 0.1))
        bids.append([price, max(0.001, volume)])
    
    # Create asks (price ascending)
    asks = []
    for i in range(depth):
        price = best_ask + (i * mid_price * 0.0001)  # Each level 1bp away
        # Base volume decreases with distance from mid
        base_volume = np.random.normal(1.0, 0.2) * (1.0 / (1.0 + i * 0.2))
        # Apply skew
        volume = base_volume * (1.0 + ask_skew * (1.0 - i * 0.1))
        asks.append([price, max(0.001, volume)])
    
    return {
        'bids': bids,
        'asks': asks,
        'timestamp': int(time.time() * 1000)
    }

def create_sample_trade(side: str = 'buy', price: float = 1000.0, 
                       size: float = 1.0) -> Dict[str, Any]:
    """
    Create a sample trade for testing.
    
    Args:
        side: 'buy' or 'sell'
        price: Trade price
        size: Trade size
        
    Returns:
        Dict with trade data
    """
    return {
        'price': price,
        'amount': size,
        'side': side,
        'timestamp': int(time.time() * 1000)
    }

def main():
    # Initialize analyzers
    print("Initializing market microstructure analyzers...")
    order_book_analyzer = OrderBookAnalyzer(
        update_frequency_ms=100,
        max_book_depth=10,
        history_window=100
    )
    
    order_flow_analyzer = OrderFlowAnalyzer(
        history_window=1000,
        time_window_seconds=300,
        large_trade_threshold=0.95
    )
    
    liquidity_profiler = LiquidityProfiler(
        history_window=1000,
        depth_levels=10,
        impact_size_tiers=[0.001, 0.005, 0.01, 0.05, 0.1]
    )
    
    # Define symbol
    symbol = 'BTC/USD'
    
    # Simulate a series of order book updates and trades
    print(f"\nSimulating order book updates and trades for {symbol}...")
    
    # Starting mid price
    mid_price = 50000.0
    
    # Simulate 100 updates
    for i in range(100):
        # Update mid price with small random changes
        mid_price *= (1.0 + np.random.normal(0, 0.0001))
        
        # Create order book with different skews
        bid_skew = np.sin(i / 10) * 0.5  # Oscillating bid skew
        ask_skew = np.cos(i / 10) * 0.5  # Oscillating ask skew
        
        order_book = create_sample_order_book(
            mid_price=mid_price,
            depth=10,
            bid_skew=bid_skew,
            ask_skew=ask_skew
        )
        
        # Process order book
        ob_results = order_book_analyzer.process_order_book(symbol, order_book)
        lp_results = liquidity_profiler.process_order_book(symbol, order_book)
        
        # Every 5 updates, create a trade
        if i % 5 == 0:
            # Randomize trade parameters
            side = 'buy' if np.random.random() > 0.5 else 'sell'
            price = mid_price * (1.0 + np.random.normal(0, 0.0002))
            size = np.random.lognormal(-1, 1)  # Random size with small bias to small trades
            
            trade = create_sample_trade(side=side, price=price, size=size)
            
            # Process trade
            of_results = order_flow_analyzer.process_trade(symbol, trade)
            liquidity_profiler.process_trade(symbol, trade)
            
            print(f"Trade {i//5 + 1}: {side.upper()} {size:.4f} @ ${price:.2f}")
            
            if of_results and 'signals' in of_results and of_results['signals']:
                for signal_name, signal in of_results['signals'].items():
                    if signal_name != 'overall_bias':
                        continue
                    print(f"  Signal: {signal_name}: {signal['direction']} "
                         f"(confidence: {signal['confidence']:.2f})")
        
        # Every 20 updates, print current metrics
        if i % 20 == 0:
            print(f"\nOrder Book Update {i+1} - Mid Price: ${mid_price:.2f}")
            
            # Print order book metrics
            if 'metrics' in ob_results:
                metrics = ob_results['metrics']
                print(f"  Spread: ${metrics['spread_absolute']:.2f} "
                     f"({metrics['spread_bps']:.1f} bps)")
                print(f"  Imbalance: {metrics['weighted_imbalance']:.2f}")
                print(f"  Book Pressure: {metrics.get('price_pressure', 0):.2f}")
                
                if 'predictions' in ob_results:
                    pred = ob_results['predictions']
                    print(f"  Price Prediction: {pred.get('direction', 'neutral')} "
                         f"(confidence: {pred.get('confidence', 0):.2f})")
            
            # Print liquidity metrics
            if lp_results:
                print(f"  Liquidity Score: {lp_results['liquidity_score']:.1f}/10")
                print(f"  Total Depth: {lp_results['total_depth']['total']:.1f}")
                
                # Show impact estimates for medium size
                if 'impact_estimates' in lp_results and '0.01' in lp_results['impact_estimates']:
                    impact = lp_results['impact_estimates']['0.01']
                    print(f"  Est. Impact (1% size): {impact['avg_impact_bps']:.1f} bps")
    
    # After simulation, analyze overall results
    print("\n" + "="*50)
    print("Simulation Complete - Summary Analysis")
    print("="*50)
    
    # Get order book analysis summary
    print("\nOrder Book Analysis:")
    book_metrics = order_book_analyzer.book_metrics.get(symbol, {})
    if book_metrics:
        print(f"  Final Spread: ${book_metrics['spread_absolute']:.2f} "
             f"({book_metrics['spread_bps']:.1f} bps)")
        print(f"  Final Imbalance: {book_metrics['weighted_imbalance']:.2f}")
        print(f"  Book Liquidity: {book_metrics.get('liquidity_score', 0):.1f}")
        
    # Get order flow analysis summary
    print("\nOrder Flow Analysis:")
    flow_metrics = order_flow_analyzer.metrics.get(symbol, {})
    if flow_metrics:
        print(f"  Total Volume: {flow_metrics['total_volume']:.2f}")
        print(f"  Volume Imbalance: {flow_metrics['volume_imbalance']:.2f}")
        print(f"  Trade Imbalance: {flow_metrics['trade_imbalance']:.2f}")
        print(f"  Avg Trade Size: {flow_metrics['avg_trade_size']:.2f}")
        
    # Get liquidity profile summary
    print("\nLiquidity Profile:")
    profile = liquidity_profiler.get_current_profile(symbol)
    if profile:
        print(f"  Liquidity Score: {profile['liquidity_score']:.1f}/10")
        print(f"  Effective Spread: {profile.get('effective_spread', 0):.2f}")
        print(f"  Total Depth: {profile['total_depth']['total']:.1f}")
        
        # Print liquidity score components
        components = liquidity_profiler.get_liquidity_score_components(symbol)
        if components:
            print("\nLiquidity Score Components:")
            for name, component in components.items():
                if name != 'total_score':
                    print(f"  {name}: {component['value']:.1f} "
                         f"(weight: {component.get('weight', 0):.1f})")
    
    print("\nExample complete!")

if __name__ == "__main__":
    main() 