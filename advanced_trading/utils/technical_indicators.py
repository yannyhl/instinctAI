#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Technical Indicators Module for Financial Market Analysis.

This module provides a comprehensive collection of technical indicators
commonly used in financial market analysis and algorithmic trading.
The indicators are implemented with a focus on performance, flexibility,
and ease of use.

The module includes trend indicators, momentum indicators, volatility indicators,
volume indicators, and cycle indicators, as well as utilities for combining
and customizing indicators.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union, Callable
import logging
from scipy import stats
import warnings

# Configure logging
logger = logging.getLogger(__name__)

# Suppress specific warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, message="invalid value encountered in double_scalars")
warnings.filterwarnings("ignore", category=RuntimeWarning, message="divide by zero encountered in double_scalars") 

# -------------------------------------------------------------------------
# Trend Indicators
# -------------------------------------------------------------------------

def sma(data: Union[pd.Series, np.ndarray], window: int) -> Union[pd.Series, np.ndarray]:
    """
    Calculate Simple Moving Average (SMA).
    
    Parameters
    ----------
    data : pd.Series or np.ndarray
        Price or other data to calculate SMA for.
    window : int
        Window size for SMA calculation.
        
    Returns
    -------
    pd.Series or np.ndarray
        Simple Moving Average values.
    """
    if isinstance(data, pd.Series):
        return data.rolling(window=window).mean()
    else:
        # For numpy arrays, use convolution
        weights = np.ones(window) / window
        return np.convolve(data, weights, mode='same')


def ema(data: Union[pd.Series, np.ndarray], window: int, alpha: Optional[float] = None) -> Union[pd.Series, np.ndarray]:
    """
    Calculate Exponential Moving Average (EMA).
    
    Parameters
    ----------
    data : pd.Series or np.ndarray
        Price or other data to calculate EMA for.
    window : int
        Window size for EMA calculation.
    alpha : float, optional
        Smoothing factor. If None, alpha = 2 / (window + 1).
        
    Returns
    -------
    pd.Series or np.ndarray
        Exponential Moving Average values.
    """
    if alpha is None:
        alpha = 2 / (window + 1)
    
    if isinstance(data, pd.Series):
        return data.ewm(alpha=alpha, adjust=False).mean()
    else:
        # For numpy arrays, calculate EMA manually
        ema_values = np.zeros_like(data)
        ema_values[0] = data[0]
        for i in range(1, len(data)):
            ema_values[i] = alpha * data[i] + (1 - alpha) * ema_values[i-1]
        return ema_values


def wma(data: Union[pd.Series, np.ndarray], window: int) -> Union[pd.Series, np.ndarray]:
    """
    Calculate Weighted Moving Average (WMA).
    
    Parameters
    ----------
    data : pd.Series or np.ndarray
        Price or other data to calculate WMA for.
    window : int
        Window size for WMA calculation.
        
    Returns
    -------
    pd.Series or np.ndarray
        Weighted Moving Average values.
    """
    weights = np.arange(1, window + 1)
    
    if isinstance(data, pd.Series):
        return data.rolling(window=window).apply(
            lambda x: np.sum(weights * x) / np.sum(weights), raw=True
        )
    else:
        # For numpy arrays, calculate WMA manually
        wma_values = np.zeros_like(data)
        for i in range(window - 1, len(data)):
            wma_values[i] = np.sum(weights * data[i - window + 1:i + 1]) / np.sum(weights)
        return wma_values


def macd(
    data: Union[pd.Series, np.ndarray],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Dict[str, Union[pd.Series, np.ndarray]]:
    """
    Calculate Moving Average Convergence Divergence (MACD).
    
    Parameters
    ----------
    data : pd.Series or np.ndarray
        Price or other data to calculate MACD for.
    fast_period : int, default=12
        Window size for fast EMA.
    slow_period : int, default=26
        Window size for slow EMA.
    signal_period : int, default=9
        Window size for signal line.
        
    Returns
    -------
    Dict[str, pd.Series or np.ndarray]
        Dictionary with 'macd', 'signal', and 'histogram' keys.
    """
    fast_ema = ema(data, fast_period)
    slow_ema = ema(data, slow_period)
    macd_line = fast_ema - slow_ema
    signal_line = ema(macd_line, signal_period)
    histogram = macd_line - signal_line
    
    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }


def bollinger_bands(
    data: Union[pd.Series, np.ndarray],
    window: int = 20,
    num_std: float = 2.0
) -> Dict[str, Union[pd.Series, np.ndarray]]:
    """
    Calculate Bollinger Bands.
    
    Parameters
    ----------
    data : pd.Series or np.ndarray
        Price or other data to calculate Bollinger Bands for.
    window : int, default=20
        Window size for moving average and standard deviation.
    num_std : float, default=2.0
        Number of standard deviations for the bands.
        
    Returns
    -------
    Dict[str, pd.Series or np.ndarray]
        Dictionary with 'middle', 'upper', and 'lower' keys.
    """
    if isinstance(data, pd.Series):
        middle = data.rolling(window=window).mean()
        std = data.rolling(window=window).std(ddof=0)
        upper = middle + (std * num_std)
        lower = middle - (std * num_std)
    else:
        # For numpy arrays, calculate manually
        middle = np.zeros_like(data)
        std = np.zeros_like(data)
        for i in range(window - 1, len(data)):
            window_slice = data[i - window + 1:i + 1]
            middle[i] = np.mean(window_slice)
            std[i] = np.std(window_slice, ddof=0)
        
        upper = middle + (std * num_std)
        lower = middle - (std * num_std)
    
    return {
        'middle': middle,
        'upper': upper,
        'lower': lower
    }


