"""
Technical Indicators
------------------
Advanced technical indicators with GPU acceleration where available.
"""

import numpy as np
import pandas as pd
from typing import Optional, Union, Tuple, List, Dict, Any
from statsmodels.tsa.stattools import adfuller
from scipy import stats
from arch import arch_model
from hmmlearn import hmm
import warnings
import logging
from pathlib import Path

# Import custom modules
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
import config

# Set up logging
logger = logging.getLogger(__name__)

# Check for GPU support
try:
    if config.GPU_CONFIG["use_gpu"]:
        import cupy as cp
        import cudf
        logger.info("GPU acceleration enabled for technical indicators")
        HAS_GPU = True
    else:
        HAS_GPU = False
except ImportError:
    logger.warning("GPU libraries not available. Using CPU implementation.")
    HAS_GPU = False


def calculate_zscore(series: Union[pd.Series, np.ndarray], window: int = 20) -> np.ndarray:
    """
    Calculate z-score (normalized deviation from mean).
    
    Args:
        series: Time series data
        window: Rolling window size
        
    Returns:
        Array of z-scores
    """
    if isinstance(series, pd.Series):
        series = series.values
    
    if HAS_GPU:
        try:
            # GPU implementation
            cp_series = cp.asarray(series)
            result = cp.zeros_like(cp_series)
            
            for i in range(window, len(cp_series)):
                window_slice = cp_series[i-window:i]
                mean = cp.mean(window_slice)
                std = cp.std(window_slice)
                if std > 0:
                    result[i] = (cp_series[i] - mean) / std
            
            return cp.asnumpy(result)
        except Exception as e:
            logger.warning(f"Error in GPU calculation of z-score: {str(e)}. Falling back to CPU.")
    
    # CPU implementation
    result = np.zeros_like(series)
    
    # Calculate rolling window statistics
    for i in range(window, len(series)):
        window_slice = series[i-window:i]
        mean = np.mean(window_slice)
        std = np.std(window_slice)
        if std > 0:
            result[i] = (series[i] - mean) / std
    
    return result


def detect_regime(returns: Union[pd.Series, np.ndarray], method: str = 'volatility') -> str:
    """
    Detect the current market regime (trending, mean-reverting, high volatility).
    Simplified version for quick testing.
    
    Args:
        returns: Array or Series of returns
        method: Detection method ('hmm' or 'volatility')
        
    Returns:
        String identifying the regime
    """
    # Handle different input types
    if isinstance(returns, pd.Series):
        returns_array = returns.values
    else:
        returns_array = returns
    
    # Filter out NaN values
    returns_array = returns_array[~np.isnan(returns_array)]
    
    if len(returns_array) < 20:
        return "unknown"
    
    try:
        # Simple volatility-based method
        recent_vol = np.std(returns_array[-20:]) * np.sqrt(252)  # Annualized
        historical_vol = np.std(returns_array) * np.sqrt(252)
        
        if recent_vol > 1.5 * historical_vol:
            return "high_volatility"
        
        # Check for trend
        recent_returns = returns_array[-20:]
        positive_days = np.sum(recent_returns > 0)
        negative_days = np.sum(recent_returns < 0)
        
        if positive_days > 0.65 * len(recent_returns) or negative_days > 0.65 * len(recent_returns):
            return "trending"
        
        # Default to mean-reverting
        return "mean_reverting"
            
    except Exception as e:
        logger.error(f"Error detecting regime: {e}")
        return "unknown"


def calculate_hurst_exponent(series: Union[pd.Series, np.ndarray], 
                           min_lag: int = 2, max_lag: int = 100) -> float:
    """
    Calculate the Hurst exponent to determine if a time series is mean-reverting,
    random, or trending.
    
    Args:
        series: Time series data
        min_lag: Minimum lag for calculation
        max_lag: Maximum lag for calculation
        
    Returns:
        Hurst exponent (0-0.5: mean-reverting, 0.5: random, 0.5-1: trending)
    """
    if isinstance(series, pd.Series):
        series = series.values
    
    # Remove any NaN values
    series = series[~np.isnan(series)]
    
    if len(series) < max_lag:
        max_lag = len(series) // 2
    
    if len(series) < min_lag:
        return 0.5  # Not enough data, assume random
    
    # Create the range of lag values
    lags = range(min_lag, max_lag)
    
    # Calculate the array of variances of the differences
    tau = []
    for lag in lags:
        # Calculate price difference
        diff = np.diff(series, lag)
        
        # Calculate variance of difference
        var = np.var(diff)
        
        tau.append(var)
    
    # Calculate the slope of the log-log plot
    m = np.polyfit(np.log(lags), np.log(tau), 1)
    
    # Calculate the Hurst exponent
    hurst = m[0] / 2.0
    
    return hurst


