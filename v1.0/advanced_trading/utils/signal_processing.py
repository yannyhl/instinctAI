"""
Signal Processing Utilities
-------------------------
Advanced signal processing for filtering and combining trading signals.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Union, Optional, Any
from scipy import signal, stats
from pathlib import Path
import logging

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
        logger.info("GPU acceleration enabled for signal processing")
        HAS_GPU = True
    else:
        HAS_GPU = False
except ImportError:
    logger.warning("GPU libraries not available. Using CPU implementation.")
    HAS_GPU = False


def normalize_signals(signals: Dict[str, float], method: str = 'minmax') -> Dict[str, float]:
    """
    Normalize multiple signals to a common scale.
    
    Args:
        signals: Dictionary of signal name to signal value
        method: Normalization method ('minmax', 'zscore', or 'tanh')
        
    Returns:
        Dictionary of normalized signals
    """
    if not signals:
        return {}
    
    values = np.array(list(signals.values()))
    
    if method == 'minmax':
        # Min-max normalization to [-1, 1]
        min_val = np.min(values)
        max_val = np.max(values)
        
        if max_val > min_val:
            normalized_values = 2 * (values - min_val) / (max_val - min_val) - 1
        else:
            normalized_values = np.zeros_like(values)
    
    elif method == 'zscore':
        # Z-score normalization
        mean = np.mean(values)
        std = np.std(values)
        
        if std > 0:
            normalized_values = (values - mean) / std
            # Clip to [-1, 1]
            normalized_values = np.clip(normalized_values, -1, 1)
        else:
            normalized_values = np.zeros_like(values)
    
    elif method == 'tanh':
        # Hyperbolic tangent normalization (inherently bounds to [-1, 1])
        normalized_values = np.tanh(values)
    
    else:
        logger.warning(f"Unknown normalization method: {method}. Using raw values.")
        normalized_values = values
    
    # Create new dictionary with normalized values
    return {key: float(norm_val) for key, norm_val in zip(signals.keys(), normalized_values)}


def generate_ensemble_signal(signals: Dict[str, float], 
                           weights: Optional[Dict[str, float]] = None,
                           threshold: float = 0.0) -> float:
    """
    Generate a single ensemble signal from multiple signals with optional weighting.
    
    Args:
        signals: Dictionary of signal name to signal value
        weights: Dictionary of signal name to weight
        threshold: Threshold for taking action (ensemble value must exceed this)
        
    Returns:
        Ensemble signal value
    """
    if not signals:
        return 0.0
    
    # Default to equal weights if not provided
    if weights is None:
        weights = {signal_name: 1.0 / len(signals) for signal_name in signals}
    
    # Calculate weighted sum
    ensemble_value = 0.0
    total_weight = 0.0
    
    for signal_name, signal_value in signals.items():
        if signal_name in weights:
            weight = weights[signal_name]
            ensemble_value += signal_value * weight
            total_weight += weight
    
    # Normalize by total weight
    if total_weight > 0:
        ensemble_value /= total_weight
    
    # Apply threshold
    if abs(ensemble_value) < threshold:
        return 0.0
    
    return ensemble_value


def apply_kalman_filter(series: Union[pd.Series, np.ndarray], 
                       process_variance: float = 1e-5,
                       measurement_variance: float = 1e-3) -> np.ndarray:
    """
    Apply Kalman filter to smooth a time series.
    
    Args:
        series: Time series data
        process_variance: Process variance (Q) - higher values mean more responsive filter
        measurement_variance: Measurement variance (R) - higher values mean more smoothing
        
    Returns:
        Filtered series
    """
    if isinstance(series, pd.Series):
        series = series.values
    
    # Handle NaN values
    series = np.array(series)
    nan_mask = np.isnan(series)
    
    if np.all(nan_mask):
        return np.zeros_like(series)
    
    # Replace NaNs with closest valid value
    valid_indices = np.where(~nan_mask)[0]
    if len(valid_indices) == 0:
        return np.zeros_like(series)
    
    # Simple imputation for NaNs
    for i in range(len(series)):
        if nan_mask[i]:
            # Find nearest valid index
            nearest_idx = valid_indices[np.argmin(np.abs(valid_indices - i))]
            series[i] = series[nearest_idx]
    
    # Apply Kalman filter
    n = len(series)
    filtered_series = np.zeros(n)
    
    # Initial state
    x_hat = series[0]
    p = 1.0
    
    for i in range(n):
        # Prediction
        x_hat_minus = x_hat
        p_minus = p + process_variance
        
        # Update
        k = p_minus / (p_minus + measurement_variance)
        x_hat = x_hat_minus + k * (series[i] - x_hat_minus)
        p = (1 - k) * p_minus
        
        filtered_series[i] = x_hat
    
    return filtered_series


def apply_lowpass_filter(series: Union[pd.Series, np.ndarray], 
                        cutoff: float = 0.1,
                        order: int = 5) -> np.ndarray:
    """
    Apply a low-pass filter to smooth noisy data.
    
    Args:
        series: Time series data
        cutoff: Cutoff frequency (0-1)
        order: Filter order
        
    Returns:
        Filtered series
    """
    if isinstance(series, pd.Series):
        series = series.values
    
    # Handle NaN values
    nan_mask = np.isnan(series)
    
    if np.all(nan_mask):
        return np.zeros_like(series)
    
    # Replace NaNs with closest valid value for filtering
    series_clean = series.copy()
    for i in range(len(series)):
        if nan_mask[i]:
            valid_indices = np.where(~nan_mask)[0]
            if len(valid_indices) > 0:
                nearest_idx = valid_indices[np.argmin(np.abs(valid_indices - i))]
                series_clean[i] = series_clean[nearest_idx]
            else:
                series_clean[i] = 0
    
    # Design Butterworth filter
    nyquist = 0.5
    normal_cutoff = cutoff / nyquist
    b, a = signal.butter(order, normal_cutoff, btype='low', analog=False)
    
    # Apply filter (forward and backward for zero phase)
    filtered_series = signal.filtfilt(b, a, series_clean)
    
    # Restore NaN values
    filtered_series[nan_mask] = np.nan
    
    return filtered_series


def calculate_crossovers(fast_series: Union[pd.Series, np.ndarray],
                        slow_series: Union[pd.Series, np.ndarray]) -> np.ndarray:
    """
    Calculate crossover points between two series.
    
    Args:
        fast_series: Faster-moving series
        slow_series: Slower-moving series
        
    Returns:
        Array with 1 for bullish crossover, -1 for bearish crossover, 0 otherwise
    """
    if isinstance(fast_series, pd.Series):
        fast_series = fast_series.values
    if isinstance(slow_series, pd.Series):
        slow_series = slow_series.values
    
    # Ensure equal lengths
    length = min(len(fast_series), len(slow_series))
    fast_series = fast_series[:length]
    slow_series = slow_series[:length]
    
    # Initialize result array
    crossovers = np.zeros(length)
    
    # Calculate differences
    diff = fast_series - slow_series
    
    # Find crossover points (where diff changes sign)
    for i in range(1, length):
        if diff[i-1] <= 0 and diff[i] > 0:
            crossovers[i] = 1  # Bullish crossover
        elif diff[i-1] >= 0 and diff[i] < 0:
            crossovers[i] = -1  # Bearish crossover
    
    return crossovers


def apply_hysteresis_filter(signals: np.ndarray, enter_threshold: float = 0.5, 
                          exit_threshold: float = 0.3) -> np.ndarray:
    """
    Apply hysteresis filtering to reduce false signals.
    
    Args:
        signals: Input signal array
        enter_threshold: Threshold to enter a position
        exit_threshold: Threshold to exit a position
        
    Returns:
        Filtered signals
    """
    if enter_threshold < exit_threshold:
        logger.warning("Enter threshold should be greater than exit threshold. Swapping values.")
        enter_threshold, exit_threshold = exit_threshold, enter_threshold
    
    # Initialize result
    filtered_signals = np.zeros_like(signals)
    
    # Initialize state (0 = no position, 1 = long, -1 = short)
    state = 0
    
    # Apply hysteresis
    for i in range(len(signals)):
        signal = signals[i]
        
        if state == 0:  # No position
            if signal >= enter_threshold:
                state = 1  # Enter long
            elif signal <= -enter_threshold:
                state = -1  # Enter short
        elif state == 1:  # Long position
            if signal <= -exit_threshold:
                state = -1  # Flip to short
            elif signal < exit_threshold:
                state = 0  # Exit long
        elif state == -1:  # Short position
            if signal >= exit_threshold:
                state = 1  # Flip to long
            elif signal > -exit_threshold:
                state = 0  # Exit short
        
        filtered_signals[i] = state
    
    return filtered_signals


def calculate_adaptive_thresholds(series: Union[pd.Series, np.ndarray],
                                window: int = 20,
                                n_std: float = 2.0) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate adaptive thresholds based on recent volatility.
    
    Args:
        series: Time series data
        window: Window size for volatility calculation
        n_std: Number of standard deviations for thresholds
        
    Returns:
        Tuple of (upper_threshold, lower_threshold)
    """
    if isinstance(series, pd.Series):
        series = series.values
    
    # Initialize thresholds
    upper_threshold = np.zeros_like(series)
    lower_threshold = np.zeros_like(series)
    
    # Calculate rolling mean and standard deviation
    for i in range(window, len(series)):
        window_slice = series[i-window:i]
        mean = np.mean(window_slice)
        std = np.std(window_slice)
        
        upper_threshold[i] = mean + n_std * std
        lower_threshold[i] = mean - n_std * std
    
    # Fill initial values
    upper_threshold[:window] = upper_threshold[window]
    lower_threshold[:window] = lower_threshold[window]
    
    return upper_threshold, lower_threshold