def keltner_channels(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    window: int = 20,
    atr_window: int = 10,
    multiplier: float = 2.0
) -> Dict[str, Union[pd.Series, np.ndarray]]:
    """
    Calculate Keltner Channels.
    
    Parameters
    ----------
    high : pd.Series or np.ndarray
        High prices.
    low : pd.Series or np.ndarray
        Low prices.
    close : pd.Series or np.ndarray
        Close prices.
    window : int, default=20
        Window size for EMA.
    atr_window : int, default=10
        Window size for ATR.
    multiplier : float, default=2.0
        Multiplier for ATR.
        
    Returns
    -------
    Dict[str, pd.Series or np.ndarray]
        Dictionary with 'middle', 'upper', and 'lower' keys.
    """
    # Calculate middle line (EMA of close)
    middle = ema(close, window)
    
    # Calculate ATR
    atr_values = atr(high, low, close, atr_window)
    
    # Calculate upper and lower bands
    upper = middle + (multiplier * atr_values)
    lower = middle - (multiplier * atr_values)
    
    return {
        'middle': middle,
        'upper': upper,
        'lower': lower
    }


def parabolic_sar(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    af_start: float = 0.02,
    af_increment: float = 0.02,
    af_max: float = 0.2
) -> Union[pd.Series, np.ndarray]:
    """
    Calculate Parabolic SAR (Stop and Reverse).
    
    Parameters
    ----------
    high : pd.Series or np.ndarray
        High prices.
    low : pd.Series or np.ndarray
        Low prices.
    af_start : float, default=0.02
        Starting acceleration factor.
    af_increment : float, default=0.02
        Acceleration factor increment.
    af_max : float, default=0.2
        Maximum acceleration factor.
        
    Returns
    -------
    pd.Series or np.ndarray
        Parabolic SAR values.
    """
    # Convert to numpy arrays for calculation
    if isinstance(high, pd.Series):
        high_values = high.values
        low_values = low.values
        index = high.index
        return_series = True
    else:
        high_values = high
        low_values = low
        return_series = False
    
    # Initialize variables
    n = len(high_values)
    sar = np.zeros(n)
    ep = np.zeros(n)  # Extreme point
    af = np.zeros(n)  # Acceleration factor
    trend = np.zeros(n)  # 1 for uptrend, -1 for downtrend
    
    # Initialize trend, EP, and SAR for the first period
    trend[0] = 1  # Start with uptrend
    ep[0] = high_values[0]
    sar[0] = low_values[0]
    af[0] = af_start
    
    # Calculate SAR values
    for i in range(1, n):
        # Previous SAR
        sar[i] = sar[i-1] + af[i-1] * (ep[i-1] - sar[i-1])
        
        # Adjust SAR value for current period
        if trend[i-1] == 1:  # Previous trend is up
            # SAR can't be higher than the lowest low of the previous two periods
            if i >= 2:
                sar[i] = min(sar[i], min(low_values[i-2:i]))
            else:
                sar[i] = min(sar[i], low_values[i-1])
            
            # Check if current low is below SAR (trend reversal)
            if low_values[i] < sar[i]:
                trend[i] = -1  # Change to downtrend
                sar[i] = ep[i-1]  # SAR becomes the previous EP
                ep[i] = low_values[i]  # EP becomes the current low
                af[i] = af_start  # Reset AF
            else:
                trend[i] = 1  # Continue uptrend
                if high_values[i] > ep[i-1]:
                    ep[i] = high_values[i]  # Update EP
                    af[i] = min(af[i-1] + af_increment, af_max)  # Increase AF
                else:
                    ep[i] = ep[i-1]  # Keep previous EP
                    af[i] = af[i-1]  # Keep previous AF
        else:  # Previous trend is down
            # SAR can't be lower than the highest high of the previous two periods
            if i >= 2:
                sar[i] = max(sar[i], max(high_values[i-2:i]))
            else:
                sar[i] = max(sar[i], high_values[i-1])
            
            # Check if current high is above SAR (trend reversal)
            if high_values[i] > sar[i]:
                trend[i] = 1  # Change to uptrend
                sar[i] = ep[i-1]  # SAR becomes the previous EP
                ep[i] = high_values[i]  # EP becomes the current high
                af[i] = af_start  # Reset AF
            else:
                trend[i] = -1  # Continue downtrend
                if low_values[i] < ep[i-1]:
                    ep[i] = low_values[i]  # Update EP
                    af[i] = min(af[i-1] + af_increment, af_max)  # Increase AF
                else:
                    ep[i] = ep[i-1]  # Keep previous EP
                    af[i] = af[i-1]  # Keep previous AF
    
    # Return as Series if input was Series
    if return_series:
        return pd.Series(sar, index=index)
    else:
        return sar


