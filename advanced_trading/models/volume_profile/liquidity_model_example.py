#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Example demonstrating the use of the LiquidityModel class for analyzing
market liquidity and optimizing trade execution.

This example shows how to:
1. Create a liquidity model from price and volume data
2. Calculate various liquidity metrics
3. Fit and visualize market impact models
4. Optimize trade execution to minimize market impact
5. Extract liquidity features for use in trading strategies
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path to allow imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import the LiquidityModel class
from models.volume_profile.liquidity_model import LiquidityModel

def generate_synthetic_data(n_samples=1000, with_trend=True, with_seasonality=True, with_noise=True):
    """
    Generate synthetic price and volume data for demonstration.
    
    Parameters
    ----------
    n_samples : int, default=1000
        Number of samples to generate.
    with_trend : bool, default=True
        Whether to include a trend component.
    with_seasonality : bool, default=True
        Whether to include a seasonality component.
    with_noise : bool, default=True
        Whether to include a noise component.
        
    Returns
    -------
    pd.DataFrame
        DataFrame with datetime index and price, volume, bid, ask, bid_volume, ask_volume columns.
    """
    # Generate dates
    start_date = datetime(2023, 1, 1)
    dates = [start_date + timedelta(hours=i) for i in range(n_samples)]
    
    # Generate price data
    price = 100.0  # Starting price
    prices = []
    
    # Trend component
    trend = np.linspace(0, 20, n_samples) if with_trend else np.zeros(n_samples)
    
    # Seasonality component (multiple cycles)
    seasonality1 = 5 * np.sin(np.linspace(0, 4 * np.pi, n_samples)) if with_seasonality else np.zeros(n_samples)
    seasonality2 = 2 * np.sin(np.linspace(0, 20 * np.pi, n_samples)) if with_seasonality else np.zeros(n_samples)
    
    # Noise component
    noise = np.random.normal(0, 1, n_samples) if with_noise else np.zeros(n_samples)
    
    # Combine components
    price_series = price + trend + seasonality1 + seasonality2 + noise
    
    # Generate volume data (higher at certain price levels)
    base_volume = 1000
    volume = np.random.gamma(shape=2, scale=500, size=n_samples)
    
    # Add volume spikes at certain price levels
    for i in range(n_samples):
        # Higher volume near round numbers
        price_mod = price_series[i] % 10
        if price_mod < 0.5 or price_mod > 9.5:
            volume[i] *= 3
        
        # Higher volume at local extremes
        if i > 5 and i < n_samples - 5:
            if (price_series[i] > price_series[i-5:i]).all() and (price_series[i] > price_series[i+1:i+6]).all():
                volume[i] *= 2
            if (price_series[i] < price_series[i-5:i]).all() and (price_series[i] < price_series[i+1:i+6]).all():
                volume[i] *= 2
    
    # Generate bid/ask data
    spread = np.random.gamma(shape=1, scale=0.05, size=n_samples)
    bid = price_series - spread / 2
    ask = price_series + spread / 2
    
    # Generate bid/ask volume data
    bid_volume = volume * (0.4 + 0.2 * np.random.random(n_samples))
    ask_volume = volume * (0.4 + 0.2 * np.random.random(n_samples))
    
    # Create DataFrame
    df = pd.DataFrame({
        'price': price_series,
        'volume': volume,
        'bid': bid,
        'ask': ask,
        'bid_volume': bid_volume,
        'ask_volume': ask_volume
    }, index=dates)
    
    return df

def generate_large_trade_events(data, n_events=10, min_volume_percentile=90):
    """
    Generate synthetic large trade events for market resilience calculation.
    
    Parameters
    ----------
    data : pd.DataFrame
        DataFrame with price and volume data.
    n_events : int, default=10
        Number of events to generate.
    min_volume_percentile : int, default=90
        Minimum volume percentile to consider as a large trade.
        
    Returns
    -------
    List[pd.Timestamp]
        List of timestamps for large trade events.
    """
    # Find high volume periods
    volume_threshold = np.percentile(data['volume'], min_volume_percentile)
    high_volume_indices = data[data['volume'] >= volume_threshold].index
    
    # Randomly select events
    if len(high_volume_indices) > n_events:
        event_indices = np.random.choice(high_volume_indices, size=n_events, replace=False)
    else:
        event_indices = high_volume_indices
    
    return list(event_indices)

