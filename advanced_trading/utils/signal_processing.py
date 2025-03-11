"""
Signal Processing Utilities
-------------------------
Advanced signal processing for filtering and combining trading signals.

This module provides tools for processing financial time series signals,
including filtering, normalization, and combining signals from multiple sources.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Union, Optional, Any
import logging
from pathlib import Path

# Import SciPy components conditionally
try:
    from scipy import signal, stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# Set up logging
logger = logging.getLogger(__name__)

# Check for GPU support
try:
    import cupy as cp
    import cudf
    HAS_GPU = True
    logger.info("GPU acceleration enabled for signal processing")
except ImportError:
    HAS_GPU = False
    logger.info("GPU libraries not available. Using CPU implementation.")


def normalize_signals(signals: Dict[str, float], method: str = 'minmax') -> Dict[str, float]:
    """
    Normalize multiple signals to a common scale.
    
    Args:
        signals: Dictionary of signal name to signal value
        method: Normalization method ('minmax', 'zscore', 'tanh', or 'sigmoid')
        
    Returns:
        Dictionary of normalized signals
    """
    if not signals:
        return {}
    
    values = np.array(list(signals.values()))
    
    if method == 'minmax':
        # Min-max normalization to [0, 1]
        min_val = np.min(values)
        max_val = np.max(values)
        
        # Handle the case where all values are the same
        if min_val == max_val:
            normalized = np.zeros_like(values)
        else:
            normalized = (values - min_val) / (max_val - min_val)
        
        # Scale to [-1, 1]
        normalized = 2 * normalized - 1
        
    elif method == 'zscore':
        # Z-score normalization
        mean = np.mean(values)
        std = np.std(values)
        
        # Handle zero standard deviation
        if std == 0:
            normalized = np.zeros_like(values)
        else:
            normalized = (values - mean) / std
            
        # Clip to reasonable range
        normalized = np.clip(normalized, -3, 3)
        normalized = normalized / 3  # Scale to [-1, 1]
        
    elif method == 'tanh':
        # Hyperbolic tangent normalization
        mean = np.mean(values)
        std = np.std(values)
        
        # Handle zero standard deviation
        if std == 0:
            normalized = np.zeros_like(values)
        else:
            normalized = np.tanh((values - mean) / (std + 1e-8))
    
    elif method == 'sigmoid':
        # Sigmoid normalization
        mean = np.mean(values)
        std = np.std(values)
        
        # Handle zero standard deviation
        if std == 0:
            normalized = np.zeros_like(values)
        else:
            normalized = 1 / (1 + np.exp(-(values - mean) / (std + 1e-8)))
            normalized = 2 * normalized - 1  # Scale to [-1, 1]
    
    else:
        raise ValueError(f"Unknown normalization method: {method}")
    
    # Create a new dictionary with normalized values
    return {k: float(v) for k, v in zip(signals.keys(), normalized)}


def generate_ensemble_signal(signals: Dict[str, float], 
                             weights: Optional[Dict[str, float]] = None,
                             threshold: float = 0.0) -> float:
    """
    Generate a single ensemble signal from multiple signals with optional weighting.
    
    Args:
        signals: Dictionary of signal name to signal value
        weights: Optional dictionary of signal name to weight (defaults to equal weights)
        threshold: Threshold for taking action (ensemble value must exceed this)
        
    Returns:
        Ensemble signal value
    """
    if not signals:
        return 0.0
    
    # If no weights provided, use equal weights
    if weights is None:
        weights = {k: 1.0 for k in signals}
    
    # Filter out signals that don't have weights
    signals = {k: v for k, v in signals.items() if k in weights}
    
    # Handle case where no valid signals remain
    if not signals:
        return 0.0
    
    # Calculate weighted sum
    total_weight = sum(weights[k] for k in signals)
    ensemble_value = 0.0
    
    for signal_name, signal_value in signals.items():
        if signal_name in weights:
            weight = weights[signal_name]
            ensemble_value += signal_value * weight
    
    # Normalize by total weight
    if total_weight > 0:
        ensemble_value /= total_weight
    
    # Apply threshold
    if abs(ensemble_value) < threshold:
        return 0.0
    
    return ensemble_value


def smooth_signal(series: Union[pd.Series, np.ndarray], 
                  method: str = 'ewm', 
                  **kwargs) -> np.ndarray:
    """
    Apply smoothing to a signal to reduce noise.
    
    Args:
        series: Time series data
        method: Smoothing method ('ewm', 'sma', 'lowpass', or 'kalman')
        **kwargs: Additional parameters for the specific smoothing method
        
    Returns:
        Smoothed signal as numpy array
    """
    # Convert to numpy if pandas Series
    if isinstance(series, pd.Series):
        values = series.values
    else:
        values = series
    
    if method == 'ewm':
        # Exponentially weighted moving average
        alpha = kwargs.get('alpha', 0.2)
        if isinstance(series, pd.Series):
            return series.ewm(alpha=alpha).mean().values
        else:
            # Manual EWM calculation
            smoothed = np.zeros_like(values, dtype=float)
            smoothed[0] = values[0]
            for i in range(1, len(values)):
                smoothed[i] = alpha * values[i] + (1 - alpha) * smoothed[i-1]
            return smoothed
            
    elif method == 'sma':
        # Simple moving average
        window = kwargs.get('window', 10)
        if isinstance(series, pd.Series):
            return series.rolling(window=window, min_periods=1).mean().values
        else:
            # Manual SMA calculation
            smoothed = np.zeros_like(values, dtype=float)
            for i in range(len(values)):
                start = max(0, i - window + 1)
                smoothed[i] = np.mean(values[start:i+1])
            return smoothed
            
    elif method == 'lowpass' and SCIPY_AVAILABLE:
        # Butterworth low-pass filter
        cutoff = kwargs.get('cutoff', 0.1)
        order = kwargs.get('order', 5)
        
        # Design the filter
        nyq = 0.5
        normal_cutoff = cutoff / nyq
        b, a = signal.butter(order, normal_cutoff, btype='low', analog=False)
        
        # Apply the filter
        return signal.filtfilt(b, a, values)
        
    elif method == 'kalman':
        # Simple Kalman filter
        process_variance = kwargs.get('process_variance', 1e-5)
        measurement_variance = kwargs.get('measurement_variance', 1e-3)
        
        # Initialize
        n = len(values)
        filtered = np.zeros(n)
        prediction = values[0]
        prediction_variance = 1.0
        
        # Process the data
        for i in range(n):
            # Prediction update
            prediction_variance += process_variance
            
            # Measurement update
            kalman_gain = prediction_variance / (prediction_variance + measurement_variance)
            filtered[i] = prediction + kalman_gain * (values[i] - prediction)
            prediction = filtered[i]
            prediction_variance = (1 - kalman_gain) * prediction_variance
            
        return filtered
    
    else:
        # Default to just returning the original series
        logger.warning(f"Unknown smoothing method: {method}. Returning original signal.")
        return values


def calculate_crossovers(fast_series: Union[pd.Series, np.ndarray],
                         slow_series: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """
    Calculate crossover points between two time series.
    
    Args:
        fast_series: Faster-moving series
        slow_series: Slower-moving series
        
    Returns:
        Array with 1 for bullish crossover, -1 for bearish crossover, 0 otherwise
    """
    # Convert to numpy if pandas Series
    if isinstance(fast_series, pd.Series):
        fast_values = fast_series.values
    else:
        fast_values = fast_series
        
    if isinstance(slow_series, pd.Series):
        slow_values = slow_series.values
    else:
        slow_values = slow_series
    
    # Ensure equal lengths
    n = min(len(fast_values), len(slow_values))
    fast_values = fast_values[:n]
    slow_values = slow_values[:n]
    
    # Calculate differences
    diff = fast_values - slow_values
    
    # Find crossovers
    crossovers = np.zeros(n)
    
    for i in range(1, n):
        if diff[i-1] <= 0 and diff[i] > 0:
            # Bullish crossover (fast crosses above slow)
            crossovers[i] = 1
        elif diff[i-1] >= 0 and diff[i] < 0:
            # Bearish crossover (fast crosses below slow)
            crossovers[i] = -1
    
    return crossovers


def apply_hysteresis_filter(signals: np.ndarray, 
                           enter_threshold: float = 0.5, 
                           exit_threshold: float = 0.3) -> np.ndarray:
    """
    Apply a hysteresis filter to trading signals to reduce false signals.
    
    This filter requires signals to exceed the enter_threshold to trigger a position,
    but then only exit when signals fall below the exit_threshold.
    
    Args:
        signals: Array of signal values
        enter_threshold: Threshold to enter a position
        exit_threshold: Threshold to exit a position
        
    Returns:
        Filtered signal with hysteresis
    """
    n = len(signals)
    filtered = np.zeros(n)
    position = 0  # 0 = no position, 1 = long, -1 = short
    
    for i in range(n):
        signal = signals[i]
        
        # Long position logic
        if position <= 0 and signal > enter_threshold:
            # Enter long
            position = 1
        elif position > 0 and signal < -exit_threshold:
            # Exit long and enter short
            position = -1
        # Short position logic
        elif position >= 0 and signal < -enter_threshold:
            # Enter short
            position = -1
        elif position < 0 and signal > exit_threshold:
            # Exit short and enter long
            position = 1
        # Otherwise, maintain current position
        
        # Record position
        filtered[i] = position
    
    return filtered


def calculate_adaptive_thresholds(series: Union[pd.Series, np.ndarray],
                                 window: int = 20,
                                 n_std: float = 2.0) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate adaptive thresholds based on recent volatility.
    
    Args:
        series: Time series data
        window: Window size for rolling standard deviation
        n_std: Number of standard deviations for the threshold
        
    Returns:
        Tuple of (upper_threshold, lower_threshold) arrays
    """
    # Convert to pandas if numpy array
    if isinstance(series, np.ndarray):
        series = pd.Series(series)
    
    # Calculate rolling mean and std
    rolling_mean = series.rolling(window=window, min_periods=1).mean()
    rolling_std = series.rolling(window=window, min_periods=1).std().fillna(0)
    
    # Calculate thresholds
    upper_threshold = rolling_mean + n_std * rolling_std
    lower_threshold = rolling_mean - n_std * rolling_std
    
    return upper_threshold.values, lower_threshold.values