def ichimoku_cloud(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
    displacement: int = 26
) -> Dict[str, Union[pd.Series, np.ndarray]]:
    """
    Calculate Ichimoku Cloud components.
    
    Parameters
    ----------
    high : pd.Series or np.ndarray
        High prices.
    low : pd.Series or np.ndarray
        Low prices.
    close : pd.Series or np.ndarray
        Close prices.
    tenkan_period : int, default=9
        Period for Tenkan-sen (Conversion Line).
    kijun_period : int, default=26
        Period for Kijun-sen (Base Line).
    senkou_b_period : int, default=52
        Period for Senkou Span B.
    displacement : int, default=26
        Displacement for Senkou Span A and B.
        
    Returns
    -------
    Dict[str, pd.Series or np.ndarray]
        Dictionary with 'tenkan_sen', 'kijun_sen', 'senkou_span_a', 'senkou_span_b', and 'chikou_span' keys.
    """
    # Convert to pandas Series for calculation if numpy arrays
    if not isinstance(high, pd.Series):
        high = pd.Series(high)
        low = pd.Series(low)
        close = pd.Series(close)
        return_series = False
    else:
        return_series = True
    
    # Calculate Tenkan-sen (Conversion Line): (highest high + lowest low) / 2 for the past tenkan_period
    tenkan_sen = (high.rolling(window=tenkan_period).max() + low.rolling(window=tenkan_period).min()) / 2
    
    # Calculate Kijun-sen (Base Line): (highest high + lowest low) / 2 for the past kijun_period
    kijun_sen = (high.rolling(window=kijun_period).max() + low.rolling(window=kijun_period).min()) / 2
    
    # Calculate Senkou Span A (Leading Span A): (Tenkan-sen + Kijun-sen) / 2, displaced forward by displacement periods
    senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(displacement)
    
    # Calculate Senkou Span B (Leading Span B): (highest high + lowest low) / 2 for the past senkou_b_period, displaced forward by displacement periods
    senkou_span_b = ((high.rolling(window=senkou_b_period).max() + low.rolling(window=senkou_b_period).min()) / 2).shift(displacement)
    
    # Calculate Chikou Span (Lagging Span): Close price, displaced backwards by displacement periods
    chikou_span = close.shift(-displacement)
    
    # Return as numpy arrays if input was numpy arrays
    if not return_series:
        tenkan_sen = tenkan_sen.values
        kijun_sen = kijun_sen.values
        senkou_span_a = senkou_span_a.values
        senkou_span_b = senkou_span_b.values
        chikou_span = chikou_span.values
    
    return {
        'tenkan_sen': tenkan_sen,
        'kijun_sen': kijun_sen,
        'senkou_span_a': senkou_span_a,
        'senkou_span_b': senkou_span_b,
        'chikou_span': chikou_span
    }


def supertrend(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    period: int = 10,
    multiplier: float = 3.0
) -> Dict[str, Union[pd.Series, np.ndarray]]:
    """
    Calculate SuperTrend indicator.
    
    Parameters
    ----------
    high : pd.Series or np.ndarray
        High prices.
    low : pd.Series or np.ndarray
        Low prices.
    close : pd.Series or np.ndarray
        Close prices.
    period : int, default=10
        Period for ATR calculation.
    multiplier : float, default=3.0
        Multiplier for ATR.
        
    Returns
    -------
    Dict[str, pd.Series or np.ndarray]
        Dictionary with 'supertrend', 'direction', 'upper_band', and 'lower_band' keys.
    """
    # Convert to pandas Series for calculation if numpy arrays
    if not isinstance(high, pd.Series):
        high = pd.Series(high)
        low = pd.Series(low)
        close = pd.Series(close)
        return_series = False
    else:
        return_series = True
    
    # Calculate ATR
    atr_values = atr(high, low, close, period)
    
    # Calculate basic upper and lower bands
    basic_upper = (high + low) / 2 + (multiplier * atr_values)
    basic_lower = (high + low) / 2 - (multiplier * atr_values)
    
    # Initialize final bands and trend direction
    final_upper = np.zeros(len(close))
    final_lower = np.zeros(len(close))
    supertrend = np.zeros(len(close))
    direction = np.zeros(len(close))  # 1 for uptrend, -1 for downtrend
    
    # Set initial values
    final_upper[0] = basic_upper[0]
    final_lower[0] = basic_lower[0]
    supertrend[0] = (final_upper[0] + final_lower[0]) / 2
    direction[0] = 1 if close[0] > supertrend[0] else -1
    
    # Calculate SuperTrend
    for i in range(1, len(close)):
        # Calculate final upper band
        if basic_upper[i] < final_upper[i-1] or close[i-1] > final_upper[i-1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i-1]
        
        # Calculate final lower band
        if basic_lower[i] > final_lower[i-1] or close[i-1] < final_lower[i-1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i-1]
        
        # Determine trend direction
        if supertrend[i-1] == final_upper[i-1]:
            # Previous trend was down
            if close[i] > final_upper[i]:
                # Trend reversal to up
                supertrend[i] = final_lower[i]
                direction[i] = 1
            else:
                # Continue downtrend
                supertrend[i] = final_upper[i]
                direction[i] = -1
        else:
            # Previous trend was up
            if close[i] < final_lower[i]:
                # Trend reversal to down
                supertrend[i] = final_upper[i]
                direction[i] = -1
            else:
                # Continue uptrend
                supertrend[i] = final_lower[i]
                direction[i] = 1
    
    # Convert to pandas Series if input was Series
    if return_series:
        supertrend = pd.Series(supertrend, index=close.index)
        direction = pd.Series(direction, index=close.index)
        final_upper = pd.Series(final_upper, index=close.index)
        final_lower = pd.Series(final_lower, index=close.index)
    
    return {
        'supertrend': supertrend,
        'direction': direction,
        'upper_band': final_upper,
        'lower_band': final_lower
    }

# -------------------------------------------------------------------------
# Volatility Indicators
# -------------------------------------------------------------------------

