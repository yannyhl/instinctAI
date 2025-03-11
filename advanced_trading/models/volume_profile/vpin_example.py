#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Example demonstrating the use of the VPIN (Volume-synchronized Probability of Informed Trading)
module for analyzing order flow toxicity in financial markets.

This example shows how to:
1. Calculate VPIN from market data
2. Detect toxic events based on VPIN
3. Visualize VPIN and related metrics
4. Extract VPIN features for use in trading strategies
5. Compare different trade classification methods
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

# Import the VPIN class
from models.volume_profile.vpin import VPIN, VPINCalculator

def generate_synthetic_data(n_samples=5000, with_flash_crash=True, with_informed_trading=True):
    """
    Generate synthetic market data for demonstration.
    
    Parameters
    ----------
    n_samples : int, default=5000
        Number of samples to generate.
    with_flash_crash : bool, default=True
        Whether to include a flash crash event.
    with_informed_trading : bool, default=True
        Whether to include periods of informed trading.
        
    Returns
    -------
    pd.DataFrame
        DataFrame with synthetic market data.
    """
    # Generate dates
    start_date = datetime(2023, 1, 1, 9, 30)  # Market open at 9:30 AM
    dates = [start_date + timedelta(minutes=i) for i in range(n_samples)]
    
    # Generate price data
    price = 100.0  # Starting price
    prices = []
    
    # Add trend, seasonality, and noise components
    trend = 0.01 * np.cumsum(np.random.normal(0, 1, n_samples))  # Random walk
    seasonality = 2 * np.sin(np.linspace(0, 10 * np.pi, n_samples))  # Sine wave
    noise = np.random.normal(0, 0.5, n_samples)  # Gaussian noise
    
    # Combine components
    base_price = price + np.cumsum(trend) + seasonality + noise
    
    # Add flash crash if requested
    if with_flash_crash:
        # Flash crash around 1/3 of the way through
        crash_start = n_samples // 3
        crash_duration = n_samples // 50  # 2% of the data
        
        # Create crash pattern: sharp decline followed by recovery
        crash_pattern = np.concatenate([
            np.linspace(0, -15, crash_duration // 2),  # Sharp decline
            np.linspace(-15, -5, crash_duration // 2)   # Partial recovery
        ])
        
        # Apply crash pattern
        base_price[crash_start:crash_start + crash_duration] += crash_pattern
    
    # Add informed trading periods if requested
    if with_informed_trading:
        # Add several periods of informed trading
        for i in range(3):
            # Random start point
            informed_start = np.random.randint(n_samples // 10, n_samples - n_samples // 5)
            informed_duration = n_samples // 30  # 3.33% of the data
            
            # Create informed trading pattern: gradual decline before a significant move
            if np.random.random() > 0.5:
                # Upward move
                informed_pattern = np.concatenate([
                    np.linspace(0, -1, informed_duration // 2),  # Slight decline (accumulation)
                    np.linspace(-1, 5, informed_duration // 2)   # Sharp rise
                ])
            else:
                # Downward move
                informed_pattern = np.concatenate([
                    np.linspace(0, 1, informed_duration // 2),   # Slight rise (distribution)
                    np.linspace(1, -5, informed_duration // 2)   # Sharp decline
                ])
            
            # Apply informed trading pattern
            base_price[informed_start:informed_start + informed_duration] += informed_pattern
    
    # Ensure price doesn't go negative
    prices = np.maximum(base_price, 0.01)
    
    # Generate volume data
    base_volume = 1000 + 500 * np.random.gamma(shape=1, scale=1, size=n_samples)
    
    # Add volume spikes during high volatility
    price_changes = np.abs(np.diff(prices, prepend=prices[0]))
    volume_multiplier = 1 + 5 * (price_changes / np.std(price_changes))
    volumes = base_volume * volume_multiplier
    
    # Generate bid/ask data
    spreads = 0.02 + 0.03 * np.random.gamma(shape=1, scale=1, size=n_samples)
    # Wider spreads during high volatility
    spreads = spreads * (1 + 2 * (price_changes / np.std(price_changes)))
    
    bid_prices = prices - spreads / 2
    ask_prices = prices + spreads / 2
    
    # Create DataFrame
    df = pd.DataFrame({
        'price': prices,
        'volume': volumes,
        'bid': bid_prices,
        'ask': ask_prices
    }, index=dates)
    
    return df

def main():
    print("VPIN (Volume-synchronized Probability of Informed Trading) Example")
    print("---------------------------------------------------------------")
    
    # Generate synthetic data
    print("\n1. Generating synthetic market data...")
    data = generate_synthetic_data(n_samples=5000)
    
    print(f"Generated data shape: {data.shape}")
    print(f"Date range: {data.index[0]} to {data.index[-1]}")
    
    # Plot the data
    plt.figure(figsize=(12, 8))
    
    # Plot price
    ax1 = plt.subplot(2, 1, 1)
    ax1.plot(data.index, data['price'], 'b-')
    ax1.set_ylabel('Price')
    ax1.set_title('Synthetic Price Data')
    ax1.grid(True, alpha=0.3)
    
    # Plot volume
    ax2 = plt.subplot(2, 1, 2, sharex=ax1)
    ax2.bar(data.index, data['volume'], width=0.8, alpha=0.7, color='g')
    ax2.set_xlabel('Time')
    ax2.set_ylabel('Volume')
    ax2.set_title('Synthetic Volume Data')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    # Calculate VPIN using the simplified interface
    print("\n2. Calculating VPIN using bulk volume classification...")
    vpin = VPIN(n_buckets=50, window_size=50, classification_method='bulk')
    vpin_data = vpin.calculate(data)
    
    print(f"VPIN data shape: {vpin_data.shape}")
    print(f"VPIN range: {vpin.vpin.min():.4f} to {vpin.vpin.max():.4f}")
    
    # Plot VPIN with price
    print("\n3. Plotting VPIN with price...")
    vpin.plot(price_data=data['price'])
    
    # Detect toxic events
    print("\n4. Detecting toxic events...")
    toxic_events = vpin.detect_toxic_events(threshold=0.99)
    
    if toxic_events:
        print(f"Detected {len(toxic_events)} toxic events:")
        for i, event in enumerate(toxic_events):
            print(f"  {i+1}. {event}")
    else:
        print("No toxic events detected with threshold 0.99")
    
    # Calculate VPIN metrics
    print("\n5. Calculating VPIN metrics...")
    metrics = vpin.get_metrics()
    
    print("VPIN Metrics:")
    for key, value in metrics.items():
        if value is not None:
            print(f"  - {key}: {value:.4f}")
    
    # Extract VPIN features
    print("\n6. Extracting VPIN features...")
    features = vpin.get_features()
    
    print("VPIN Features:")
    for key, value in features.items():
        if value is not None:
            if isinstance(value, bool):
                print(f"  - {key}: {value}")
            else:
                print(f"  - {key}: {value:.4f}")
    
    # Compare different trade classification methods
    print("\n7. Comparing different trade classification methods...")
    
    # Calculate VPIN using different methods
    vpin_bulk = VPINCalculator(n_buckets=50, window_size=50, classification_method='bulk')
    vpin_tick = VPINCalculator(n_buckets=50, window_size=50, classification_method='tick')
    vpin_lee_ready = VPINCalculator(n_buckets=50, window_size=50, classification_method='lee_ready')
    
    vpin_bulk_data = vpin_bulk.calculate_vpin(data)
    vpin_tick_data = vpin_tick.calculate_vpin(data)
    vpin_lee_ready_data = vpin_lee_ready.calculate_vpin(data, data['bid'], data['ask'])
    
    # Plot comparison
    plt.figure(figsize=(12, 8))
    
    # Plot price
    ax1 = plt.subplot(2, 1, 1)
    ax1.plot(data.index, data['price'], 'b-')
    
    # Highlight toxic events from each method
    toxic_bulk = vpin_bulk.detect_toxic_events(threshold=0.99)
    toxic_tick = vpin_tick.detect_toxic_events(threshold=0.99)
    toxic_lee_ready = vpin_lee_ready.detect_toxic_events(threshold=0.99)
    
    for event in toxic_bulk:
        ax1.axvline(x=event, color='r', linestyle='--', alpha=0.5)
    
    for event in toxic_tick:
        ax1.axvline(x=event, color='g', linestyle='--', alpha=0.5)
    
    for event in toxic_lee_ready:
        ax1.axvline(x=event, color='b', linestyle='--', alpha=0.5)
    
    ax1.set_ylabel('Price')
    ax1.set_title('Price with Toxic Events')
    ax1.grid(True, alpha=0.3)
    
    # Plot VPIN from different methods
    ax2 = plt.subplot(2, 1, 2, sharex=ax1)
    ax2.plot(vpin_bulk.vpin_series.index, vpin_bulk.vpin_series.values, 'r-', label='Bulk')
    ax2.plot(vpin_tick.vpin_series.index, vpin_tick.vpin_series.values, 'g-', label='Tick')
    ax2.plot(vpin_lee_ready.vpin_series.index, vpin_lee_ready.vpin_series.values, 'b-', label='Lee-Ready')
    
    ax2.set_xlabel('Time')
    ax2.set_ylabel('VPIN')
    ax2.set_title('VPIN Comparison')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    # Analyze buy/sell imbalance
    print("\n8. Analyzing buy/sell imbalance...")
    vpin_bulk.plot_buy_sell_imbalance()
    
    # Analyze VPIN distribution
    print("\n9. Analyzing VPIN distribution...")
    vpin_bulk.plot_vpin_distribution()
    
    # Demonstrate using VPIN in a trading strategy
    print("\n10. Using VPIN in a trading strategy...")
    
    def vpin_based_strategy(price, vpin, vpin_cdf, threshold=0.9):
        """Simple strategy based on VPIN."""
        if vpin_cdf > threshold:
            # High probability of informed trading, reduce position size
            return -1  # Sell signal
        elif vpin < 0.2:
            # Low probability of informed trading, increase position size
            return 1  # Buy signal
        else:
            return 0  # Neutral
    
    # Apply strategy
    signals = []
    for i in range(len(vpin_bulk.vpin_series)):
        if i < len(vpin_bulk.vpin_series) - 1 and not np.isnan(vpin_bulk.vpin_series.iloc[i]) and not np.isnan(vpin_bulk.cdf_series.iloc[i]):
            signal = vpin_based_strategy(
                data['price'].iloc[i],
                vpin_bulk.vpin_series.iloc[i],
                vpin_bulk.cdf_series.iloc[i]
            )
            signals.append((vpin_bulk.vpin_series.index[i], data['price'].iloc[i], signal))
    
    # Plot signals
    plt.figure(figsize=(12, 8))
    
    # Plot price
    ax1 = plt.subplot(2, 1, 1)
    ax1.plot(data.index, data['price'], 'b-')
    
    # Plot signals
    for date, price, signal in signals:
        if signal == 1:  # Buy
            ax1.scatter(date, price, color='g', marker='^', s=100)
        elif signal == -1:  # Sell
            ax1.scatter(date, price, color='r', marker='v', s=100)
    
    ax1.set_ylabel('Price')
    ax1.set_title('Trading Signals Based on VPIN')
    ax1.grid(True, alpha=0.3)
    
    # Plot VPIN and CDF
    ax2 = plt.subplot(2, 1, 2, sharex=ax1)
    ax2.plot(vpin_bulk.vpin_series.index, vpin_bulk.vpin_series.values, 'g-', label='VPIN')
    ax2.plot(vpin_bulk.cdf_series.index, vpin_bulk.cdf_series.values, 'r-', label='CDF')
    
    # Add threshold line
    ax2.axhline(y=0.9, color='r', linestyle='--', label='Threshold: 0.9')
    
    ax2.set_xlabel('Time')
    ax2.set_ylabel('VPIN / CDF')
    ax2.set_title('VPIN and CDF')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    print("\nVPIN Example completed successfully!")

if __name__ == "__main__":
    main() 