def is_stationary(series: Union[pd.Series, np.ndarray], 
                threshold: float = 0.05) -> bool:
    """
    Test if a time series is stationary using Augmented Dickey-Fuller test.
    
    Args:
        series: Time series data
        threshold: P-value threshold for rejecting null hypothesis
        
    Returns:
        True if series is stationary, False otherwise
    """
    if isinstance(series, pd.Series):
        series = series.dropna().values
    else:
        series = series[~np.isnan(series)]
    
    if len(series) < 20:
        return False  # Not enough data
    
    try:
        # Run ADF test
        result = adfuller(series)
        
        # Get p-value
        p_value = result[1]
        
        # If p-value is less than threshold, reject null hypothesis (series is stationary)
        return p_value < threshold
        
    except Exception as e:
        logger.error(f"Error testing stationarity: {str(e)}")
        return False


def calculate_bollinger_bands(series: Union[pd.Series, np.ndarray], 
                            window: int = 20, 
                            num_std: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Bollinger Bands for a time series.
    
    Args:
        series: Time series data
        window: Window size for moving average
        num_std: Number of standard deviations for bands
        
    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    if isinstance(series, pd.Series):
        series = series.values
    
    if HAS_GPU:
        try:
            # GPU implementation
            cp_series = cp.asarray(series)
            
            # Calculate middle band (moving average)
            middle_band = cp.zeros_like(cp_series)
            for i in range(window, len(cp_series) + 1):
                middle_band[i-1] = cp.mean(cp_series[i-window:i])
            
            # Calculate standard deviation
            std = cp.zeros_like(cp_series)
            for i in range(window, len(cp_series) + 1):
                std[i-1] = cp.std(cp_series[i-window:i])
            
            # Calculate upper and lower bands
            upper_band = middle_band + (std * num_std)
            lower_band = middle_band - (std * num_std)
            
            return (cp.asnumpy(upper_band), cp.asnumpy(middle_band), cp.asnumpy(lower_band))
        except Exception as e:
            logger.warning(f"Error in GPU calculation of Bollinger Bands: {str(e)}. Falling back to CPU.")
    
    # CPU implementation
    # Initialize arrays
    middle_band = np.zeros_like(series)
    upper_band = np.zeros_like(series)
    lower_band = np.zeros_like(series)
    
    # Calculate bands
    for i in range(window - 1, len(series)):
        window_slice = series[i-window+1:i+1]
        middle_band[i] = np.mean(window_slice)
        std = np.std(window_slice)
        upper_band[i] = middle_band[i] + (std * num_std)
        lower_band[i] = middle_band[i] - (std * num_std)
    
    return upper_band, middle_band, lower_band


def calculate_rsi(series: Union[pd.Series, np.ndarray], period: int = 14) -> np.ndarray:
    """
    Calculate Relative Strength Index.
    
    Args:
        series: Time series data
        period: RSI period
        
    Returns:
        Array of RSI values
    """
    if isinstance(series, pd.Series):
        series = series.values
    
    # Calculate price changes
    deltas = np.diff(series)
    deltas = np.append([0], deltas)  # Add 0 as first element to maintain length
    
    # Create arrays for gains and losses
    gains = np.zeros_like(deltas)
    losses = np.zeros_like(deltas)
    
    gains[deltas > 0] = deltas[deltas > 0]
    losses[deltas < 0] = -deltas[deltas < 0]
    
    # Initialize outputs
    avg_gain = np.zeros_like(series)
    avg_loss = np.zeros_like(series)
    rs = np.zeros_like(series)
    rsi = np.zeros_like(series)
    
    # First average gain and loss
    avg_gain[period] = np.mean(gains[1:period+1])
    avg_loss[period] = np.mean(losses[1:period+1])
    
    # Calculate RSI using Wilder's smoothing method
    for i in range(period + 1, len(series)):
        avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i]) / period
        avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i]) / period
        
        if avg_loss[i] != 0:
            rs[i] = avg_gain[i] / avg_loss[i]
        else:
            rs[i] = 100.0  # Prevent division by zero
        
        rsi[i] = 100 - (100 / (1 + rs[i]))
    
    return rsi