def atr(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    window: int = 14
) -> Union[pd.Series, np.ndarray]:
    """
    Calculate Average True Range (ATR).
    
    Parameters
    ----------
    high : pd.Series or np.ndarray
        High prices.
    low : pd.Series or np.ndarray
        Low prices.
    close : pd.Series or np.ndarray
        Close prices.
    window : int, default=14
        Window size for ATR calculation.
        
    Returns
    -------
    pd.Series or np.ndarray
        ATR values.
    """
    # Convert to pandas Series for calculation if numpy arrays
    if not isinstance(high, pd.Series):
        high = pd.Series(high)
        low = pd.Series(low)
        close = pd.Series(close)
        return_series = False
    else:
        return_series = True
    
    # Calculate True Range
    prev_close = close.shift(1)
    tr1 = high - low  # Current high - current low
    tr2 = (high - prev_close).abs()  # Current high - previous close
    tr3 = (low - prev_close).abs()  # Current low - previous close
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Calculate ATR
    atr_values = tr.rolling(window=window).mean()
    
    # Return as numpy array if input was numpy arrays
    if not return_series:
        atr_values = atr_values.values
    
    return atr_values


# -------------------------------------------------------------------------
# Momentum Indicators
# -------------------------------------------------------------------------

def rsi(
    data: Union[pd.Series, np.ndarray],
    window: int = 14
) -> Union[pd.Series, np.ndarray]:
    """
    Calculate Relative Strength Index (RSI).
    
    Parameters
    ----------
    data : pd.Series or np.ndarray
        Price or other data to calculate RSI for.
    window : int, default=14
        Window size for RSI calculation.
        
    Returns
    -------
    pd.Series or np.ndarray
        RSI values.
    """
    # Convert to pandas Series for calculation if numpy array
    if not isinstance(data, pd.Series):
        data = pd.Series(data)
        return_series = False
    else:
        return_series = True
    
    # Calculate price changes
    delta = data.diff()
    
    # Separate gains and losses
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # Calculate average gain and loss
    avg_gain = gain.rolling(window=window).mean()
    avg_loss = loss.rolling(window=window).mean()
    
    # Calculate RS
    rs = avg_gain / avg_loss
    
    # Calculate RSI
    rsi_values = 100 - (100 / (1 + rs))
    
    # Return as numpy array if input was numpy array
    if not return_series:
        rsi_values = rsi_values.values
    
    return rsi_values


def stochastic(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    k_window: int = 14,
    d_window: int = 3,
    smooth_k: int = 1
) -> Dict[str, Union[pd.Series, np.ndarray]]:
    """
    Calculate Stochastic Oscillator.
    
    Parameters
    ----------
    high : pd.Series or np.ndarray
        High prices.
    low : pd.Series or np.ndarray
        Low prices.
    close : pd.Series or np.ndarray
        Close prices.
    k_window : int, default=14
        Window size for %K calculation.
    d_window : int, default=3
        Window size for %D calculation.
    smooth_k : int, default=1
        Window size for smoothing %K.
        
    Returns
    -------
    Dict[str, pd.Series or np.ndarray]
        Dictionary with 'k' and 'd' keys.
    """
    # Convert to pandas Series for calculation if numpy arrays
    if not isinstance(high, pd.Series):
        high = pd.Series(high)
        low = pd.Series(low)
        close = pd.Series(close)
        return_series = False
    else:
        return_series = True
    
    # Calculate %K
    lowest_low = low.rolling(window=k_window).min()
    highest_high = high.rolling(window=k_window).max()
    k = 100 * ((close - lowest_low) / (highest_high - lowest_low))
    
    # Smooth %K if required
    if smooth_k > 1:
        k = k.rolling(window=smooth_k).mean()
    
    # Calculate %D
    d = k.rolling(window=d_window).mean()
    
    # Return as numpy arrays if input was numpy arrays
    if not return_series:
        k = k.values
        d = d.values
    
    return {
        'k': k,
        'd': d
    }


def cci(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    window: int = 20,
    constant: float = 0.015
) -> Union[pd.Series, np.ndarray]:
    """
    Calculate Commodity Channel Index (CCI).
    
    Parameters
    ----------
    high : pd.Series or np.ndarray
        High prices.
    low : pd.Series or np.ndarray
        Low prices.
    close : pd.Series or np.ndarray
        Close prices.
    window : int, default=20
        Window size for CCI calculation.
    constant : float, default=0.015
        Constant factor.
        
    Returns
    -------
    pd.Series or np.ndarray
        CCI values.
    """
    # Convert to pandas Series for calculation if numpy arrays
    if not isinstance(high, pd.Series):
        high = pd.Series(high)
        low = pd.Series(low)
        close = pd.Series(close)
        return_series = False
    else:
        return_series = True
    
    # Calculate typical price
    tp = (high + low + close) / 3
    
    # Calculate simple moving average of typical price
    tp_sma = tp.rolling(window=window).mean()
    
    # Calculate mean deviation
    mean_deviation = tp.rolling(window=window).apply(lambda x: np.mean(np.abs(x - np.mean(x))), raw=True)
    
    # Calculate CCI
    cci_values = (tp - tp_sma) / (constant * mean_deviation)
    
    # Return as numpy array if input was numpy arrays
    if not return_series:
        cci_values = cci_values.values
    
    return cci_values


def williams_r(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    window: int = 14
) -> Union[pd.Series, np.ndarray]:
    """
    Calculate Williams %R.
    
    Parameters
    ----------
    high : pd.Series or np.ndarray
        High prices.
    low : pd.Series or np.ndarray
        Low prices.
    close : pd.Series or np.ndarray
        Close prices.
    window : int, default=14
        Window size for Williams %R calculation.
        
    Returns
    -------
    pd.Series or np.ndarray
        Williams %R values.
    """
    # Convert to pandas Series for calculation if numpy arrays
    if not isinstance(high, pd.Series):
        high = pd.Series(high)
        low = pd.Series(low)
        close = pd.Series(close)
        return_series = False
    else:
        return_series = True
    
    # Calculate highest high and lowest low
    highest_high = high.rolling(window=window).max()
    lowest_low = low.rolling(window=window).min()
    
    # Calculate Williams %R
    williams_r_values = -100 * (highest_high - close) / (highest_high - lowest_low)
    
    # Return as numpy array if input was numpy arrays
    if not return_series:
        williams_r_values = williams_r_values.values
    
    return williams_r_values


