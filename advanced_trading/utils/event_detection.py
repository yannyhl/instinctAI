"""
Event Detection Module
---------------------
This module provides functions and classes for detecting significant market events
in time series data. It includes methods for identifying price shocks, volatility
clusters, trend changes, and outlier events.

Key components:
1. Volatility spikes detection
2. Price shock identification
3. Trend change detection
4. Outlier identification
5. Pattern recognition
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Union, Tuple, Optional
import logging
from scipy import stats
import warnings

# Configure logger
logger = logging.getLogger(__name__)

# Suppress specific warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, message="invalid value encountered in double_scalars")
warnings.filterwarnings("ignore", category=RuntimeWarning, message="Mean of empty slice")

def detect_volatility_events(
    returns: pd.Series,
    window: int = 20,
    threshold_std: float = 3.0,
    min_periods: int = 5
) -> pd.DataFrame:
    """
    Detect periods of abnormal volatility in returns series.
    
    Parameters:
    -----------
    returns : pd.Series
        Time series of asset returns
    window : int
        Rolling window to calculate volatility
    threshold_std : float
        Number of standard deviations to consider abnormal
    min_periods : int
        Minimum observations in window required to calculate volatility
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with columns:
        - 'volatility': rolling volatility
        - 'volatility_zscore': z-score of volatility
        - 'is_event': boolean indicator of abnormal volatility
    """
    # Calculate rolling volatility
    rolling_vol = returns.rolling(window=window, min_periods=min_periods).std()
    
    # Calculate volatility of volatility
    vol_of_vol = rolling_vol.rolling(window=window*2, min_periods=min_periods).std()
    
    # Calculate Z-score of volatility
    with np.errstate(divide='ignore', invalid='ignore'):
        vol_zscore = (rolling_vol - rolling_vol.rolling(window=window*3, min_periods=min_periods).mean()) / vol_of_vol
    
    # Identify volatility events
    is_event = vol_zscore > threshold_std
    
    # Create result DataFrame
    result = pd.DataFrame({
        'volatility': rolling_vol,
        'volatility_zscore': vol_zscore,
        'is_event': is_event
    }, index=returns.index)
    
    # Count number of events
    event_count = is_event.sum()
    logger.info(f"Detected {event_count} volatility events in time series of length {len(returns)}")
    
    return result

def detect_price_shocks(
    prices: pd.Series,
    returns: Optional[pd.Series] = None,
    window: int = 20,
    threshold_std: float = 4.0,
    min_periods: int = 5
) -> pd.DataFrame:
    """
    Detect sudden, significant price movements (shocks).
    
    Parameters:
    -----------
    prices : pd.Series
        Time series of asset prices
    returns : pd.Series, optional
        Time series of asset returns (if None, calculated from prices)
    window : int
        Rolling window to calculate typical price movement
    threshold_std : float
        Number of standard deviations to consider a shock
    min_periods : int
        Minimum observations in window required
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with columns:
        - 'return': asset returns
        - 'rolling_std': rolling standard deviation
        - 'return_zscore': z-score of returns
        - 'is_shock': boolean indicator of price shock
        - 'shock_magnitude': magnitude of shock (if any)
    """
    # Calculate returns if not provided
    if returns is None:
        returns = prices.pct_change()
    
    # Calculate rolling standard deviation
    rolling_std = returns.rolling(window=window, min_periods=min_periods).std()
    
    # Calculate Z-score of returns
    with np.errstate(divide='ignore', invalid='ignore'):
        return_zscore = returns / rolling_std
    
    # Identify price shocks
    is_shock = abs(return_zscore) > threshold_std
    
    # Calculate shock magnitude
    shock_magnitude = returns.copy()
    shock_magnitude[~is_shock] = 0
    
    # Create result DataFrame
    result = pd.DataFrame({
        'return': returns,
        'rolling_std': rolling_std,
        'return_zscore': return_zscore,
        'is_shock': is_shock,
        'shock_magnitude': shock_magnitude
    }, index=prices.index)
    
    # Count number of shocks
    shock_count = is_shock.sum()
    logger.info(f"Detected {shock_count} price shocks in time series of length {len(prices)}")
    
    return result

def detect_trend_changes(
    prices: pd.Series,
    fast_window: int = 20,
    slow_window: int = 50,
    confirmation_days: int = 3,
    min_periods: int = 5
) -> pd.DataFrame:
    """
    Detect significant changes in trend using moving average crossovers.
    
    Parameters:
    -----------
    prices : pd.Series
        Time series of asset prices
    fast_window : int
        Window for fast moving average
    slow_window : int
        Window for slow moving average
    confirmation_days : int
        Number of days to confirm a trend change
    min_periods : int
        Minimum observations in window required
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with columns:
        - 'fast_ma': Fast moving average
        - 'slow_ma': Slow moving average
        - 'ma_diff': Difference between fast and slow MA
        - 'trend': Trend direction (1 for uptrend, -1 for downtrend)
        - 'trend_change': Boolean indicator of trend change
        - 'trend_change_direction': Direction of trend change (1 for bullish, -1 for bearish)
    """
    # Calculate moving averages
    fast_ma = prices.rolling(window=fast_window, min_periods=min_periods).mean()
    slow_ma = prices.rolling(window=slow_window, min_periods=min_periods).mean()
    
    # Calculate difference
    ma_diff = fast_ma - slow_ma
    
    # Determine trend
    trend = np.where(ma_diff > 0, 1, -1)
    trend = pd.Series(trend, index=prices.index)
    
    # Detect trend changes
    trend_change = trend.diff() != 0
    
    # Get direction of trend change (1 for bullish, -1 for bearish)
    trend_change_direction = trend.diff()
    trend_change_direction = np.where(trend_change, trend_change_direction, 0)
    trend_change_direction = pd.Series(trend_change_direction, index=prices.index)
    
    # Apply confirmation filter - trend change must persist for confirmation_days
    if confirmation_days > 1:
        confirmed_changes = trend_change.copy()
        for i in range(1, confirmation_days):
            confirmed_changes = confirmed_changes & trend_change.shift(-i)
        
        # Only keep confirmed trend changes
        trend_change = confirmed_changes
        trend_change_direction = trend_change_direction * confirmed_changes
    
    # Create result DataFrame
    result = pd.DataFrame({
        'fast_ma': fast_ma,
        'slow_ma': slow_ma,
        'ma_diff': ma_diff,
        'trend': trend,
        'trend_change': trend_change,
        'trend_change_direction': trend_change_direction
    }, index=prices.index)
    
    # Count trend changes
    change_count = trend_change.sum()
    logger.info(f"Detected {change_count} trend changes in time series of length {len(prices)}")
    
    return result

def detect_outliers(
    data: pd.Series,
    window: int = 20,
    threshold_std: float = 3.0,
    method: str = 'zscore',
    min_periods: int = 5
) -> pd.DataFrame:
    """
    Detect outliers in time series data.
    
    Parameters:
    -----------
    data : pd.Series
        Time series data
    window : int
        Rolling window for calculating statistics
    threshold_std : float
        Threshold for outlier detection (interpretation depends on method)
    method : str
        Method for outlier detection:
        - 'zscore': Z-score based detection
        - 'iqr': Interquartile range based detection
        - 'modified_zscore': Uses median absolute deviation instead of std
    min_periods : int
        Minimum observations in window required
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with columns:
        - 'value': Original data values
        - 'score': Outlier score based on chosen method
        - 'is_outlier': Boolean indicator of outlier detection
        - 'outlier_magnitude': Magnitude of outlier (0 for non-outliers)
    """
    data_copy = data.copy()
    
    if method == 'zscore':
        # Calculate rolling mean and std
        rolling_mean = data_copy.rolling(window=window, min_periods=min_periods).mean()
        rolling_std = data_copy.rolling(window=window, min_periods=min_periods).std()
        
        # Calculate Z-score
        with np.errstate(divide='ignore', invalid='ignore'):
            score = (data_copy - rolling_mean) / rolling_std
            
        # Identify outliers
        is_outlier = abs(score) > threshold_std
        
    elif method == 'iqr':
        # Calculate rolling quantiles
        q1 = data_copy.rolling(window=window, min_periods=min_periods).quantile(0.25)
        q3 = data_copy.rolling(window=window, min_periods=min_periods).quantile(0.75)
        iqr = q3 - q1
        
        # Calculate bounds
        lower_bound = q1 - threshold_std * iqr
        upper_bound = q3 + threshold_std * iqr
        
        # Identify outliers
        is_outlier = (data_copy < lower_bound) | (data_copy > upper_bound)
        
        # Calculate normalized score
        with np.errstate(divide='ignore', invalid='ignore'):
            score = (data_copy - (q1 + q3) / 2) / iqr
            
    elif method == 'modified_zscore':
        # Calculate rolling median
        rolling_median = data_copy.rolling(window=window, min_periods=min_periods).median()
        
        # Calculate MAD (Median Absolute Deviation)
        mad = (data_copy - rolling_median).abs().rolling(window=window, min_periods=min_periods).median()
        
        # Calculate modified Z-score
        with np.errstate(divide='ignore', invalid='ignore'):
            score = 0.6745 * (data_copy - rolling_median) / mad
            
        # Identify outliers
        is_outlier = abs(score) > threshold_std
        
    else:
        raise ValueError(f"Unknown method: {method}. Must be one of 'zscore', 'iqr', or 'modified_zscore'")
    
    # Calculate outlier magnitude
    outlier_magnitude = data_copy - data_copy.rolling(window=window, min_periods=min_periods).median()
    outlier_magnitude = outlier_magnitude * is_outlier
    
    # Create result DataFrame
    result = pd.DataFrame({
        'value': data_copy,
        'score': score,
        'is_outlier': is_outlier,
        'outlier_magnitude': outlier_magnitude
    }, index=data.index)
    
    # Count outliers
    outlier_count = is_outlier.sum()
    logger.info(f"Detected {outlier_count} outliers in time series of length {len(data)} using method '{method}'")
    
    return result

def detect_patterns(
    prices: pd.Series,
    volume: Optional[pd.Series] = None,
    window_size: int = 20,
    pattern_types: List[str] = ['double_top', 'double_bottom', 'head_shoulders'],
    tolerance: float = 0.03
) -> pd.DataFrame:
    """
    Detect common chart patterns in price data.
    
    Parameters:
    -----------
    prices : pd.Series
        Time series of asset prices
    volume : pd.Series, optional
        Time series of trading volume (used for confirmation)
    window_size : int
        Window size to search for patterns
    pattern_types : List[str]
        Types of patterns to detect
    tolerance : float
        Tolerance for pattern matching (percentage)
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with columns for each pattern type detected
    """
    result = pd.DataFrame(index=prices.index)
    result['price'] = prices
    
    if volume is not None:
        result['volume'] = volume
    
    # Initialize pattern columns
    for pattern in pattern_types:
        result[f'{pattern}_pattern'] = False
        result[f'{pattern}_strength'] = 0.0
    
    # Function to check if two points are approximately equal
    def is_approx_equal(val1, val2, tol):
        return abs(val1 - val2) / val1 < tol if val1 != 0 else abs(val1 - val2) < tol
    
    # Scan for patterns using rolling windows
    for i in range(window_size, len(prices)):
        window_prices = prices.iloc[i-window_size:i]
        
        # Skip if not enough data
        if len(window_prices) < window_size:
            continue
        
        # Extract key points for pattern detection
        highs = window_prices.rolling(5, center=True).max()
        lows = window_prices.rolling(5, center=True).min()
        
        # Find local extrema
        high_points = []
        low_points = []
        
        for j in range(2, len(highs)-2):
            # Local high
            if highs.iloc[j] == window_prices.iloc[j] and window_prices.iloc[j] > window_prices.iloc[j-1] and window_prices.iloc[j] > window_prices.iloc[j+1]:
                high_points.append((j, window_prices.iloc[j]))
            
            # Local low
            if lows.iloc[j] == window_prices.iloc[j] and window_prices.iloc[j] < window_prices.iloc[j-1] and window_prices.iloc[j] < window_prices.iloc[j+1]:
                low_points.append((j, window_prices.iloc[j]))
        
        # Need at least 2 high points and 2 low points for pattern detection
        if len(high_points) < 2 or len(low_points) < 2:
            continue
        
        # Double Top detection
        if 'double_top' in pattern_types and len(high_points) >= 2:
            # Look for two similar peaks with a trough in between
            for p1_idx in range(len(high_points)-1):
                for p2_idx in range(p1_idx+1, len(high_points)):
                    p1 = high_points[p1_idx]
                    p2 = high_points[p2_idx]
                    
                    # Check if peaks are at similar levels
                    if is_approx_equal(p1[1], p2[1], tolerance):
                        # Check for a significant trough between peaks
                        min_between = window_prices.iloc[p1[0]:p2[0]].min()
                        height = p1[1] - min_between
                        
                        if height / p1[1] > tolerance * 2:  # Significant trough
                            strength = (1 - abs(p1[1] - p2[1]) / p1[1]) * (height / p1[1])
                            result.iloc[i, result.columns.get_loc('double_top_pattern')] = True
                            result.iloc[i, result.columns.get_loc('double_top_strength')] = strength
        
        # Double Bottom detection
        if 'double_bottom' in pattern_types and len(low_points) >= 2:
            # Look for two similar troughs with a peak in between
            for p1_idx in range(len(low_points)-1):
                for p2_idx in range(p1_idx+1, len(low_points)):
                    p1 = low_points[p1_idx]
                    p2 = low_points[p2_idx]
                    
                    # Check if troughs are at similar levels
                    if is_approx_equal(p1[1], p2[1], tolerance):
                        # Check for a significant peak between troughs
                        max_between = window_prices.iloc[p1[0]:p2[0]].max()
                        height = max_between - p1[1]
                        
                        if height / p1[1] > tolerance * 2:  # Significant peak
                            strength = (1 - abs(p1[1] - p2[1]) / p1[1]) * (height / p1[1])
                            result.iloc[i, result.columns.get_loc('double_bottom_pattern')] = True
                            result.iloc[i, result.columns.get_loc('double_bottom_strength')] = strength
        
        # Head and Shoulders detection
        if 'head_shoulders' in pattern_types and len(high_points) >= 3 and len(low_points) >= 2:
            # Look for 3 peaks with the middle one higher
            for p1_idx in range(len(high_points)-2):
                for p2_idx in range(p1_idx+1, len(high_points)-1):
                    for p3_idx in range(p2_idx+1, len(high_points)):
                        p1 = high_points[p1_idx]  # Left shoulder
                        p2 = high_points[p2_idx]  # Head
                        p3 = high_points[p3_idx]  # Right shoulder
                        
                        # Head should be higher than shoulders
                        if p2[1] > p1[1] and p2[1] > p3[1]:
                            # Shoulders should be at similar levels
                            if is_approx_equal(p1[1], p3[1], tolerance * 2):
                                # Check for neckline (troughs between shoulders and head)
                                min_left = window_prices.iloc[p1[0]:p2[0]].min()
                                min_right = window_prices.iloc[p2[0]:p3[0]].min()
                                
                                if is_approx_equal(min_left, min_right, tolerance * 2):
                                    strength = (1 - abs(p1[1] - p3[1]) / p1[1]) * (p2[1] - (min_left + min_right) / 2) / p2[1]
                                    result.iloc[i, result.columns.get_loc('head_shoulders_pattern')] = True
                                    result.iloc[i, result.columns.get_loc('head_shoulders_strength')] = strength
    
    # Count detected patterns
    for pattern in pattern_types:
        pattern_count = result[f'{pattern}_pattern'].sum()
        logger.info(f"Detected {pattern_count} {pattern} patterns in time series of length {len(prices)}")
    
    return result

def cluster_events(
    events_data: Dict[str, pd.DataFrame],
    window: int = 5
) -> pd.DataFrame:
    """
    Cluster multiple event types to identify periods of significant market activity.
    
    Parameters:
    -----------
    events_data : Dict[str, pd.DataFrame]
        Dictionary of event DataFrames, with keys as event types and values as
        DataFrames with boolean 'is_event' columns (output from other detection functions)
    window : int
        Window size for clustering events
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with:
        - Individual event columns
        - 'event_count': Count of simultaneous events
        - 'event_cluster': Boolean indicator of event clusters
        - 'cluster_strength': Measure of cluster significance
    """
    # Get a common index from the first DataFrame
    first_key = next(iter(events_data))
    common_index = events_data[first_key].index
    
    # Create result DataFrame with common index
    result = pd.DataFrame(index=common_index)
    
    # Add each event type
    for event_type, event_df in events_data.items():
        # Get the boolean event indicator column
        if 'is_event' in event_df.columns:
            event_col = event_df['is_event']
        elif 'is_shock' in event_df.columns:
            event_col = event_df['is_shock']
        elif 'is_outlier' in event_df.columns:
            event_col = event_df['is_outlier']
        elif 'trend_change' in event_df.columns:
            event_col = event_df['trend_change']
        else:
            # Try to find any boolean column
            bool_cols = [col for col, dtype in event_df.dtypes.items() if dtype == 'bool']
            if bool_cols:
                event_col = event_df[bool_cols[0]]
            else:
                logger.warning(f"No boolean event column found for {event_type}, skipping")
                continue
        
        # Add to result
        result[f'{event_type}_event'] = event_col
    
    # Count simultaneous events
    event_cols = [col for col in result.columns if col.endswith('_event')]
    result['event_count'] = result[event_cols].sum(axis=1)
    
    # Calculate rolling sum of events in window
    result['rolling_event_count'] = result['event_count'].rolling(window=window, min_periods=1).sum()
    
    # Identify clusters
    threshold = max(1, len(event_cols) * 0.3)  # At least 30% of event types
    result['event_cluster'] = result['rolling_event_count'] >= threshold * 2
    
    # Calculate cluster strength
    result['cluster_strength'] = result['rolling_event_count'] / (len(event_cols) * window)
    
    # Count clusters
    cluster_count = result['event_cluster'].sum()
    logger.info(f"Detected {cluster_count} event clusters from {len(event_cols)} event types")
    
    return result

# Shorthand functions for easy use

def detect_all_events(
    prices: pd.Series,
    returns: Optional[pd.Series] = None,
    volume: Optional[pd.Series] = None,
    window: int = 20
) -> Dict[str, pd.DataFrame]:
    """
    Run all event detection functions on the same data.
    
    Parameters:
    -----------
    prices : pd.Series
        Time series of asset prices
    returns : pd.Series, optional
        Time series of asset returns
    volume : pd.Series, optional
        Time series of trading volume
    window : int
        Window size for detection algorithms
        
    Returns:
    --------
    Dict[str, pd.DataFrame]
        Dictionary with results from all detection functions
    """
    # Calculate returns if not provided
    if returns is None:
        returns = prices.pct_change()
    
    # Run all detectors
    volatility_events = detect_volatility_events(returns, window=window)
    price_shocks = detect_price_shocks(prices, returns, window=window)
    trend_changes = detect_trend_changes(prices, fast_window=window, slow_window=window*2)
    outliers = detect_outliers(prices, window=window)
    
    patterns = None
    if volume is not None:
        patterns = detect_patterns(prices, volume, window_size=window)
    
    # Combine results
    results = {
        'volatility': volatility_events,
        'price_shock': price_shocks,
        'trend_change': trend_changes,
        'outlier': outliers
    }
    
    if patterns is not None:
        results['pattern'] = patterns
    
    # Create cluster
    results['cluster'] = cluster_events(results, window=window//2)
    
    return results 