def calculate_market_fear(vix: Optional[float] = None,
                         rsi: Optional[float] = None,
                         put_call_ratio: Optional[float] = None,
                         avg_true_range: Optional[float] = None,
                         weights: Optional[Dict[str, float]] = None) -> float:
    """
    Calculate a composite market fear index based on multiple indicators.
    
    Args:
        vix: VIX index value (if available)
        rsi: RSI value
        put_call_ratio: Options put/call ratio (if available)
        avg_true_range: ATR normalized by price
        weights: Dictionary of weights for each indicator
        
    Returns:
        Fear index value (0-100, higher = more fear)
    """
    # Default weights if not provided
    if weights is None:
        weights = {
            'vix': 0.4,
            'rsi': 0.3,
            'put_call_ratio': 0.2,
            'atr': 0.1
        }
    
    # Normalize each available indicator to 0-100 scale
    indicators = {}
    
    if vix is not None:
        # VIX is usually in range 10-50, normalize to 0-100
        indicators['vix'] = min(100, max(0, (vix - 10) * 2.5))
    
    if rsi is not None:
        # RSI is 0-100, but reverse it so high = fear
        indicators['rsi'] = max(0, min(100, 100 - rsi))
    
    if put_call_ratio is not None:
        # Put/call ratio usually ranges from 0.5 to 1.5
        # Higher values indicate more fear
        indicators['put_call_ratio'] = min(100, max(0, (put_call_ratio - 0.5) * 100))
    
    if avg_true_range is not None:
        # ATR as % of price, usually 0.5% to 5% for crypto
        indicators['atr'] = min(100, max(0, avg_true_range * 20 * 100))
    
    # Calculate weighted average of available indicators
    if not indicators:
        return 50.0  # Default to neutral
    
    total_weight = 0.0
    fear_index = 0.0
    
    for indicator, value in indicators.items():
        if indicator in weights:
            fear_index += value * weights[indicator]
            total_weight += weights[indicator]
    
    if total_weight > 0:
        fear_index /= total_weight
    else:
        fear_index = 50.0
    
    return fear_index


def calculate_support_resistance(price_data: Union[pd.DataFrame, Dict[str, np.ndarray]],
                               window: int = 20, clusters: int = 3) -> Tuple[float, float]:
    """
    Calculate support and resistance levels using price clustering.
    
    Args:
        price_data: DataFrame with high, low, close columns or dict with these arrays
        window: Lookback window
        clusters: Number of levels to identify
        
    Returns:
        Tuple of (support_level, resistance_level) current values
    """
    # Extract price data based on input type
    if isinstance(price_data, pd.DataFrame):
        if all(col in price_data.columns for col in ['high', 'low', 'close']):
            high = price_data['high'].values[-window:]
            low = price_data['low'].values[-window:]
            close = price_data['close'].values[-window:]
        else:
            logging.warning("DataFrame missing required columns (high, low, close)")
            return 0.0, 0.0
    else:
        # Handle case where individual arrays are passed
        high = price_data
        low = low
        close = close
    
    if len(close) < window:
        return 0.0, 0.0
    
    try:
        # Simple support/resistance calculation using recent highs and lows
        resistance_level = np.max(high[-window:])
        support_level = np.min(low[-window:])
        
        # If more sophisticated clustering is needed, we can implement it here
        
        return float(support_level), float(resistance_level)
    except Exception as e:
        logger.error(f"Error calculating support/resistance: {e}")
        # Return current price as both levels in case of error
        if len(close) > 0:
            current_price = close[-1]
            return float(current_price * 0.95), float(current_price * 1.05)
        return 0.0, 0.0


def estimate_volatility(returns: np.ndarray, method: str = 'garch',
                      window: int = 20) -> float:
    """
    Estimate future volatility using various methods.
    
    Args:
        returns: Array of returns
        method: Method to use ('garch', 'ewma', or 'simple')
        window: Window for estimation
        
    Returns:
        Estimated annualized volatility
    """
    if len(returns) < window:
        return np.std(returns) * np.sqrt(252)  # Default to simple if not enough data
    
    try:
        if method == 'garch':
            # Fit GARCH(1,1) model
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = arch_model(returns, vol='Garch', p=1, q=1)
                model_fit = model.fit(disp='off')
                forecast = model_fit.forecast(horizon=1)
                return float(np.sqrt(forecast.variance.iloc[-1, 0])) * np.sqrt(252)
        
        elif method == 'ewma':
            # Exponentially weighted moving average (RiskMetrics approach)
            lambda_param = 0.94  # Standard value in RiskMetrics
            weights = np.zeros_like(returns[-window:])
            
            # Calculate weights
            for i in range(window):
                weights[i] = (1 - lambda_param) * lambda_param ** (window - i - 1)
            
            # Normalize weights
            weights = weights / np.sum(weights)
            
            # Calculate weighted variance
            returns_window = returns[-window:]
            variance = np.sum(weights * returns_window ** 2)
            
            return float(np.sqrt(variance)) * np.sqrt(252)
        
        else:  # 'simple'
            # Simple rolling window standard deviation
            return float(np.std(returns[-window:])) * np.sqrt(252)
            
    except Exception as e:
        logger.error(f"Error estimating volatility: {str(e)}")
        return float(np.std(returns[-window:])) * np.sqrt(252)  # Fallback to simple method 