def roc(
    data: Union[pd.Series, np.ndarray],
    window: int = 12
) -> Union[pd.Series, np.ndarray]:
    """
    Calculate Rate of Change (ROC).
    
    Parameters
    ----------
    data : pd.Series or np.ndarray
        Price or other data to calculate ROC for.
    window : int, default=12
        Window size for ROC calculation.
        
    Returns
    -------
    pd.Series or np.ndarray
        ROC values.
    """
    # Convert to pandas Series for calculation if numpy array
    if not isinstance(data, pd.Series):
        data = pd.Series(data)
        return_series = False
    else:
        return_series = True
    
    # Calculate ROC
    roc_values = 100 * (data / data.shift(window) - 1)
    
    # Return as numpy array if input was numpy array
    if not return_series:
        roc_values = roc_values.values
    
    return roc_values


def momentum(
    data: Union[pd.Series, np.ndarray],
    window: int = 14
) -> Union[pd.Series, np.ndarray]:
    """
    Calculate Momentum.
    
    Parameters
    ----------
    data : pd.Series or np.ndarray
        Price or other data to calculate Momentum for.
    window : int, default=14
        Window size for Momentum calculation.
        
    Returns
    -------
    pd.Series or np.ndarray
        Momentum values.
    """
    # Convert to pandas Series for calculation if numpy array
    if not isinstance(data, pd.Series):
        data = pd.Series(data)
        return_series = False
    else:
        return_series = True
    
    # Calculate Momentum
    momentum_values = data - data.shift(window)
    
    # Return as numpy array if input was numpy array
    if not return_series:
        momentum_values = momentum_values.values
    
    return momentum_values


def tsi(
    data: Union[pd.Series, np.ndarray],
    long_window: int = 25,
    short_window: int = 13
) -> Union[pd.Series, np.ndarray]:
    """
    Calculate True Strength Index (TSI).
    
    Parameters
    ----------
    data : pd.Series or np.ndarray
        Price or other data to calculate TSI for.
    long_window : int, default=25
        Long window size for TSI calculation.
    short_window : int, default=13
        Short window size for TSI calculation.
        
    Returns
    -------
    pd.Series or np.ndarray
        TSI values.
    """
    # Convert to pandas Series for calculation if numpy array
    if not isinstance(data, pd.Series):
        data = pd.Series(data)
        return_series = False
    else:
        return_series = True
    
    # Calculate price changes
    momentum = data.diff()
    
    # Calculate double smoothed momentum
    momentum_ema1 = momentum.ewm(span=long_window, adjust=False).mean()
    momentum_ema2 = momentum_ema1.ewm(span=short_window, adjust=False).mean()
    
    # Calculate double smoothed absolute momentum
    abs_momentum = momentum.abs()
    abs_momentum_ema1 = abs_momentum.ewm(span=long_window, adjust=False).mean()
    abs_momentum_ema2 = abs_momentum_ema1.ewm(span=short_window, adjust=False).mean()
    
    # Calculate TSI
    tsi_values = 100 * momentum_ema2 / abs_momentum_ema2
    
    # Return as numpy array if input was numpy array
    if not return_series:
        tsi_values = tsi_values.values
    
    return tsi_values


def awesome_oscillator(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    short_window: int = 5,
    long_window: int = 34
) -> Union[pd.Series, np.ndarray]:
    """
    Calculate Awesome Oscillator.
    
    Parameters
    ----------
    high : pd.Series or np.ndarray
        High prices.
    low : pd.Series or np.ndarray
        Low prices.
    short_window : int, default=5
        Short window size for Awesome Oscillator calculation.
    long_window : int, default=34
        Long window size for Awesome Oscillator calculation.
        
    Returns
    -------
    pd.Series or np.ndarray
        Awesome Oscillator values.
    """
    # Convert to pandas Series for calculation if numpy arrays
    if not isinstance(high, pd.Series):
        high = pd.Series(high)
        low = pd.Series(low)
        return_series = False
    else:
        return_series = True
    
    # Calculate median price
    median_price = (high + low) / 2
    
    # Calculate simple moving averages
    short_sma = median_price.rolling(window=short_window).mean()
    long_sma = median_price.rolling(window=long_window).mean()
    
    # Calculate Awesome Oscillator
    ao_values = short_sma - long_sma
    
    # Return as numpy array if input was numpy arrays
    if not return_series:
        ao_values = ao_values.values
    
    return ao_values

# -------------------------------------------------------------------------
# Volume Indicators
# -------------------------------------------------------------------------

def obv(
    close: Union[pd.Series, np.ndarray],
    volume: Union[pd.Series, np.ndarray]
) -> Union[pd.Series, np.ndarray]:
    """
    Calculate On-Balance Volume (OBV).
    
    Parameters
    ----------
    close : pd.Series or np.ndarray
        Close prices.
    volume : pd.Series or np.ndarray
        Volume data.
        
    Returns
    -------
    pd.Series or np.ndarray
        OBV values.
    """
    # Convert to pandas Series for calculation if numpy arrays
    if not isinstance(close, pd.Series):
        close = pd.Series(close)
        volume = pd.Series(volume)
        return_series = False
    else:
        return_series = True
    
    # Calculate price changes
    price_change = close.diff()
    
    # Initialize OBV
    obv_values = pd.Series(0, index=close.index)
    
    # Calculate OBV
    for i in range(1, len(close)):
        if price_change.iloc[i] > 0:
            obv_values.iloc[i] = obv_values.iloc[i-1] + volume.iloc[i]
        elif price_change.iloc[i] < 0:
            obv_values.iloc[i] = obv_values.iloc[i-1] - volume.iloc[i]
        else:
            obv_values.iloc[i] = obv_values.iloc[i-1]
    
    # Return as numpy array if input was numpy arrays
    if not return_series:
        obv_values = obv_values.values
    
    return obv_values