def apply_consensus_filter(signals: Dict[str, np.ndarray], 
                          required_agreement: float = 0.6) -> np.ndarray:
    """
    Generate consensus signal based on agreement among multiple signals.
    
    Args:
        signals: Dictionary of signal name to signal array
        required_agreement: Fraction of signals required to agree (0.0-1.0)
        
    Returns:
        Consensus signal array
    """
    if not signals:
        return np.array([])
    
    # Get the length of signals
    first_key = next(iter(signals))
    n = len(signals[first_key])
    
    # Ensure all signals have the same length
    for name, signal_array in signals.items():
        if len(signal_array) != n:
            raise ValueError(f"Signal '{name}' has different length than others")
    
    # Calculate consensus
    consensus = np.zeros(n)
    num_signals = len(signals)
    
    for i in range(n):
        # Count positive and negative signals
        pos_count = sum(1 for sig in signals.values() if sig[i] > 0)
        neg_count = sum(1 for sig in signals.values() if sig[i] < 0)
        
        # Calculate agreement ratios
        pos_agreement = pos_count / num_signals
        neg_agreement = neg_count / num_signals
        
        # Generate consensus
        if pos_agreement >= required_agreement:
            consensus[i] = 1
        elif neg_agreement >= required_agreement:
            consensus[i] = -1
        
    return consensus


