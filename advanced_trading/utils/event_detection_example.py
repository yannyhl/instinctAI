"""
Event Detection Example
----------------------
This example demonstrates how to use the event detection module to identify
significant market events in financial time series data.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf
from datetime import datetime, timedelta
import logging

# Import our event detection module
from advanced_trading.utils.event_detection import (
    detect_volatility_events,
    detect_price_shocks,
    detect_trend_changes,
    detect_outliers,
    detect_patterns,
    cluster_events,
    detect_all_events
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def download_example_data(ticker: str = 'SPY', period: str = '2y') -> pd.DataFrame:
    """
    Download example financial data using yfinance.
    
    Parameters:
    -----------
    ticker : str
        Ticker symbol to download
    period : str
        Period to download (e.g. '1y', '2y', '5y')
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with OHLCV data
    """
    logger.info(f"Downloading {ticker} data for {period}")
    data = yf.download(ticker, period=period)
    logger.info(f"Downloaded {len(data)} rows of data")
    return data

def demonstrate_volatility_events():
    """Demonstrate volatility event detection."""
    # Download data
    data = download_example_data(ticker='SPY', period='2y')
    
    # Calculate returns
    returns = data['Close'].pct_change().dropna()
    
    # Detect volatility events
    volatility_events = detect_volatility_events(
        returns=returns,
        window=20,
        threshold_std=2.5,
        min_periods=5
    )
    
    # Plot results
    plt.figure(figsize=(12, 8))
    
    # Plot 1: Price and volatility events
    plt.subplot(2, 1, 1)
    plt.plot(data.index, data['Close'], 'b-', label='Price')
    
    # Highlight volatility events
    event_dates = volatility_events[volatility_events['is_event']].index
    for date in event_dates:
        plt.axvline(x=date, color='r', linestyle='--', alpha=0.3)
    
    plt.title('Price Chart with Volatility Events')
    plt.ylabel('Price')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Plot 2: Volatility and Z-score
    plt.subplot(2, 1, 2)
    plt.plot(volatility_events.index, volatility_events['volatility'], 'g-', label='Volatility')
    plt.plot(volatility_events.index, volatility_events['volatility_zscore'], 'm-', label='Volatility Z-score')
    
    # Highlight events and threshold
    plt.axhline(y=2.5, color='r', linestyle='--', label='Threshold')
    for date in event_dates:
        plt.axvline(x=date, color='r', linestyle='--', alpha=0.3)
    
    plt.title('Volatility and Z-score with Events')
    plt.ylabel('Value')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    # Print number of detected events
    event_count = volatility_events['is_event'].sum()
    logger.info(f"Detected {event_count} volatility events out of {len(volatility_events)} data points")
    
    return volatility_events

def demonstrate_price_shocks():
    """Demonstrate price shock detection."""
    # Download data
    data = download_example_data(ticker='SPY', period='2y')
    
    # Detect price shocks
    price_shocks = detect_price_shocks(
        prices=data['Close'],
        window=20,
        threshold_std=3.0,
        min_periods=5
    )
    
    # Plot results
    plt.figure(figsize=(12, 8))
    
    # Plot 1: Price and shock events
    plt.subplot(2, 1, 1)
    plt.plot(data.index, data['Close'], 'b-', label='Price')
    
    # Highlight shock events
    shock_dates = price_shocks[price_shocks['is_shock']].index
    for date in shock_dates:
        plt.axvline(x=date, color='r', linestyle='--', alpha=0.5)
    
    plt.title('Price Chart with Shock Events')
    plt.ylabel('Price')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Plot 2: Returns and Z-score
    plt.subplot(2, 1, 2)
    plt.plot(price_shocks.index, price_shocks['return'], 'g-', label='Return')
    plt.plot(price_shocks.index, price_shocks['return_zscore'], 'm-', label='Return Z-score')
    
    # Highlight events and thresholds
    plt.axhline(y=3.0, color='r', linestyle='--', label='Threshold')
    plt.axhline(y=-3.0, color='r', linestyle='--')
    for date in shock_dates:
        plt.axvline(x=date, color='r', linestyle='--', alpha=0.5)
    
    plt.title('Returns and Z-score with Shock Events')
    plt.ylabel('Value')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    # Print number of detected shocks
    shock_count = price_shocks['is_shock'].sum()
    logger.info(f"Detected {shock_count} price shocks out of {len(price_shocks)} data points")
    
    return price_shocks

def demonstrate_trend_changes():
    """Demonstrate trend change detection."""
    # Download data
    data = download_example_data(ticker='SPY', period='2y')
    
    # Detect trend changes
    trend_changes = detect_trend_changes(
        prices=data['Close'],
        fast_window=20,
        slow_window=50,
        confirmation_days=3,
        min_periods=5
    )
    
    # Plot results
    plt.figure(figsize=(12, 8))
    
    # Plot 1: Price, MAs, and trend changes
    plt.subplot(2, 1, 1)
    plt.plot(data.index, data['Close'], 'b-', label='Price')
    plt.plot(trend_changes.index, trend_changes['fast_ma'], 'g-', label='Fast MA (20)')
    plt.plot(trend_changes.index, trend_changes['slow_ma'], 'r-', label='Slow MA (50)')
    
    # Highlight trend changes
    bullish_dates = trend_changes[(trend_changes['trend_change']) & (trend_changes['trend_change_direction'] > 0)].index
    bearish_dates = trend_changes[(trend_changes['trend_change']) & (trend_changes['trend_change_direction'] < 0)].index
    
    for date in bullish_dates:
        plt.axvline(x=date, color='g', linestyle='--', alpha=0.5)
    
    for date in bearish_dates:
        plt.axvline(x=date, color='r', linestyle='--', alpha=0.5)
    
    plt.title('Price Chart with Moving Averages and Trend Changes')
    plt.ylabel('Price')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Plot 2: MA difference and trend
    plt.subplot(2, 1, 2)
    plt.plot(trend_changes.index, trend_changes['ma_diff'], 'b-', label='MA Difference')
    plt.plot(trend_changes.index, trend_changes['trend'], 'm-', label='Trend Direction')
    
    # Highlight trend changes
    for date in bullish_dates:
        plt.axvline(x=date, color='g', linestyle='--', alpha=0.5)
    
    for date in bearish_dates:
        plt.axvline(x=date, color='r', linestyle='--', alpha=0.5)
    
    plt.axhline(y=0, color='k', linestyle='-', alpha=0.3)
    
    plt.title('Moving Average Difference and Trend Direction')
    plt.ylabel('Value')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    # Print number of detected trend changes
    trend_change_count = trend_changes['trend_change'].sum()
    bullish_count = len(bullish_dates)
    bearish_count = len(bearish_dates)
    
    logger.info(f"Detected {trend_change_count} trend changes ({bullish_count} bullish, {bearish_count} bearish) out of {len(trend_changes)} data points")
    
    return trend_changes

def demonstrate_pattern_detection():
    """Demonstrate chart pattern detection."""
    # Download data
    data = download_example_data(ticker='SPY', period='2y')
    
    # Detect patterns
    patterns = detect_patterns(
        prices=data['Close'],
        volume=data['Volume'],
        window_size=50,
        pattern_types=['double_top', 'double_bottom', 'head_shoulders'],
        tolerance=0.03
    )
    
    # Plot results
    plt.figure(figsize=(12, 10))
    
    # Plot price with pattern markers
    plt.subplot(3, 1, 1)
    plt.plot(data.index, data['Close'], 'b-', label='Price')
    
    # Mark double tops
    double_top_dates = patterns[patterns['double_top_pattern']].index
    for date in double_top_dates:
        plt.axvline(x=date, color='r', linestyle='--', alpha=0.5)
        plt.text(date, data.loc[date, 'Close'] * 1.02, 'DT', color='r')
    
    # Mark double bottoms
    double_bottom_dates = patterns[patterns['double_bottom_pattern']].index
    for date in double_bottom_dates:
        plt.axvline(x=date, color='g', linestyle='--', alpha=0.5)
        plt.text(date, data.loc[date, 'Close'] * 0.98, 'DB', color='g')
    
    # Mark head and shoulders
    hs_dates = patterns[patterns['head_shoulders_pattern']].index
    for date in hs_dates:
        plt.axvline(x=date, color='m', linestyle='--', alpha=0.5)
        plt.text(date, data.loc[date, 'Close'] * 1.04, 'H&S', color='m')
    
    plt.title('Price Chart with Detected Patterns')
    plt.ylabel('Price')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Plot pattern strengths
    plt.subplot(3, 1, 2)
    plt.plot(patterns.index, patterns['double_top_strength'], 'r-', label='Double Top Strength')
    plt.plot(patterns.index, patterns['double_bottom_strength'], 'g-', label='Double Bottom Strength')
    plt.plot(patterns.index, patterns['head_shoulders_strength'], 'm-', label='Head & Shoulders Strength')
    
    plt.title('Pattern Strength')
    plt.ylabel('Strength')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Plot volume
    plt.subplot(3, 1, 3)
    plt.plot(data.index, data['Volume'], 'b-', label='Volume')
    
    plt.title('Trading Volume')
    plt.ylabel('Volume')
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    # Print number of detected patterns
    dt_count = patterns['double_top_pattern'].sum()
    db_count = patterns['double_bottom_pattern'].sum()
    hs_count = patterns['head_shoulders_pattern'].sum()
    
    logger.info(f"Detected {dt_count} double tops, {db_count} double bottoms, and {hs_count} head & shoulders patterns out of {len(patterns)} data points")
    
    return patterns

def demonstrate_combined_detection():
    """Demonstrate the detection of all event types and clustering."""
    # Download data
    data = download_example_data(ticker='SPY', period='2y')
    
    # Calculate returns
    returns = data['Close'].pct_change().dropna()
    
    # Detect all events
    all_events = detect_all_events(
        prices=data['Close'],
        returns=returns,
        volume=data['Volume'],
        window=20
    )
    
    # Get the cluster results
    clusters = all_events['cluster']
    
    # Plot results
    plt.figure(figsize=(12, 10))
    
    # Plot 1: Price with event clusters
    plt.subplot(2, 1, 1)
    plt.plot(data.index, data['Close'], 'b-', label='Price')
    
    # Highlight event clusters
    cluster_dates = clusters[clusters['event_cluster']].index
    for date in cluster_dates:
        plt.axvline(x=date, color='r', linestyle='--', alpha=0.3)
    
    plt.title('Price Chart with Event Clusters')
    plt.ylabel('Price')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # Plot 2: Event count and cluster strength
    plt.subplot(2, 1, 2)
    plt.plot(clusters.index, clusters['event_count'], 'g-', label='Event Count')
    plt.plot(clusters.index, clusters['rolling_event_count'], 'b-', label='Rolling Event Count')
    plt.plot(clusters.index, clusters['cluster_strength'] * 10, 'r-', label='Cluster Strength (x10)')
    
    # Highlight event clusters
    for date in cluster_dates:
        plt.axvline(x=date, color='r', linestyle='--', alpha=0.3)
    
    plt.title('Event Count and Cluster Strength')
    plt.ylabel('Value')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    # Print number of detected clusters
    cluster_count = clusters['event_cluster'].sum()
    logger.info(f"Detected {cluster_count} event clusters out of {len(clusters)} data points")
    
    return all_events

def main():
    """Run all demonstration functions."""
    try:
        logger.info("Starting event detection examples")
        
        # Demonstrate each detection type
        logger.info("Demonstrating volatility event detection")
        volatility_events = demonstrate_volatility_events()
        
        logger.info("Demonstrating price shock detection")
        price_shocks = demonstrate_price_shocks()
        
        logger.info("Demonstrating trend change detection")
        trend_changes = demonstrate_trend_changes()
        
        logger.info("Demonstrating pattern detection")
        patterns = demonstrate_pattern_detection()
        
        logger.info("Demonstrating combined event detection and clustering")
        all_events = demonstrate_combined_detection()
        
        logger.info("All event detection examples completed successfully")
        
    except Exception as e:
        logger.error(f"Error in event detection examples: {e}", exc_info=True)

if __name__ == "__main__":
    main() 