def mfi(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    volume: Union[pd.Series, np.ndarray],
    window: int = 14
) -> Union[pd.Series, np.ndarray]:
    """
    Calculate Money Flow Index (MFI).
    
    Parameters
    ----------
    high : pd.Series or np.ndarray
        High prices.
    low : pd.Series or np.ndarray
        Low prices.
    close : pd.Series or np.ndarray
        Close prices.
    volume : pd.Series or np.ndarray
        Volume data.
    window : int, default=14
        Window size for MFI calculation.
        
    Returns
    -------
    pd.Series or np.ndarray
        MFI values.
    """
    # Convert to pandas Series for calculation if numpy arrays
    if not isinstance(high, pd.Series):
        high = pd.Series(high)
        low = pd.Series(low)
        close = pd.Series(close)
        volume = pd.Series(volume)
        return_series = False
    else:
        return_series = True
    
    # Calculate typical price
    tp = (high + low + close) / 3
    
    # Calculate money flow
    money_flow = tp * volume
    
    # Calculate positive and negative money flow
    diff = tp.diff()
    positive_flow = pd.Series(0, index=tp.index)
    negative_flow = pd.Series(0, index=tp.index)
    
    positive_flow[diff > 0] = money_flow[diff > 0]
    negative_flow[diff < 0] = money_flow[diff < 0]
    
    # Calculate positive and negative money flow ratio
    positive_mf = positive_flow.rolling(window=window).sum()
    negative_mf = negative_flow.rolling(window=window).sum()
    
    # Calculate money flow ratio and MFI
    mfr = positive_mf / negative_mf
    mfi_values = 100 - (100 / (1 + mfr))
    
    # Return as numpy array if input was numpy arrays
    if not return_series:
        mfi_values = mfi_values.values
    
    return mfi_values


def vwap(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    volume: Union[pd.Series, np.ndarray],
    reset_period: Optional[str] = None
) -> Union[pd.Series, np.ndarray]:
    """
    Calculate Volume Weighted Average Price (VWAP).
    
    Parameters
    ----------
    high : pd.Series or np.ndarray
        High prices.
    low : pd.Series or np.ndarray
        Low prices.
    close : pd.Series or np.ndarray
        Close prices.
    volume : pd.Series or np.ndarray
        Volume data.
    reset_period : str, optional
        Period to reset VWAP calculation. Options: 'day', 'week', 'month'.
        If None, VWAP is calculated without resetting.
        
    Returns
    -------
    pd.Series or np.ndarray
        VWAP values.
    """
    # Convert to pandas Series for calculation if numpy arrays
    if not isinstance(high, pd.Series):
        high = pd.Series(high)
        low = pd.Series(low)
        close = pd.Series(close)
        volume = pd.Series(volume)
        return_series = False
    else:
        return_series = True
    
    # Ensure we have a DatetimeIndex for reset_period
    if reset_period is not None and not isinstance(high.index, pd.DatetimeIndex):
        raise ValueError("DatetimeIndex required for reset_period")
    
    # Calculate typical price
    tp = (high + low + close) / 3
    
    # Calculate VWAP
    if reset_period is None:
        # No reset, calculate cumulative VWAP
        cumulative_tp_volume = (tp * volume).cumsum()
        cumulative_volume = volume.cumsum()
        vwap_values = cumulative_tp_volume / cumulative_volume
    else:
        # Reset VWAP based on period
        if reset_period == 'day':
            grouper = pd.Grouper(freq='D')
        elif reset_period == 'week':
            grouper = pd.Grouper(freq='W')
        elif reset_period == 'month':
            grouper = pd.Grouper(freq='M')
        else:
            raise ValueError("reset_period must be one of 'day', 'week', 'month'")
        
        # Group by reset period
        tp_volume = tp * volume
        grouped = pd.concat([tp_volume, volume], axis=1)
        grouped.columns = ['tp_volume', 'volume']
        
        # Calculate cumulative values within each group
        grouped['cumulative_tp_volume'] = grouped.groupby(grouper)['tp_volume'].cumsum()
        grouped['cumulative_volume'] = grouped.groupby(grouper)['volume'].cumsum()
        
        # Calculate VWAP
        vwap_values = grouped['cumulative_tp_volume'] / grouped['cumulative_volume']
    
    # Return as numpy array if input was numpy arrays
    if not return_series:
        vwap_values = vwap_values.values
    
    return vwap_values