def apply_consensus_filter(signals: Dict[str, np.ndarray], 
                         required_agreement: float = 0.6) -> np.ndarray:
    """
    Apply consensus filtering to require multiple signals to agree.
    
    Args:
        signals: Dictionary of signal arrays
        required_agreement: Fraction of signals required to agree (0-1)
        
    Returns:
        Consensus signal
    """
    if not signals:
        return np.array([])
    
    # Ensure all signals have the same length
    signal_arrays = list(signals.values())
    min_length = min(len(arr) for arr in signal_arrays)
    
    # Create arrays of 1 (positive signal), -1 (negative signal), 0 (neutral)
    binary_signals = []
    for signal in signal_arrays:
        signal = signal[:min_length]
        binary = np.zeros(min_length)
        binary[signal > 0] = 1
        binary[signal < 0] = -1
        binary_signals.append(binary)
    
    # Stack the arrays
    stacked = np.vstack(binary_signals)
    
    # Count agreements
    consensus = np.zeros(min_length)
    
    for i in range(min_length):
        # Count positive and negative signals
        pos_count = np.sum(stacked[:, i] > 0)
        neg_count = np.sum(stacked[:, i] < 0)
        total = len(binary_signals)
        
        # Check if we have enough agreement
        if pos_count / total >= required_agreement:
            consensus[i] = 1
        elif neg_count / total >= required_agreement:
            consensus[i] = -1
    
    return consensus