def calculate_fft_components(series: Union[pd.Series, np.ndarray], 
                            num_components: int = 3) -> np.ndarray:
    """
    Extract the main periodic components from a time series using FFT.
    
    Args:
        series: Time series data
        num_components: Number of top frequency components to keep
        
    Returns:
        Reconstructed time series using only the top frequency components
    """
    if not SCIPY_AVAILABLE:
        logger.warning("SciPy not available. Cannot calculate FFT components.")
        if isinstance(series, pd.Series):
            return series.values
        return series
    
    # Convert to numpy if pandas Series
    if isinstance(series, pd.Series):
        values = series.values
    else:
        values = series
    
    # Remove mean
    mean = np.mean(values)
    detrended = values - mean
    
    # Apply FFT
    n = len(detrended)
    fft_values = np.fft.rfft(detrended)
    frequencies = np.fft.rfftfreq(n)
    
    # Get magnitudes
    magnitudes = np.abs(fft_values)
    
    # Exclude the DC component (zero frequency)
    magnitudes[0] = 0
    
    # Find top frequencies
    top_indices = np.argsort(magnitudes)[-num_components:]
    
    # Create filtered spectrum
    filtered_fft = np.zeros_like(fft_values, dtype=complex)
    filtered_fft[top_indices] = fft_values[top_indices]
    
    # Reconstruct the signal
    reconstructed = np.fft.irfft(filtered_fft, n=n)
    
    # Add back the mean
    reconstructed += mean
    
    return reconstructed 