def volume_profile(
    price: Union[pd.Series, np.ndarray],
    volume: Union[pd.Series, np.ndarray],
    n_bins: int = 50
) -> Dict[str, Union[pd.Series, np.ndarray]]:
    """
    Calculate Volume Profile.
    
    Parameters
    ----------
    price : pd.Series or np.ndarray
        Price data.
    volume : pd.Series or np.ndarray
        Volume data.
    n_bins : int, default=50
        Number of price bins.
        
    Returns
    -------
    Dict[str, pd.Series or np.ndarray]
        Dictionary with 'price_bins', 'volume_profile', 'poc', and 'value_area' keys.
    """
    # Convert to numpy arrays for calculation
    if isinstance(price, pd.Series):
        price_values = price.values
        volume_values = volume.values
        return_series = True
    else:
        price_values = price
        volume_values = volume
        return_series = False
    
    # Calculate price bins
    price_min = np.min(price_values)
    price_max = np.max(price_values)
    price_bins = np.linspace(price_min, price_max, n_bins + 1)
    bin_centers = (price_bins[:-1] + price_bins[1:]) / 2
    
    # Calculate volume profile
    volume_profile_values, _ = np.histogram(price_values, bins=price_bins, weights=volume_values)
    
    # Find point of control (price level with highest volume)
    poc_idx = np.argmax(volume_profile_values)
    poc = bin_centers[poc_idx]
    
    # Calculate value area (70% of volume)
    total_volume = np.sum(volume_profile_values)
    value_area_volume = 0.7 * total_volume
    
    # Sort bins by volume (descending)
    sorted_idx = np.argsort(volume_profile_values)[::-1]
    cumulative_volume = 0
    value_area_idx = []
    
    for idx in sorted_idx:
        value_area_idx.append(idx)
        cumulative_volume += volume_profile_values[idx]
        if cumulative_volume >= value_area_volume:
            break
    
    # Get min and max price in value area
    min_idx = np.min(value_area_idx)
    max_idx = np.max(value_area_idx)
    value_area = (bin_centers[min_idx], bin_centers[max_idx])
    
    # Return as pandas Series if input was Series
    if return_series:
        price_bins = pd.Series(bin_centers)
        volume_profile_values = pd.Series(volume_profile_values, index=price_bins)
    
    return {
        'price_bins': bin_centers,
        'volume_profile': volume_profile_values,
        'poc': poc,
        'value_area': value_area
    }


def chaikin_money_flow(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    volume: Union[pd.Series, np.ndarray],
    window: int = 20
) -> Union[pd.Series, np.ndarray]:
    """
    Calculate Chaikin Money Flow (CMF).
    
    Parameters
    ----------
    high : pd.Series or np.ndarray
        High prices.
    low : pd.Series or np.ndarray
        Low prices.
    close : pd.Series or np.ndarray
        Close prices.
    volume : pd.Series or np.ndarray
        Volume data.
    window : int, default=20
        Window size for CMF calculation.
        
    Returns
    -------
    pd.Series or np.ndarray
        CMF values.
    """
    # Convert to pandas Series for calculation if numpy arrays
    if not isinstance(high, pd.Series):
        high = pd.Series(high)
        low = pd.Series(low)
        close = pd.Series(close)
        volume = pd.Series(volume)
        return_series = False
    else:
        return_series = True
    
    # Calculate Money Flow Multiplier
    mfm = ((close - low) - (high - close)) / (high - low)
    
    # Handle division by zero
    mfm = mfm.replace([np.inf, -np.inf], 0)
    mfm = mfm.fillna(0)
    
    # Calculate Money Flow Volume
    mfv = mfm * volume
    
    # Calculate Chaikin Money Flow
    cmf_values = mfv.rolling(window=window).sum() / volume.rolling(window=window).sum()
    
    # Return as numpy array if input was numpy arrays
    if not return_series:
        cmf_values = cmf_values.values
    
    return cmf_values


# -------------------------------------------------------------------------
# Trend Strength Indicators
# -------------------------------------------------------------------------

def adx(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    window: int = 14
) -> Dict[str, Union[pd.Series, np.ndarray]]:
    """
    Calculate Average Directional Index (ADX).
    
    Parameters
    ----------
    high : pd.Series or np.ndarray
        High prices.
    low : pd.Series or np.ndarray
        Low prices.
    close : pd.Series or np.ndarray
        Close prices.
    window : int, default=14
        Window size for ADX calculation.
        
    Returns
    -------
    Dict[str, pd.Series or np.ndarray]
        Dictionary with 'adx', 'di_plus', and 'di_minus' keys.
    """
    # Convert to pandas Series for calculation if numpy arrays
    if not isinstance(high, pd.Series):
        high = pd.Series(high)
        low = pd.Series(low)
        close = pd.Series(close)
        return_series = False
    else:
        return_series = True
    
    # Calculate True Range
    prev_close = close.shift(1)
    tr1 = high - low  # Current high - current low
    tr2 = (high - prev_close).abs()  # Current high - previous close
    tr3 = (low - prev_close).abs()  # Current low - previous close
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Calculate Directional Movement
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    # Calculate Plus Directional Movement (+DM)
    plus_dm = pd.Series(0, index=high.index)
    plus_dm[(up_move > down_move) & (up_move > 0)] = up_move[(up_move > down_move) & (up_move > 0)]
    
    # Calculate Minus Directional Movement (-DM)
    minus_dm = pd.Series(0, index=high.index)
    minus_dm[(down_move > up_move) & (down_move > 0)] = down_move[(down_move > up_move) & (down_move > 0)]
    
    # Calculate smoothed True Range and Directional Movement
    smoothed_tr = tr.rolling(window=window).sum()
    smoothed_plus_dm = plus_dm.rolling(window=window).sum()
    smoothed_minus_dm = minus_dm.rolling(window=window).sum()
    
    # Calculate Directional Indicators
    di_plus = 100 * smoothed_plus_dm / smoothed_tr
    di_minus = 100 * smoothed_minus_dm / smoothed_tr
    
    # Calculate Directional Index
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus)
    
    # Calculate Average Directional Index
    adx_values = dx.rolling(window=window).mean()
    
    # Return as numpy arrays if input was numpy arrays
    if not return_series:
        adx_values = adx_values.values
        di_plus = di_plus.values
        di_minus = di_minus.values
    
    return {
        'adx': adx_values,
        'di_plus': di_plus,
        'di_minus': di_minus
    }