def calculate_fft_components(series: Union[pd.Series, np.ndarray], 
                           num_components: int = 3) -> np.ndarray:
    """
    Extract main frequency components using Fast Fourier Transform.
    
    Args:
        series: Time series data
        num_components: Number of frequency components to extract
        
    Returns:
        Reconstructed series with main components
    """
    if isinstance(series, pd.Series):
        series = series.values
    
    # Remove NaN values
    series = np.array(series)
    nan_mask = np.isnan(series)
    
    if np.all(nan_mask):
        return np.zeros_like(series)
    
    # Replace NaNs with mean
    series_clean = series.copy()
    series_clean[nan_mask] = np.mean(series_clean[~nan_mask])
    
    # Apply FFT
    fft_result = np.fft.rfft(series_clean)
    
    # Get absolute values (magnitudes)
    magnitudes = np.abs(fft_result)
    
    # Get indices of top components
    indices = np.argsort(magnitudes)[-num_components:]
    
    # Create mask for top components
    mask = np.zeros(len(fft_result), dtype=bool)
    mask[indices] = True
    
    # Zero out all other components
    filtered_fft = np.zeros_like(fft_result, dtype=complex)
    filtered_fft[mask] = fft_result[mask]
    
    # Inverse FFT to get reconstructed signal
    reconstructed = np.fft.irfft(filtered_fft, n=len(series_clean))
    
    # Restore NaN values
    reconstructed[nan_mask] = np.nan
    
    return reconstructed 