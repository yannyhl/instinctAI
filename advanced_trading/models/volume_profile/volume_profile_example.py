#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Example demonstrating the use of the VolumeProfile class for analyzing
volume distribution in financial markets.

This example shows how to:
1. Create a volume profile from price and volume data
2. Analyze the volume profile to identify key price levels
3. Visualize the volume profile in different ways
4. Extract features from the volume profile for use in trading strategies
5. Identify support and resistance levels based on volume distribution
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

# Import the VolumeProfile class
from models.volume_profile.volume_profile import VolumeProfile

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
        DataFrame with datetime index and price, volume columns.
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
    
    # Create DataFrame
    df = pd.DataFrame({
        'price': price_series,
        'volume': volume
    }, index=dates)
    
    return df

def main():
    print("Volume Profile Analysis Example")
    print("-------------------------------")
    
    # Generate synthetic data
    print("\n1. Generating synthetic price and volume data...")
    data = generate_synthetic_data(n_samples=1000)
    
    print(f"Generated data shape: {data.shape}")
    print(f"Price range: {data['price'].min():.2f} - {data['price'].max():.2f}")
    print(f"Total volume: {data['volume'].sum():.2f}")
    
    # Plot the data
    plt.figure(figsize=(12, 6))
    
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
    
    # Create volume profile
    print("\n2. Creating volume profile...")
    profile = VolumeProfile(
        price_data=data['price'],
        volume_data=data['volume'],
        n_bins=50
    )
    
    print(f"Point of Control (POC): {profile.get_point_of_control():.2f}")
    print(f"Value Area: {profile.get_value_area()[0]:.2f} - {profile.get_value_area()[1]:.2f}")
    
    # Plot volume profile
    print("\n3. Plotting volume profile...")
    profile.plot_profile(
        figsize=(10, 6),
        color='blue',
        show_poc=True,
        show_value_area=True,
        horizontal=True,
        title='Volume Profile'
    )
    
    # Plot volume profile with price
    print("\n4. Plotting volume profile with price...")
    profile.plot_profile_with_price(
        price_data=data['price'],
        figsize=(12, 8),
        profile_width=0.3,
        profile_color='blue',
        price_color='black',
        show_poc=True,
        show_value_area=True,
        title='Price with Volume Profile'
    )
    
    # Identify support and resistance levels
    print("\n5. Identifying support and resistance levels...")
    levels = profile.identify_support_resistance(volume_threshold=0.7)
    
    print("Support levels:")
    for level in levels['support']:
        print(f"  - {level:.2f}")
    
    print("Resistance levels:")
    for level in levels['resistance']:
        print(f"  - {level:.2f}")
    
    # Plot price with support and resistance levels
    plt.figure(figsize=(12, 6))
    plt.plot(data.index, data['price'], 'b-')
    
    # Plot support levels
    for level in levels['support']:
        plt.axhline(y=level, color='g', linestyle='--', alpha=0.7)
    
    # Plot resistance levels
    for level in levels['resistance']:
        plt.axhline(y=level, color='r', linestyle='--', alpha=0.7)
    
    # Plot POC
    plt.axhline(y=profile.get_point_of_control(), color='purple', linestyle='-', 
               label=f'POC: {profile.get_point_of_control():.2f}')
    
    plt.xlabel('Time')
    plt.ylabel('Price')
    plt.title('Price with Support and Resistance Levels')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
    
    # Generate buy/sell volume data for delta analysis
    print("\n6. Calculating volume delta...")
    
    # Simulate buy/sell volume (more buys at lower prices, more sells at higher prices)
    price_range = data['price'].max() - data['price'].min()
    mid_price = data['price'].min() + price_range / 2
    
    buy_ratio = 1 - (data['price'] - data['price'].min()) / price_range
    buy_ratio = buy_ratio * 0.5 + 0.3  # Scale to 0.3-0.8 range
    
    buy_volume = data['volume'] * buy_ratio
    sell_volume = data['volume'] * (1 - buy_ratio)
    
    # Calculate volume delta
    delta_profile = profile.calculate_volume_delta(buy_volume, sell_volume)
    
    # Plot volume delta
    profile.plot_volume_delta(
        delta_profile=delta_profile,
        figsize=(10, 6),
        title='Volume Delta Profile (Buy - Sell)'
    )
    
    # Extract features from volume profile
    print("\n7. Extracting features from volume profile...")
    features = profile.get_volume_profile_features()
    
    print("Volume Profile Features:")
    for key, value in features.items():
        print(f"  - {key}: {value:.4f}")
    
    # Demonstrate using volume profile in a trading strategy
    print("\n8. Using volume profile in a trading strategy...")
    
    # Simple strategy: Buy when price is near support, sell when price is near resistance
    def volume_profile_strategy(price, support_levels, resistance_levels, poc, tolerance=0.01):
        """Simple strategy based on volume profile levels."""
        # Check if price is near support
        for level in support_levels:
            if abs(price - level) / price < tolerance:
                return 1  # Buy signal
        
        # Check if price is near resistance
        for level in resistance_levels:
            if abs(price - level) / price < tolerance:
                return -1  # Sell signal
        
        # Check if price is near POC
        if abs(price - poc) / price < tolerance:
            return 0  # Neutral signal
        
        return None  # No signal
    
    # Apply strategy to the last 100 data points
    signals = []
    for i in range(len(data) - 100, len(data)):
        price = data['price'].iloc[i]
        signal = volume_profile_strategy(
            price, 
            levels['support'], 
            levels['resistance'], 
            profile.get_point_of_control(),
            tolerance=0.01
        )
        signals.append((data.index[i], price, signal))
    
    # Plot signals
    plt.figure(figsize=(12, 6))
    plt.plot(data.index[-100:], data['price'].iloc[-100:], 'b-')
    
    # Plot support levels
    for level in levels['support']:
        plt.axhline(y=level, color='g', linestyle='--', alpha=0.7)
    
    # Plot resistance levels
    for level in levels['resistance']:
        plt.axhline(y=level, color='r', linestyle='--', alpha=0.7)
    
    # Plot POC
    plt.axhline(y=profile.get_point_of_control(), color='purple', linestyle='-', 
               label=f'POC: {profile.get_point_of_control():.2f}')
    
    # Plot signals
    for date, price, signal in signals:
        if signal == 1:  # Buy
            plt.scatter(date, price, color='g', marker='^', s=100)
        elif signal == -1:  # Sell
            plt.scatter(date, price, color='r', marker='v', s=100)
        elif signal == 0:  # Neutral
            plt.scatter(date, price, color='blue', marker='o', s=50)
    
    plt.xlabel('Time')
    plt.ylabel('Price')
    plt.title('Trading Signals Based on Volume Profile')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
    
    print("\nVolume Profile Analysis Example completed successfully!")

if __name__ == "__main__":
    main() 