def aroon(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    window: int = 25
) -> Dict[str, Union[pd.Series, np.ndarray]]:
    """
    Calculate Aroon Indicator.
    
    Parameters
    ----------
    high : pd.Series or np.ndarray
        High prices.
    low : pd.Series or np.ndarray
        Low prices.
    window : int, default=25
        Window size for Aroon calculation.
        
    Returns
    -------
    Dict[str, pd.Series or np.ndarray]
        Dictionary with 'aroon_up', 'aroon_down', and 'aroon_oscillator' keys.
    """
    # Convert to pandas Series for calculation if numpy arrays
    if not isinstance(high, pd.Series):
        high = pd.Series(high)
        low = pd.Series(low)
        return_series = False
    else:
        return_series = True
    
    # Calculate Aroon Up and Down
    aroon_up = pd.Series(0, index=high.index)
    aroon_down = pd.Series(0, index=low.index)
    
    for i in range(window, len(high)):
        # Get window slice
        high_window = high.iloc[i-window+1:i+1]
        low_window = low.iloc[i-window+1:i+1]
        
        # Find the indices of the highest high and lowest low
        high_idx = high_window.argmax()
        low_idx = low_window.argmin()
        
        # Calculate periods since highest high and lowest low
        periods_since_high = window - 1 - high_idx
        periods_since_low = window - 1 - low_idx
        
        # Calculate Aroon Up and Down
        aroon_up.iloc[i] = 100 * (window - periods_since_high) / window
        aroon_down.iloc[i] = 100 * (window - periods_since_low) / window
    
    # Calculate Aroon Oscillator
    aroon_oscillator = aroon_up - aroon_down
    
    # Return as numpy arrays if input was numpy arrays
    if not return_series:
        aroon_up = aroon_up.values
        aroon_down = aroon_down.values
        aroon_oscillator = aroon_oscillator.values
    
    return {
        'aroon_up': aroon_up,
        'aroon_down': aroon_down,
        'aroon_oscillator': aroon_oscillator
    }


# -------------------------------------------------------------------------
# Oscillators
# -------------------------------------------------------------------------

def dpo(
    data: Union[pd.Series, np.ndarray],
    window: int = 20
) -> Union[pd.Series, np.ndarray]:
    """
    Calculate Detrended Price Oscillator (DPO).
    
    Parameters
    ----------
    data : pd.Series or np.ndarray
        Price or other data to calculate DPO for.
    window : int, default=20
        Window size for DPO calculation.
        
    Returns
    -------
    pd.Series or np.ndarray
        DPO values.
    """
    # Convert to pandas Series for calculation if numpy array
    if not isinstance(data, pd.Series):
        data = pd.Series(data)
        return_series = False
    else:
        return_series = True
    
    # Calculate the shifted SMA
    shift = window // 2 + 1
    sma_values = data.rolling(window=window).mean()
    
    # Calculate DPO
    dpo_values = data.shift(shift) - sma_values
    
    # Return as numpy array if input was numpy array
    if not return_series:
        dpo_values = dpo_values.values
    
    return dpo_values


def kst(
    data: Union[pd.Series, np.ndarray],
    roc1_window: int = 10,
    roc2_window: int = 15,
    roc3_window: int = 20,
    roc4_window: int = 30,
    sma1_window: int = 10,
    sma2_window: int = 10,
    sma3_window: int = 10,
    sma4_window: int = 15,
    signal_window: int = 9
) -> Dict[str, Union[pd.Series, np.ndarray]]:
    """
    Calculate Know Sure Thing (KST) Oscillator.
    
    Parameters
    ----------
    data : pd.Series or np.ndarray
        Price or other data to calculate KST for.
    roc1_window : int, default=10
        Window size for first ROC calculation.
    roc2_window : int, default=15
        Window size for second ROC calculation.
    roc3_window : int, default=20
        Window size for third ROC calculation.
    roc4_window : int, default=30
        Window size for fourth ROC calculation.
    sma1_window : int, default=10
        Window size for first SMA calculation.
    sma2_window : int, default=10
        Window size for second SMA calculation.
    sma3_window : int, default=10
        Window size for third SMA calculation.
    sma4_window : int, default=15
        Window size for fourth SMA calculation.
    signal_window : int, default=9
        Window size for signal line calculation.
        
    Returns
    -------
    Dict[str, pd.Series or np.ndarray]
        Dictionary with 'kst' and 'signal' keys.
    """
    # Convert to pandas Series for calculation if numpy array
    if not isinstance(data, pd.Series):
        data = pd.Series(data)
        return_series = False
    else:
        return_series = True
    
    # Calculate Rate of Change (ROC)
    roc1 = 100 * (data / data.shift(roc1_window) - 1)
    roc2 = 100 * (data / data.shift(roc2_window) - 1)
    roc3 = 100 * (data / data.shift(roc3_window) - 1)
    roc4 = 100 * (data / data.shift(roc4_window) - 1)
    
    # Calculate SMAs of ROCs
    sma1 = roc1.rolling(window=sma1_window).mean()
    sma2 = roc2.rolling(window=sma2_window).mean()
    sma3 = roc3.rolling(window=sma3_window).mean()
    sma4 = roc4.rolling(window=sma4_window).mean()
    
    # Calculate KST
    kst_values = sma1 + 2 * sma2 + 3 * sma3 + 4 * sma4
    
    # Calculate signal line
    signal = kst_values.rolling(window=signal_window).mean()
    
    # Return as numpy arrays if input was numpy array
    if not return_series:
        kst_values = kst_values.values
        signal = signal.values
    
    return {
        'kst': kst_values,
        'signal': signal
    } 