def main():
    print("Liquidity Analysis Example")
    print("-------------------------")
    
    # Generate synthetic data
    print("\n1. Generating synthetic market data...")
    data = generate_synthetic_data(n_samples=1000)
    
    print(f"Generated data shape: {data.shape}")
    print(f"Price range: {data['price'].min():.2f} - {data['price'].max():.2f}")
    print(f"Average spread: {(data['ask'] - data['bid']).mean():.4f}")
    print(f"Average volume: {data['volume'].mean():.2f}")
    
    # Plot the data
    plt.figure(figsize=(12, 8))
    
    # Plot price and spread
    ax1 = plt.subplot(3, 1, 1)
    ax1.plot(data.index, data['price'], 'b-', label='Price')
    ax1.fill_between(data.index, data['bid'], data['ask'], color='blue', alpha=0.2, label='Spread')
    ax1.set_ylabel('Price')
    ax1.set_title('Synthetic Price Data with Bid-Ask Spread')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot volume
    ax2 = plt.subplot(3, 1, 2, sharex=ax1)
    ax2.bar(data.index, data['volume'], width=0.8, alpha=0.7, color='g', label='Total Volume')
    ax2.set_ylabel('Volume')
    ax2.set_title('Synthetic Volume Data')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Plot bid/ask volume
    ax3 = plt.subplot(3, 1, 3, sharex=ax1)
    ax3.bar(data.index, data['bid_volume'], width=0.8, alpha=0.7, color='g', label='Bid Volume')
    ax3.bar(data.index, data['ask_volume'], width=0.8, alpha=0.7, color='r', label='Ask Volume')
    ax3.set_xlabel('Time')
    ax3.set_ylabel('Volume')
    ax3.set_title('Synthetic Bid/Ask Volume Data')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    # Create liquidity model
    print("\n2. Creating liquidity model...")
    liquidity_model = LiquidityModel(
        price_data=data['price'],
        volume_data=data['volume'],
        bid_data=data['bid'],
        ask_data=data['ask'],
        bid_volume_data=data['bid_volume'],
        ask_volume_data=data['ask_volume'],
        time_index=data.index
    )
    
    # Calculate liquidity metrics
    print("\n3. Calculating liquidity metrics...")
    metrics = liquidity_model.calculate_liquidity_metrics(order_size=1000)
    
    print("Liquidity Metrics:")
    print(f"  - Spread: {metrics.spread:.4f}")
    print(f"  - Depth: {metrics.depth:.2f}")
    print(f"  - Volume Profile Concentration: {metrics.volume_profile_concentration:.4f}")
    print(f"  - Amihud Illiquidity: {metrics.amihud_illiquidity:.8f}")
    print(f"  - Slippage Estimate: {metrics.slippage_estimate:.4f}")
    print(f"  - Market Impact: {metrics.market_impact:.4f}")
    
    # Plot liquidity metrics
    liquidity_model.plot_liquidity_metrics(
        figsize=(12, 8),
        title='Liquidity Metrics Analysis'
    )
    
    # Calculate and plot Amihud illiquidity over time
    print("\n4. Analyzing Amihud illiquidity over time...")
    amihud = liquidity_model.calculate_amihud_illiquidity(window=20)
    
    plt.figure(figsize=(12, 6))
    plt.plot(amihud.index, amihud.values, 'r-')
    plt.xlabel('Time')
    plt.ylabel('Amihud Illiquidity')
    plt.title('Amihud Illiquidity Over Time')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
    
    # Generate order flow data for Kyle's lambda calculation
    print("\n5. Calculating Kyle's lambda...")
    
    # Calculate returns
    returns = data['price'].pct_change().fillna(0)
    
    # Generate synthetic order flow (signed volume)
    # Positive values represent buying pressure, negative values represent selling pressure
    order_flow = pd.Series(
        data['volume'] * np.sign(returns),
        index=data.index
    )
    
    # Calculate Kyle's lambda
    kyle_lambda = liquidity_model.calculate_kyle_lambda(returns, order_flow, window=20)
    
    plt.figure(figsize=(12, 6))
    plt.plot(kyle_lambda.index, kyle_lambda.values, 'g-')
    plt.xlabel('Time')
    plt.ylabel('Kyle\'s Lambda')
    plt.title('Kyle\'s Lambda Over Time')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
    
    # Fit market impact models
    print("\n6. Fitting market impact models...")
    
    # Generate synthetic order sizes and impacts for demonstration
    adv = data['volume'].mean()  # Average daily volume
    order_sizes = np.linspace(0.01 * adv, 0.5 * adv, 20)
    
    # Generate synthetic impacts with noise
    linear_impacts = 0.1 * order_sizes / adv + np.random.normal(0, 0.001, 20)
    sqrt_impacts = 0.1 * np.sqrt(order_sizes / adv) + np.random.normal(0, 0.001, 20)
    power_impacts = 0.1 * np.power(order_sizes / adv, 0.6) + np.random.normal(0, 0.001, 20)
    
    # Fit models
    linear_model, linear_params = liquidity_model.fit_market_impact_model(
        order_sizes, linear_impacts, model_type='linear'
    )
    print(f"Linear model parameter: alpha = {linear_params[0]:.6f}")
    
    sqrt_model, sqrt_params = liquidity_model.fit_market_impact_model(
        order_sizes, sqrt_impacts, model_type='square_root'
    )
    print(f"Square root model parameter: alpha = {sqrt_params[0]:.6f}")
    
    power_model, power_params = liquidity_model.fit_market_impact_model(
        order_sizes, power_impacts, model_type='power_law'
    )
    print(f"Power law model parameters: alpha = {power_params[0]:.6f}, beta = {power_params[1]:.6f}")
    
    # Plot market impact models
    plt.figure(figsize=(12, 6))
    
    # Plot data points
    plt.scatter(order_sizes, linear_impacts, color='blue', label='Linear Data')
    plt.scatter(order_sizes, sqrt_impacts, color='green', label='Square Root Data')
    plt.scatter(order_sizes, power_impacts, color='red', label='Power Law Data')
    
    # Plot fitted models
    x = np.linspace(0, max(order_sizes), 100)
    plt.plot(x, linear_model(x, *linear_params), 'b-', label='Linear Model')
    plt.plot(x, sqrt_model(x, *sqrt_params), 'g-', label='Square Root Model')
    plt.plot(x, power_model(x, *power_params), 'r-', label='Power Law Model')
    
    plt.xlabel('Order Size')
    plt.ylabel('Market Impact')
    plt.title('Market Impact Models Comparison')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
    
    # Optimize execution
    print("\n7. Optimizing execution to minimize market impact...")
    
    # Use square root model for optimization
    liquidity_model.fit_market_impact_model(order_sizes, sqrt_impacts, model_type='square_root')
    
    # Plot market impact model
    liquidity_model.plot_market_impact_model(
        max_order_size=0.5 * adv,
        figsize=(10, 6),
        title='Square Root Market Impact Model'
    )
    
    # Calculate optimal execution for different order sizes
    total_sizes = [0.1 * adv, 0.2 * adv, 0.5 * adv]
    max_impact = 0.001  # 0.1% maximum impact per chunk
    
    for total_size in total_sizes:
        chunks, chunk_size, total_impact = liquidity_model.estimate_optimal_execution_size(
            total_size=total_size,
            max_impact=max_impact
        )
        
        print(f"Order size: {total_size:.2f}")
        print(f"  - Optimal execution: {chunks} chunks of {chunk_size:.2f} each")
        print(f"  - Estimated total impact: {total_impact:.4f}")
        
        # Plot optimal execution
        liquidity_model.plot_optimal_execution(
            total_size=total_size,
            max_impact=max_impact,
            figsize=(12, 6),
            title=f'Optimal Execution for Order Size {total_size:.2f}'
        )
    
    # Calculate market resilience
    print("\n8. Calculating market resilience...")
    
    # Generate synthetic large trade events
    events = generate_large_trade_events(data, n_events=20)
    
    # Calculate market resilience
    resilience = liquidity_model.calculate_market_resilience(
        price_data=data['price'],
        event_times=events,
        window_before=10,
        window_after=30
    )
    
    if resilience is not None:
        print(f"Average market resilience (recovery time): {resilience:.2f} periods")
    else:
        print("Could not calculate market resilience (no significant events found)")
    
    # Extract liquidity features for machine learning
    print("\n9. Extracting liquidity features for machine learning...")
    
    features = liquidity_model.get_liquidity_features()
    
    print("Liquidity Features:")
    for key, value in features.items():
        print(f"  - {key}: {value:.6f}")
    
    # Demonstrate using liquidity metrics in a trading strategy
    print("\n10. Using liquidity metrics in a trading strategy...")
    
    def liquidity_based_strategy(price, spread, depth, amihud_illiquidity, order_size=1000):
        """Simple strategy based on liquidity metrics."""
        # Calculate slippage estimate
        slippage = spread * (order_size / depth)
        
        # Calculate liquidity score (lower is better)
        liquidity_score = slippage + amihud_illiquidity * 10000
        
        # Generate signals based on liquidity
        if liquidity_score < 0.001:
            return 1  # Good liquidity, buy signal
        elif liquidity_score > 0.005:
            return -1  # Poor liquidity, sell signal
        else:
            return 0  # Neutral
    
    # Calculate rolling liquidity metrics
    window = 20
    rolling_spread = (data['ask'] - data['bid']).rolling(window=window).mean()
    rolling_depth = (data['bid_volume'] + data['ask_volume']).rolling(window=window).mean()
    rolling_amihud = amihud.rolling(window=window).mean()
    
    # Apply strategy
    signals = []
    for i in range(window, len(data)):
        signal = liquidity_based_strategy(
            price=data['price'].iloc[i],
            spread=rolling_spread.iloc[i],
            depth=rolling_depth.iloc[i],
            amihud_illiquidity=rolling_amihud.iloc[i]
        )
        signals.append((data.index[i], data['price'].iloc[i], signal))
    
    # Plot signals
    plt.figure(figsize=(12, 6))
    plt.plot(data.index[-200:], data['price'].iloc[-200:], 'b-')
    
    # Plot signals for the last 200 periods
    for date, price, signal in signals[-200:]:
        if signal == 1:  # Buy
            plt.scatter(date, price, color='g', marker='^', s=100)
        elif signal == -1:  # Sell
            plt.scatter(date, price, color='r', marker='v', s=100)
    
    plt.xlabel('Time')
    plt.ylabel('Price')
    plt.title('Trading Signals Based on Liquidity Metrics')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
    
    print("\nLiquidity Analysis Example completed successfully!")

if __name__ == "__main__":
    main() 